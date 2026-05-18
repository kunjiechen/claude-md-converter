"""ReportLab readable fallback backend."""

from __future__ import annotations

from bs4 import BeautifulSoup

from .backend_capability import PdfBackendCapability


class ReportLabFallbackBackend:
    name = "reportlab"
    capability = PdfBackendCapability(
        name="reportlab",
        fidelity_level="non_conformant",
        readable_fallback=True,
        limitations=["text-only fallback", "tables/images/styles are degraded"],
    )

    def is_available(self) -> bool:
        try:
            import reportlab  # noqa: F401
            return True
        except Exception:
            return False

    def render(self, html: str, output_path, *, base_url: str):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase import pdfmetrics

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["style", "script"]):
            tag.decompose()
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        body.fontName = "STSong-Light"
        body.fontSize = 10
        body.leading = 14
        heading = styles["Heading2"]
        heading.fontName = "STSong-Light"
        story = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th", "pre"]):
            text = " ".join(tag.get_text(" ", strip=True).split())
            if not text:
                continue
            story.append(Paragraph(_escape(text), heading if tag.name in ("h1", "h2", "h3") else body))
            story.append(Spacer(1, 4))
        if not story:
            story.append(Paragraph("PDF fallback generated, but source text was empty.", body))
        SimpleDocTemplate(str(output_path), pagesize=A4).build(story)
        return output_path.exists() and output_path.stat().st_size > 0


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
