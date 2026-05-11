"""PDF 导出器 — HTML → weasyprint

将 HtmlRenderer 生成的语义化 HTML 通过 weasyprint 渲染为 PDF 文档。
复用同一套 Jinja2 模板和主题 CSS，确保与 HTML/Word 输出视觉一致。
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import date

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    """PDF 导出器：AST → HTML → PDF（weasyprint）"""

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

        # 页面设置
        self.page_size = options.get('page_size', 'A4')
        self.margin = options.get('margin', '2.5cm')

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
        self._renderer = HtmlRenderer(flowchart_processor=self._flowchart)

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """将 AST 转换为 PDF 文件"""
        if not HAS_WEASYPRINT:
            self._log("weasyprint 未安装，请运行: pip install weasyprint", "error")
            return False

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
        )

        # 6. weasyprint 渲染
        output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            WeasyprintHTML(string=html).write_pdf(str(output_file))
        except Exception as e:
            self._log(f"PDF 生成失败: {e}", "error")
            return False

        self._log(f"PDF文档已生成: {output_path}")
        return True

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
