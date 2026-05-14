"""PDF 导出器 — HTML → PDF backend chain

将 HtmlRenderer 生成的语义化 HTML 渲染为 PDF 文档。
优先使用 WeasyPrint；缺少 GTK/Pango 等系统库时，自动降级到
Chromium/Edge、wkhtmltopdf、LibreOffice 或纯 Python 文本 PDF。
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import date
import json
import shutil
import subprocess
import tempfile
import textwrap

from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup

from parser import MarkdownParser
from html_engine.renderer import HtmlRenderer
from html_engine.context import RenderContext
from html_engine.themes import ThemeRegistry
from flowchart import FlowchartProcessor

try:
    from weasyprint import HTML as WeasyprintHTML

    HAS_WEASYPRINT = True
except ImportError:
    WeasyprintHTML = None  # type: ignore
    HAS_WEASYPRINT = False


class PdfExporter:
    """PDF 导出器：AST → HTML → PDF（多后端降级）"""

    def __init__(self, **options):
        self.output_dir = options.get('output_dir')
        self.verbose = options.get('verbose', False)
        self.input_dir = None

        # 文档元数据
        self.doc_title = options.get('doc_title', '')
        self.doc_number = options.get('doc_number', '')
        self.doc_version = options.get('doc_version', '')
        self.doc_department = options.get('doc_department', '')
        self.doc_company = options.get('doc_company', '')
        self.include_cover = options.get('include_cover', False)

        # 页面设置
        self.page_size = options.get('page_size', 'A4')
        self.margin = options.get('margin', '2.5cm')
        self.last_backend = ''
        self.last_degraded = False
        self.last_warnings: List[str] = []

        # 主题
        theme_name = options.get('theme', 'tech-doc')
        theme_cls = ThemeRegistry.get(theme_name) or ThemeRegistry.default()
        self._theme = theme_cls() if theme_cls else None

        # 流程图处理器
        self._flowchart = FlowchartProcessor(**options)

        # Jinja2 环境
        template_dir = Path(__file__).parent.parent.parent / 'html_engine' / 'templates'
        self._jinja = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
        )

        # HTML 渲染器
        self._renderer = HtmlRenderer(flowchart_processor=self._flowchart, mermaid_render_mode='server')

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """将 AST 转换为 PDF 文件"""
        output_file = Path(output_path)

        # 1. 构建渲染上下文（同 HTML 导出器）
        context = RenderContext(
            title=self.doc_title or output_file.stem,
            number=self.doc_number,
            version=self.doc_version,
            department=self.doc_department,
            company=self.doc_company,
            date=date.today().strftime('%Y.%m.%d'),
        )

        # 2. 渲染 body HTML
        self._renderer.render(ast, context)

        # 3. 若 md 中无修订记录表，则自动生成
        if not context.revision_html:
            context.revision_html = self._generate_default_revision(context)

        # 4. 加载主题 CSS（包含 print.css）
        css_parts = []
        if self._theme:
            css_dir = Path(__file__).parent.parent.parent / 'html_engine' / 'css'
            css_parts.append(self._theme.css_tokens)
            for fname in self._theme.css_files:
                fpath = css_dir / fname
                if fpath.exists():
                    css_parts.append(fpath.read_text(encoding='utf-8'))
            # 添加 print.css（@page 规则等）
            print_css = css_dir / 'print.css'
            if print_css.exists():
                css_parts.append(print_css.read_text(encoding='utf-8'))
        theme_css = "<style>\n" + "\n".join(css_parts) + "\n</style>"

        # 5. 渲染完整 HTML 文档
        template = self._jinja.get_template('document.html.j2')
        html = template.render(
            title=context.title,
            number=context.number,
            version=context.version,
            department=context.department,
            company=context.company,
            date=context.date,
            theme_css=theme_css,
            toc_html=context.toc_html,
            body_html=context.body_html,
            revision_html=context.revision_html,
            cover_html=context.cover_html,
            flowcharts=context.flowcharts,
            show_cover=self.include_cover,
        )

        # 6. 多后端 PDF 渲染
        output_file.parent.mkdir(parents=True, exist_ok=True)
        base_url = str(self.input_dir or output_file.parent)
        if not self._write_pdf_with_fallbacks(html, output_file, base_url):
            return False

        self._write_backend_sidecar(output_file)
        backend_note = f" ({self.last_backend})" if self.last_backend else ""
        self._log(f"PDF文档已生成: {output_path}{backend_note}")
        return True

    def _write_pdf_with_fallbacks(self, html: str, output_file: Path, base_url: str) -> bool:
        errors: List[str] = []

        if HAS_WEASYPRINT:
            try:
                WeasyprintHTML(string=html, base_url=base_url).write_pdf(str(output_file))
                self.last_backend = "weasyprint"
                self.last_degraded = False
                return output_file.exists() and output_file.stat().st_size > 0
            except Exception as exc:
                errors.append(f"WeasyPrint failed: {exc}")
        else:
            errors.append("WeasyPrint is not installed")

        fallback_steps = (
            ("chromium", self._render_with_chromium),
            ("wkhtmltopdf", self._render_with_wkhtmltopdf),
            ("libreoffice", self._render_with_libreoffice),
            ("reportlab_text", self._render_with_reportlab_text),
        )
        for backend, renderer in fallback_steps:
            try:
                if renderer(html, output_file, base_url):
                    self.last_backend = backend
                    self.last_degraded = backend != "chromium"
                    self.last_warnings = errors + [self._backend_quality_note(backend)]
                    return True
            except Exception as exc:
                errors.append(f"{backend} failed: {exc}")

        self.last_warnings = errors
        self._log("PDF 生成失败，已尝试所有后端: " + " | ".join(errors), "error")
        return False

    def _render_with_chromium(self, html: str, output_file: Path, base_url: str) -> bool:
        browser = self._find_chromium()
        if not browser:
            return False
        with tempfile.TemporaryDirectory(prefix="techdoc-pdf-") as tmp:
            html_path = Path(tmp) / "document.html"
            html_path.write_text(html, encoding="utf-8")
            cmd = [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={output_file}",
                html_path.resolve().as_uri(),
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if proc.returncode != 0:
                self._log(f"Chromium PDF 后端失败: {proc.stderr[-500:]}", "error")
                return False
        return output_file.exists() and output_file.stat().st_size > 0

    def _render_with_wkhtmltopdf(self, html: str, output_file: Path, base_url: str) -> bool:
        exe = shutil.which("wkhtmltopdf")
        if not exe:
            return False
        with tempfile.TemporaryDirectory(prefix="techdoc-pdf-") as tmp:
            html_path = Path(tmp) / "document.html"
            html_path.write_text(html, encoding="utf-8")
            cmd = [exe, "--enable-local-file-access", str(html_path), str(output_file)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if proc.returncode != 0:
                self._log(f"wkhtmltopdf 后端失败: {proc.stderr[-500:]}", "error")
                return False
        return output_file.exists() and output_file.stat().st_size > 0

    def _render_with_libreoffice(self, html: str, output_file: Path, base_url: str) -> bool:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            return False
        with tempfile.TemporaryDirectory(prefix="techdoc-pdf-") as tmp:
            tmp_dir = Path(tmp)
            html_path = tmp_dir / "document.html"
            html_path.write_text(html, encoding="utf-8")
            cmd = [
                soffice,
                f"-env:UserInstallation=file://{tmp_dir / 'lo-profile'}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_dir),
                str(html_path),
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            converted = tmp_dir / "document.pdf"
            if proc.returncode != 0 or not converted.exists():
                self._log(f"LibreOffice PDF 后端失败: {proc.stderr[-500:]}", "error")
                return False
            shutil.copy2(converted, output_file)
        return output_file.exists() and output_file.stat().st_size > 0

    def _render_with_reportlab_text(self, html: str, output_file: Path, base_url: str) -> bool:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            from reportlab.pdfbase import pdfmetrics
        except ImportError:
            return False

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["style", "script"]):
            tag.decompose()

        doc = SimpleDocTemplate(str(output_file), pagesize=A4)
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        body.fontName = "STSong-Light"
        body.fontSize = 10
        body.leading = 14
        heading = styles["Heading2"]
        heading.fontName = "STSong-Light"

        story = []
        for block in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
            text = " ".join(block.get_text(" ", strip=True).split())
            if not text:
                continue
            style = heading if block.name in ("h1", "h2", "h3") else body
            prefix = "• " if block.name == "li" else ""
            for part in textwrap.wrap(prefix + text, width=90) or [prefix + text]:
                story.append(Paragraph(self._escape_reportlab(part), style))
            story.append(Spacer(1, 4))
        if not story:
            story.append(Paragraph("PDF fallback generated, but source text was empty.", body))
        doc.build(story)
        return output_file.exists() and output_file.stat().st_size > 0

    @staticmethod
    def _escape_reportlab(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _find_chromium() -> Optional[str]:
        names = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
            "msedge",
            "chrome",
        ]
        for name in names:
            found = shutil.which(name)
            if found:
                return found
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _backend_quality_note(backend: str) -> str:
        notes = {
            "chromium": "PDF 使用 Chromium/Edge 打印后端生成，CSS 兼容性较好但分页可能与 WeasyPrint 略有差异。",
            "wkhtmltopdf": "PDF 使用 wkhtmltopdf 降级生成，现代 CSS/表格分页保真度可能下降。",
            "libreoffice": "PDF 使用 LibreOffice 降级生成，HTML/CSS 保真度可能下降。",
            "reportlab_text": "PDF 使用纯文本低保真后端生成，仅保证可阅读，不保留完整表格/样式/图片。",
        }
        return notes.get(backend, f"PDF 使用 {backend} 降级生成。")

    def _write_backend_sidecar(self, output_file: Path):
        if not self.last_backend:
            return
        payload = {
            "backend": self.last_backend,
            "degraded": self.last_degraded,
            "warnings": self.last_warnings,
        }
        sidecar = output_file.with_suffix(output_file.suffix + ".backend.json")
        sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def convert_file(self, input_path: str, output_path: Optional[str] = None) -> bool:
        """转换 Markdown 文件为 PDF"""
        input_file = Path(input_path)
        if not input_file.exists():
            self._log(f"输入文件不存在: {input_path}", "error")
            return False

        self.input_dir = input_file.parent

        # 解析 Markdown
        parser = MarkdownParser()
        ast = parser.parse_file(str(input_file))

        # 生成输出路径
        if output_path is None:
            suffix = '.pdf'
            if self.output_dir:
                out_dir = Path(self.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                output_path = str(out_dir / (input_file.stem + suffix))
            else:
                output_path = str(input_file.parent / (input_file.stem + suffix))

        return self.convert(ast, output_path)

    def get_output_path(self, input_path: str, format_ext: str = '.pdf') -> str:
        """生成输出文件路径"""
        input_file = Path(input_path)
        if self.output_dir:
            out_dir = Path(self.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            return str(out_dir / (input_file.stem + format_ext))
        return str(input_file.parent / (input_file.stem + format_ext))

    @staticmethod
    def validate_input(input_path: str) -> bool:
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if p.suffix.lower() != '.md':
            raise ValueError(f"输入文件不是Markdown文件: {input_path}")
        return True

    @staticmethod
    def _generate_default_revision(context: RenderContext) -> str:
        """生成默认修订记录表 HTML"""
        rows = []
        if context.version or context.date:
            rows.append(
                f'<tr>'
                f'<td class="align-center">{context.version or "A/0"}</td>'
                f'<td class="align-center">-</td>'
                f'<td class="align-left">初版创建</td>'
                f'<td class="align-left">-</td>'
                f'<td class="align-center">{context.date or "-"}</td>'
                f'<td class="align-left">-</td>'
                f'</tr>'
            )
        header = (
            '<tr>'
            '<th class="align-center">版次</th>'
            '<th class="align-center">修订人</th>'
            '<th class="align-left">修订原因</th>'
            '<th class="align-left">修订内容</th>'
            '<th class="align-center">修订日期</th>'
            '<th class="align-left">备注</th>'
            '</tr>'
        )
        table = (
            '<table class="table table--revision">\n'
            f'<thead>\n{header}\n</thead>\n'
            f'<tbody>\n' + "\n".join(rows) + '\n</tbody>\n'
            '</table>'
        )
        return (
            '<h2 class="heading heading--2">文件修订履历表</h2>\n'
            f'{table}'
        )

    def _log(self, message: str, level: str = "info"):
        if self.verbose or level == "error":
            print(f"[{level.upper()}] {message}")
