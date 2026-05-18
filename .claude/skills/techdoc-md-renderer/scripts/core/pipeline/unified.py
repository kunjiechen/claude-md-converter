"""Unified V2 render pipeline.

This entrypoint is now strict. It builds the V2 model/policy/layout chain once,
then invokes renderer adapters with no legacy fallback path.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

from diagnostics import make_diagnostic
from parser import MarkdownParser
from core.layout import LayoutPlanner
from core.normalize import ast_to_document
from core.rules import PolicyBuilder
from core.semantic import analyze_document
from renderers.base import RenderContext, RenderResult
from renderers.docx import DocxRendererAdapter
from renderers.html import HtmlRendererAdapter
from renderers.pdf import PdfRendererAdapter

from .quality_gate import evaluate_unified_quality
from .report import UnifiedRenderReport
from .trace import RenderTrace


FORMAT_ALIASES = {
    "html": "html",
    "pdf": "pdf",
    "docx": "word",
    "word": "word",
}


def render_document(
    input_path: Optional[Union[str, Path]] = None,
    *,
    markdown: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    format: str = "html",
    options: Optional[Dict[str, Any]] = None,
) -> UnifiedRenderReport:
    """Render a Markdown document through the V2 adapter pipeline.

    Parser, semantic analysis, policy resolution, and layout planning happen
    once before the selected adapter is invoked. Renderer adapters receive only
    DocumentModel, RenderPolicy, LayoutPlan, diagnostics, assets, and options.
    """

    opts = dict(options or {})
    target = _normalize_format(format)
    source_path = Path(input_path) if input_path else None
    temp_source = None
    diagnostics = []
    trace = RenderTrace()

    if not source_path and markdown is None:
        return UnifiedRenderReport(
            success=False,
            format=target,
            error="input_path or markdown is required",
            fidelity_level="non_conformant",
        )

    try:
        if source_path:
            with trace.phase("markdown_parse", input_path=str(source_path)):
                ast = MarkdownParser().parse_file(str(source_path))
            source_hint = str(source_path)
            base_path = source_path.parent
        else:
            with trace.phase("markdown_parse", input_path="<memory>"):
                ast = MarkdownParser().parse(markdown or "")
            temp_source = _write_temp_markdown(markdown or "")
            source_path = temp_source
            source_hint = "<memory>"
            base_path = temp_source.parent

        with trace.phase("document_model_build", blocks=len(ast)):
            document = ast_to_document(ast, source_hint=source_hint)
        with trace.phase("semantic_analysis"):
            semantic = analyze_document(document, base_path=base_path, attach=True)
        with trace.phase("policy_build"):
            policy = PolicyBuilder().build(
                document,
                document_profile=opts.get("document_profile"),
                page_profile=opts.get("page_profile"),
            )
        with trace.phase("layout_plan"):
            layout_plan = LayoutPlanner().plan(document, policy, attach=True)
        diagnostics.extend(semantic.to_dict().get("diagnostics") or [])
        diagnostics.extend(layout_plan.diagnostics or [])

        out = Path(output_path) if output_path else _default_output_path(source_path, target)
        adapter = _adapter_for(target)
        context = RenderContext(
            document=document,
            policy=policy,
            layout_plan=layout_plan,
            output_path=out,
            diagnostics=diagnostics,
            assets={"base_path": str(base_path)},
            options=opts,
        )
        with trace.phase("renderer_adapter", target=target):
            result = adapter.render(context)
        if result.success:
            return _report_from_adapter(
                target=target,
                result=result,
                document=document,
                policy=policy,
                layout_plan=layout_plan,
                legacy_used=False,
                fallback_used=result.fallback_used,
                trace=trace,
            )

        diagnostics = list(result.diagnostics or diagnostics)
        diagnostics.append(make_diagnostic(
            "unified_pipeline_adapter_failed",
            "Renderer adapter failed in strict V2 mode.",
            severity="error",
            category="pipeline",
            fallback="return_failure",
            evidence=[target, result.error or ""],
        ))
        return _failure_report(target, diagnostics, result.error, trace)
    except Exception as exc:
        diagnostics.append(make_diagnostic(
            "unified_pipeline_failed",
            "Unified V2 pipeline failed before adapter output.",
            severity="error",
            category="pipeline",
            fallback="return_failure",
            evidence=[str(exc)],
        ))
        return _failure_report(target, diagnostics, str(exc), trace)
    finally:
        if temp_source and temp_source.exists():
            try:
                temp_source.unlink()
            except OSError:
                pass


def _normalize_format(format_name: str) -> str:
    target = FORMAT_ALIASES.get((format_name or "html").lower())
    if not target:
        raise ValueError("Unsupported format: %s" % format_name)
    return target


def _adapter_for(target: str):
    if target == "html":
        return HtmlRendererAdapter()
    if target == "word":
        return DocxRendererAdapter()
    if target == "pdf":
        return PdfRendererAdapter()
    raise ValueError("Unsupported adapter target: %s" % target)


def _default_output_path(source_path: Path, target: str) -> Path:
    ext = ".docx" if target == "word" else ".%s" % target
    return source_path.with_suffix(ext)


def _write_temp_markdown(markdown: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".md", prefix="techdoc-unified-", delete=False, encoding="utf-8")
    with handle:
        handle.write(markdown)
    return Path(handle.name)


def _report_from_adapter(
    *,
    target: str,
    result: RenderResult,
    document,
    policy,
    layout_plan,
    legacy_used: bool,
    fallback_used: bool,
    trace: RenderTrace,
) -> UnifiedRenderReport:
    quality = evaluate_unified_quality(
        diagnostics=list(result.diagnostics or []),
        fidelity_level=result.fidelity_level,
        fallback_used=fallback_used,
        layout_plan=layout_plan.to_dict(),
        renderer_metadata=result.metadata or {},
    )
    trace_data = trace.to_dict()
    return UnifiedRenderReport(
        success=result.success,
        format=target,
        output_path=result.output_path,
        renderer_used=(result.metadata or {}).get("renderer", "%s_adapter" % target),
        fallback_used=fallback_used,
        legacy_used=legacy_used,
        fidelity_level=result.fidelity_level,
        degradation_reason=result.degradation_reason,
        diagnostics=list(result.diagnostics or []),
        diagnostics_summary=quality.diagnostics_summary,
        quality_gate=quality.to_dict(),
        render_trace=trace_data,
        performance_report=_performance_report(trace_data),
        semantic_analysis=document.metadata.get("semantic_analysis") or {},
        render_policy=policy.to_dict(),
        layout_plan=layout_plan.to_dict(),
        renderer_metadata=result.metadata or {},
        error=result.error,
    )


def _failure_report(target: str, diagnostics, error: Optional[str], trace: RenderTrace) -> UnifiedRenderReport:
    quality = evaluate_unified_quality(
        diagnostics=list(diagnostics or []),
        fidelity_level="non_conformant",
        fallback_used=False,
        layout_plan={},
    )
    trace_data = trace.to_dict()
    return UnifiedRenderReport(
        success=False,
        format=target,
        fallback_used=False,
        fidelity_level="non_conformant",
        diagnostics=list(diagnostics or []),
        diagnostics_summary=quality.diagnostics_summary,
        quality_gate=quality.to_dict(),
        render_trace=trace_data,
        performance_report=_performance_report(trace_data),
        error=error,
    )


def _performance_report(trace_data: Dict[str, Any]) -> Dict[str, Any]:
    slowest = trace_data.get("slowest_phases") or []
    return {
        "phase_timings": trace_data.get("events") or [],
        "slowest_phases": slowest,
        "cache_strategy": [
            "Cache parsed Markdown AST by source mtime/content hash.",
            "Cache resolved assets by path/stat signature.",
            "Cache prerendered diagrams by source hash and target renderer.",
            "Cache PDF backend availability checks per process.",
        ],
        "optional_parallel_strategy": [
            "Run AssetAnalysis and DiagramAnalysis independently after DocumentModel build.",
            "Preflight local image validation in a bounded thread pool.",
            "Batch render independent documents with per-document isolated reports.",
        ],
    }
