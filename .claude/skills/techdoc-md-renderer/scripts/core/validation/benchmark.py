"""Real document validation benchmark (V2-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Sequence

from api import Converter
from parser import MarkdownParser
from core.normalize import ast_to_document
from core.semantic import analyze_document


@dataclass
class RealDocumentCase:
    case_id: str
    path: str
    profile: str
    category: str
    language: str = "mixed"
    expected_features: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FidelityBenchmarkResult:
    case: Dict[str, Any]
    format: str
    v2: Dict[str, Any]
    comparison: Dict[str, Any]
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationDashboard:
    total_runs: int
    renderer_pass_rate: Dict[str, float]
    degraded_rate: Dict[str, float]
    profile_coverage: Dict[str, int]
    backend_instability: Dict[str, int]
    known_fidelity_gaps: List[str]
    rollout_recommendation: Dict[str, Any]
    results: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def default_real_document_corpus() -> List[RealDocumentCase]:
    g_c110 = "/Users/chenkunjie/Downloads/SBPAI/Proj/规范文档/G-C110 流程图编制规范_A0/out/G-C110 流程图编制规范_A0.md"
    return [
        RealDocumentCase(
            case_id="g-c110-flowchart-spec-a0",
            path=g_c110,
            profile="requirement_spec",
            category="mixed_chinese_formal_spec",
            language="zh-CN",
            expected_features=["toc", "revision_table", "html_table", "images", "numbered_headings", "mixed_chinese_english"],
            notes="User-provided real document for initial validation.",
        ),
        RealDocumentCase("chip-manual-seed", "TODO/real-corpus/chip_manual.md", "chip_manual", "chip_manual"),
        RealDocumentCase("autosar-spec-seed", "TODO/real-corpus/autosar_spec.md", "autosar_spec", "autosar_spec"),
        RealDocumentCase("api-reference-seed", "TODO/real-corpus/api_reference.md", "api_reference", "api_reference"),
        RealDocumentCase("test-report-seed", "TODO/real-corpus/test_report.md", "test_report", "test_report"),
    ]


def run_validation_corpus(
    corpus: Iterable[RealDocumentCase],
    output_dir: Path,
    formats: Sequence[str] = ("html", "word", "pdf"),
    *,
    write_report: bool = True,
) -> ValidationDashboard:
    results: List[FidelityBenchmarkResult] = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for case in corpus:
        if not Path(case.path).exists():
            continue
        for fmt in formats:
            results.append(run_validation_case(case, output_dir, fmt))
    dashboard = build_quality_dashboard(results)
    if write_report:
        (output_dir / "validation-dashboard.json").write_text(
            json.dumps(dashboard.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return dashboard


def run_validation_case(case: RealDocumentCase, output_dir: Path, output_format: str) -> FidelityBenchmarkResult:
    output_dir = Path(output_dir) / case.case_id / output_format
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(case.path)
    ext = ".docx" if output_format == "word" else ".%s" % output_format
    v2_out = output_dir / ("v2" + ext)

    v2 = Converter().convert_file(
        source,
        format=output_format,
        output_path=v2_out,
        pipeline="v2",
        profile=case.profile,
        report=True,
    )

    document_metrics = _document_metrics(source)
    v2_metrics = _artifact_metrics(v2.output_path)
    comparison = _evaluate_v2(document_metrics, v2_metrics)
    result = FidelityBenchmarkResult(
        case=case.to_dict(),
        format=output_format,
        v2=_conversion_payload(v2, v2_metrics),
        comparison=comparison,
        recommendation=_recommendation(output_format, comparison, v2),
    )
    (output_dir / "benchmark-result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def build_quality_dashboard(results: Iterable[FidelityBenchmarkResult]) -> ValidationDashboard:
    results = list(results)
    by_format: Dict[str, List[FidelityBenchmarkResult]] = {}
    profile_coverage: Dict[str, int] = {}
    for result in results:
        by_format.setdefault(result.format, []).append(result)
        profile = result.case.get("profile", "unknown")
        profile_coverage[profile] = profile_coverage.get(profile, 0) + 1

    renderer_pass_rate = {}
    degraded_rate = {}
    backend_instability = {}
    for fmt, fmt_results in by_format.items():
        total = max(1, len(fmt_results))
        renderer_pass_rate[fmt] = round(sum(1 for r in fmt_results if r.v2.get("success")) / total, 3)
        degraded_rate[fmt] = round(sum(1 for r in fmt_results if r.v2.get("fidelity_level") in ("degraded", "non_conformant")) / total, 3)
        backend_instability[fmt] = sum(1 for r in fmt_results if r.v2.get("backend_used") in ("wkhtmltopdf", "reportlab"))

    gaps = _known_gaps(results)
    return ValidationDashboard(
        total_runs=len(results),
        renderer_pass_rate=renderer_pass_rate,
        degraded_rate=degraded_rate,
        profile_coverage=profile_coverage,
        backend_instability=backend_instability,
        known_fidelity_gaps=gaps,
        rollout_recommendation=_rollout_recommendation(results, degraded_rate),
        results=[r.to_dict() for r in results],
    )


def _document_metrics(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    ast = MarkdownParser().parse(text)
    doc = ast_to_document(ast, source_hint=str(path))
    semantic = analyze_document(doc, base_path=path.parent)
    data = semantic.to_dict()
    raw_image_count = len(re.findall(r"(<img\b|!\[[^\]]*\]\()", text, re.I))
    return {
        "line_count": len(text.splitlines()),
        "table_count": len(data.get("tables") or []),
        "asset_count": max(len(data.get("assets") or []), raw_image_count),
    }


def _artifact_metrics(path: str) -> Dict[str, Any]:
    if not path or not Path(path).exists():
        return {"exists": False, "size_bytes": 0}
    p = Path(path)
    metrics = {"exists": True, "size_bytes": p.stat().st_size}
    if p.suffix.lower() == ".html":
        text = p.read_text(encoding="utf-8", errors="ignore")
        metrics.update({
            "table_count": len(re.findall(r"<table\b", text, re.I)),
            "image_count": len(re.findall(r"<img\b", text, re.I)),
        })
    elif p.suffix.lower() == ".docx":
        from renderers.docx.comparison import collect_docx_metrics

        metrics.update(collect_docx_metrics(p).to_dict())
    elif p.suffix.lower() == ".pdf":
        metrics["pdf_readable"] = p.stat().st_size > 100
    return metrics


def _conversion_payload(result, metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "success": result.success,
        "output_path": result.output_path,
        "error": result.error,
        "pipeline": getattr(result, "pipeline", None),
        "renderer_used": getattr(result, "renderer_used", None),
        "fidelity_level": getattr(result, "fidelity_level", None),
        "quality_status": getattr(result, "quality_status", None),
        "quality_score": getattr(result, "quality_score", None),
        "backend_used": None,
        "unified_report_path": getattr(result, "unified_report_path", None),
        "metrics": metrics,
    }


def _evaluate_v2(document_metrics, v2_metrics) -> Dict[str, Any]:
    return {
        "document_metrics": document_metrics,
        "layout_fidelity": "pass" if v2_metrics.get("exists") else "fail",
        "image_fidelity": _image_fidelity(document_metrics, v2_metrics),
        "table_fidelity": _table_fidelity(document_metrics, v2_metrics),
    }


def _image_fidelity(document_metrics: Dict[str, Any], artifact_metrics: Dict[str, Any]) -> str:
    expected = int(document_metrics.get("asset_count") or 0)
    if not expected:
        return "not_applicable"
    rendered = artifact_metrics.get("image_count")
    if rendered is None:
        return "review"
    if rendered >= expected:
        return "pass"
    if rendered > 0:
        return "review"
    return "fail"


def _table_fidelity(document_metrics: Dict[str, Any], artifact_metrics: Dict[str, Any]) -> str:
    table_count = document_metrics.get("table_count", 0)
    if not table_count:
        return "not_applicable"
    artifact_tables = artifact_metrics.get("table_count")
    if artifact_tables is None:
        return "review"
    return "pass" if artifact_tables >= table_count else "review"


def _recommendation(output_format: str, comparison: Dict[str, Any], v2) -> str:
    if not v2.success:
        return "fix_v2_render_failure"
    if output_format == "pdf":
        return "monitor_pdf_backend_stability"
    if comparison.get("layout_fidelity") == "pass":
        return "v2_ready_for_corpus_expansion"
    return "review_v2_output"


def _known_gaps(results: List[FidelityBenchmarkResult]) -> List[str]:
    gaps = []
    if any(r.format == "pdf" for r in results):
        gaps.append("PDF validation remains backend-sensitive and needs per-backend corpus history.")
    return gaps


def _rollout_recommendation(results, degraded_rate) -> Dict[str, Any]:
    return {
        "html": "v2_default",
        "word": "v2_default",
        "pdf": "v2_with_backend_monitoring",
        "required_evidence": [
            "at least 10 real documents per target profile",
            "degraded rate below 5%",
            "no silent content loss diagnostics",
        ],
    }
