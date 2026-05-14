"""Page-level visual validation for DOCX/PDF artifacts.

The validator is intentionally dependency-aware: it performs real page
rendering when LibreOffice/Poppler are available, and reports a non-blocking
warning when the local environment cannot render the file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List


@dataclass
class VisualIssue:
    severity: str
    category: str
    message: str
    location: str = ""


@dataclass
class VisualValidationReport:
    file_path: str
    format: str
    renderer: str = ""
    rendered: bool = False
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[VisualIssue] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity != "critical")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["critical_count"] = self.critical_count
        payload["warning_count"] = self.warning_count
        return payload


class VisualValidator:
    """Render DOCX/PDF pages and detect obvious visual defects."""

    def __init__(self, dpi: int = 96, max_pages: int = 8):
        self.dpi = dpi
        self.max_pages = max_pages

    def validate(self, file_path: str) -> VisualValidationReport:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            return self._validate_docx(path)
        if suffix == ".pdf":
            return self._validate_pdf(path)
        report = VisualValidationReport(str(path), suffix.lstrip(".") or "unknown")
        self._add(report, "warning", "visual", "该格式暂不支持页面级视觉校验")
        return report

    def _validate_docx(self, path: Path) -> VisualValidationReport:
        report = VisualValidationReport(str(path), "docx")
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            self._add(report, "warning", "dependency", "未安装 LibreOffice，跳过 DOCX 页面级视觉校验")
            report.metrics["renderer_available"] = False
            return report

        report.renderer = "libreoffice+pdftoppm"
        with tempfile.TemporaryDirectory(prefix="techdoc-visual-") as tmp:
            tmp_dir = Path(tmp)
            cmd = [
                soffice,
                f"-env:UserInstallation=file://{tmp_dir / 'lo-profile'}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_dir),
                str(path),
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            pdf_path = tmp_dir / f"{path.stem}.pdf"
            if proc.returncode != 0 or not pdf_path.exists():
                self._add(report, "warning", "render", "LibreOffice 未能渲染 DOCX，跳过视觉页检")
                report.metrics["render_stderr"] = proc.stderr[-500:]
                return report
            return self._validate_pdf_pages(pdf_path, report)

    def _validate_pdf(self, path: Path) -> VisualValidationReport:
        report = VisualValidationReport(str(path), "pdf", renderer="pdftoppm")
        return self._validate_pdf_pages(path, report)

    def _validate_pdf_pages(self, path: Path, report: VisualValidationReport) -> VisualValidationReport:
        pdftoppm = shutil.which("pdftoppm")
        if not pdftoppm:
            self._add(report, "warning", "dependency", "未安装 Poppler(pdftoppm)，跳过页面级视觉校验")
            report.metrics["renderer_available"] = False
            return report

        try:
            from PIL import Image
        except ImportError:
            self._add(report, "warning", "dependency", "未安装 Pillow，跳过页面图片分析")
            report.metrics["renderer_available"] = False
            return report

        with tempfile.TemporaryDirectory(prefix="techdoc-pages-") as tmp:
            prefix = str(Path(tmp) / "page")
            cmd = [
                pdftoppm,
                "-png",
                "-r",
                str(self.dpi),
                "-f",
                "1",
                "-l",
                str(self.max_pages),
                str(path),
                prefix,
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            if proc.returncode != 0:
                self._add(report, "warning", "render", "pdftoppm 未能渲染页面，跳过视觉页检")
                report.metrics["render_stderr"] = proc.stderr[-500:]
                return report

            pages = sorted(Path(tmp).glob("page-*.png"))
            report.rendered = bool(pages)
            report.metrics["rendered_pages"] = len(pages)
            report.metrics["dpi"] = self.dpi
            if not pages:
                self._add(report, "critical", "visual", "没有渲染出任何页面")
                return report

            blank_pages: List[int] = []
            sparse_pages: List[int] = []
            page_metrics = []
            for idx, page in enumerate(pages, 1):
                metric = self._analyze_png(page, Image)
                page_metrics.append(metric)
                if metric["white_ratio"] >= 0.995:
                    blank_pages.append(idx)
                elif metric["ink_ratio"] <= 0.003:
                    sparse_pages.append(idx)

            report.metrics["pages"] = page_metrics
            if blank_pages:
                self._add(report, "critical", "blank_page", f"疑似空白页: {blank_pages[:8]}")
            if sparse_pages:
                self._add(report, "warning", "sparse_page", f"疑似内容过少页面: {sparse_pages[:8]}")
        return report

    @staticmethod
    def _analyze_png(path: Path, image_module) -> Dict[str, Any]:
        img = image_module.open(path).convert("RGB")
        width, height = img.size
        total = max(width * height, 1)
        white = 0
        ink = 0
        # Full scan is fine for low DPI and limited pages.
        for r, g, b in img.getdata():
            if r >= 248 and g >= 248 and b >= 248:
                white += 1
            if r <= 245 or g <= 245 or b <= 245:
                ink += 1
        return {
            "file": path.name,
            "width": width,
            "height": height,
            "white_ratio": round(white / total, 5),
            "ink_ratio": round(ink / total, 5),
        }

    @staticmethod
    def _add(report: VisualValidationReport, severity: str, category: str,
             message: str, location: str = ""):
        report.issues.append(VisualIssue(severity, category, message, location))

