"""Chromium print-to-PDF backend."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from .backend_capability import PdfBackendCapability


class ChromiumBackend:
    name = "chromium"
    capability = PdfBackendCapability(
        name="chromium",
        fidelity_level="review",
        paged_media=True,
        css_print=True,
        table_repeat_header=False,
        basic_svg=True,
        browser_quality=True,
        limitations=["pagination can differ from paged-media engines"],
    )

    def is_available(self) -> bool:
        return bool(self._find_chromium())

    def render(self, html: str, output_path, *, base_url: str):
        browser = self._find_chromium()
        if not browser:
            return False
        with tempfile.TemporaryDirectory(prefix="techdoc-pdf-adapter-") as tmp:
            html_path = Path(tmp) / "document.html"
            html_path.write_text(html, encoding="utf-8")
            cmd = [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={output_path}",
                html_path.resolve().as_uri(),
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            return proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0

    @staticmethod
    def _find_chromium():
        names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"]
        for name in names:
            found = shutil.which(name)
            if found:
                return found
        for candidate in [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        ]:
            if candidate.exists():
                return str(candidate)
        return None
