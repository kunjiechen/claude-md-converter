"""WeasyPrint PDF backend."""

from __future__ import annotations

from .backend_capability import PdfBackendCapability


class WeasyPrintBackend:
    name = "weasyprint"
    capability = PdfBackendCapability(
        name="weasyprint",
        fidelity_level="conformant",
        paged_media=True,
        css_print=True,
        table_repeat_header=True,
        basic_svg=True,
        limitations=["complex JavaScript diagrams require prerender"],
    )

    def is_available(self) -> bool:
        try:
            import weasyprint  # noqa: F401
            return True
        except Exception:
            return False

    def render(self, html: str, output_path, *, base_url: str):
        from weasyprint import HTML
        HTML(string=html, base_url=base_url).write_pdf(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
