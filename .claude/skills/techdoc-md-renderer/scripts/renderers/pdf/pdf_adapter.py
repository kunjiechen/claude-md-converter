"""Minimal PDF adapter: DocumentModel -> HTML adapter -> PDF backend."""

from __future__ import annotations

from pathlib import Path
import tempfile

from diagnostics import make_diagnostic
from renderers.base import RenderContext, RenderResult, RendererAdapter
from renderers.html import HtmlRendererAdapter
from .backend_registry import PdfBackendRegistry


class PdfRendererAdapter(RendererAdapter):
    target = "pdf"

    def __init__(self, registry: PdfBackendRegistry = None):
        self.registry = registry or PdfBackendRegistry()

    def render(self, context: RenderContext) -> RenderResult:
        diagnostics = list(context.diagnostics or [])
        diagnostics.extend(context.layout_plan.diagnostics)
        diagnostics.extend(self._capability_diagnostics(context))
        try:
            output_path = Path(context.output_path or "")
            if not output_path:
                raise ValueError("PDF adapter requires output_path")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            html_context = RenderContext(
                document=context.document,
                policy=context.policy,
                layout_plan=context.layout_plan,
                diagnostics=diagnostics,
                assets=context.assets,
                options=context.options,
            )
            html_result = HtmlRendererAdapter().render(html_context)
            diagnostics.extend(html_result.diagnostics)
            if not html_result.success:
                raise RuntimeError(html_result.error or "HTML adapter failed")

            adapter_policy = ((context.policy.renderer_policy.get("pdf") or {}).get("adapter_policy") or {})
            preferred = context.options.get("pdf_backend") or adapter_policy.get("preferred_backend") or "weasyprint"
            fallbacks = context.options.get("pdf_fallback_backends") or adapter_policy.get("fallback_backends") or ["chromium", "wkhtmltopdf", "reportlab"]
            backend = self.registry.select(preferred, fallbacks)
            if backend.name != preferred:
                diagnostics.append(make_diagnostic(
                    "fallback_to_review_backend",
                    "Preferred PDF backend was unavailable; selected fallback backend.",
                    severity="warning",
                    category="renderer",
                    fallback=backend.name,
                    evidence=[preferred, backend.name],
                ))
            if backend.name == "reportlab":
                diagnostics.append(make_diagnostic(
                    "reportlab_non_conformant",
                    "ReportLab fallback is readable but non-conformant for technical document layout.",
                    severity="warning",
                    category="renderer",
                    fallback="readable_text_pdf",
                    evidence=["reportlab"],
                ))
            if context.layout_plan.tables and not backend.capability.table_repeat_header:
                diagnostics.append(make_diagnostic(
                    "unsupported_backend_feature",
                    "Selected PDF backend does not declare table repeat-header support.",
                    severity="warning",
                    category="renderer",
                    fallback="table_header_repeat_not_guaranteed",
                    evidence=[backend.name, "table_repeat_header"],
                ))

            with tempfile.TemporaryDirectory(prefix="techdoc-pdf-adapter-") as tmp:
                html_path = Path(tmp) / "document.html"
                html_path.write_text(html_result.content, encoding="utf-8")
                ok = backend.render(html_result.content, output_path, base_url=str(Path(context.assets.get("base_path", output_path.parent))))
            if not ok:
                raise RuntimeError(f"PDF backend failed: {backend.name}")
            fidelity, reason = self._fidelity(backend, diagnostics)
            return RenderResult(
                success=True,
                output_path=str(output_path),
                diagnostics=diagnostics,
                fidelity_level=fidelity,
                degradation_reason=reason,
                fallback_used=backend.name != preferred,
                metadata={"renderer": "pdf_adapter", "backend_used": backend.name, "backend_capability": backend.capability.to_dict()},
            )
        except Exception as exc:
            diagnostics.append(make_diagnostic(
                "pdf_adapter_render_failed",
                "PDF adapter failed before producing output.",
                severity="error",
                category="renderer",
                fallback="legacy_pdf_renderer",
                evidence=[str(exc)],
            ))
            return RenderResult(False, diagnostics=diagnostics, fidelity_level="non_conformant", degradation_reason="pdf_adapter_render_failed", fallback_used=True, error=str(exc))

    def _capability_diagnostics(self, context: RenderContext):
        diagnostics = []
        # Table splitting and JS diagram prerendering are deliberately not solved in Phase 7.
        if any(t.overflow_risk != "low" for t in context.layout_plan.tables):
            diagnostics.append(make_diagnostic(
                "degraded_table_split",
                "PDF adapter records table overflow risk; perfect table splitting is not implemented in Phase 7.",
                severity="warning",
                category="renderer",
                fallback="overflow_wrapper_review",
            ))
        if context.layout_plan.diagrams:
            diagnostics.append(make_diagnostic(
                "degraded_pagination",
                "Diagram prerendering is required for stable paged output; PDF adapter uses HTML placeholder/browser rendering source.",
                severity="warning",
                category="renderer",
                fallback="diagram_placeholder_review",
            ))
        assets = (context.document.metadata.get("semantic_analysis") or {}).get("assets") or []
        if any(asset.get("kind") == "svg" for asset in assets):
            diagnostics.append(make_diagnostic(
                "degraded_svg_render",
                "SVG rendering depends on selected PDF backend capability.",
                severity="warning",
                category="renderer",
                fallback="backend_svg_capability_review",
            ))
        return diagnostics

    @staticmethod
    def _fidelity(backend, diagnostics):
        if backend.capability.fidelity_level == "non_conformant":
            return "non_conformant", "reportlab_non_conformant"
        if any(d.get("severity") == "error" for d in diagnostics):
            return "degraded", "error_diagnostics_present"
        if backend.capability.fidelity_level == "review":
            return "review", f"{backend.name}_review_backend"
        if any(d.get("category") in ("renderer", "asset", "layout", "unsupported") and d.get("severity") == "warning" for d in diagnostics):
            return "review", "review_diagnostics_present"
        return "conformant", ""
