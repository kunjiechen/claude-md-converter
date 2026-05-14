"""Regression runner for product-level conversion validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json
import time

from pipeline import ConversionPipeline


@dataclass
class RegressionItem:
    input_path: str
    format: str
    output_path: str = ""
    success: bool = False
    quality_status: Optional[str] = None
    quality_score: Optional[int] = None
    deliverable: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class RegressionReport:
    input_dir: str
    output_dir: str
    formats: List[str]
    total: int = 0
    passed: int = 0
    review: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0
    items: List[RegressionItem] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


class RegressionRunner:
    """Run a fixed Markdown corpus across output formats and quality gates."""

    EXCLUDED_NAMES = {"README.md", "README.markdown"}

    def __init__(self, formats: Iterable[str] = ("word", "html", "pdf"), max_retries: int = 1):
        self.formats = list(formats)
        self.max_retries = max_retries

    def run(self, input_dir: str, output_dir: str, **options) -> RegressionReport:
        start = time.time()
        root = Path(input_dir)
        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        report = RegressionReport(str(root), str(out_root), self.formats)

        md_files = sorted([
            p for p in root.rglob("*")
            if p.suffix.lower() in (".md", ".markdown") and p.name not in self.EXCLUDED_NAMES
        ])
        for md in md_files:
            rel_parent = md.relative_to(root).parent
            for fmt in self.formats:
                suffix = ".docx" if fmt == "word" else f".{fmt}"
                target_dir = out_root / rel_parent / fmt
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / f"{md.stem}{suffix}"
                item = self._run_one(md, fmt, target, **options)
                report.items.append(item)

        report.total = len(report.items)
        report.passed = sum(1 for i in report.items if i.quality_status == "pass")
        report.review = sum(1 for i in report.items if i.quality_status == "review")
        report.failed = sum(1 for i in report.items if not i.success or i.quality_status == "fail")
        report.elapsed_seconds = round(time.time() - start, 3)

        summary_path = out_root / "regression_summary.json"
        summary_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _run_one(self, md: Path, fmt: str, target: Path, **options) -> RegressionItem:
        pipeline = ConversionPipeline(max_retries=self.max_retries)
        run_options = {**options, "quality_report": True}
        result = pipeline.run(md, format=fmt, output_path=target, **run_options)
        return RegressionItem(
            input_path=str(md),
            format=fmt,
            output_path=result.output_path,
            success=result.success,
            quality_status=result.quality_status,
            quality_score=result.quality_score,
            deliverable=result.deliverable,
            error=result.error,
        )
