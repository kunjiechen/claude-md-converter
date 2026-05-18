"""wkhtmltopdf backend."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from .backend_capability import PdfBackendCapability


class WkhtmltopdfBackend:
    name = "wkhtmltopdf"
    capability = PdfBackendCapability(
        name="wkhtmltopdf",
        fidelity_level="review",
        paged_media=False,
        css_print=False,
        table_repeat_header=False,
        basic_svg=True,
        limitations=["modern CSS support is limited", "pagination fidelity is review-only"],
    )

    def is_available(self) -> bool:
        return bool(shutil.which("wkhtmltopdf"))

    def render(self, html: str, output_path, *, base_url: str):
        exe = shutil.which("wkhtmltopdf")
        if not exe:
            return False
        with tempfile.TemporaryDirectory(prefix="techdoc-pdf-adapter-") as tmp:
            html_path = Path(tmp) / "document.html"
            html_path.write_text(html, encoding="utf-8")
            proc = subprocess.run([exe, "--enable-local-file-access", str(html_path), str(output_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            return proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
