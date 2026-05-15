"""Word 导出器 — HTML → python-docx

将 HtmlRenderer 生成的语义化 HTML 转换为 Word 文档。
通过 BeautifulSoup4 解析 HTML DOM，StyleMapper 映射 CSS class，python-docx 构建输出。
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import date
import re
import copy

from bs4 import BeautifulSoup, Tag, NavigableString
from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from parser import MarkdownParser
from html_engine.renderer import HtmlRenderer
from html_engine.context import RenderContext
from html_engine.themes import ThemeRegistry
from flowchart import FlowchartProcessor
from .style_mapper import StyleMapper, ALIGN_MAP
from .style_config import ensure_styles
from .inline_processor import InlineProcessor
from .table_builder import TableBuilder
from .footnote_injector import FootnoteInjector
from .list_builder import ListBuilder
from .image_builder import ImageBuilder
from .section_builder import SectionBuilder


class WordExporter:
    """HTML → Word 导出器

    读取 HtmlRenderer 生成的语义化 HTML，通过 BeautifulSoup4 解析，
    使用 python-docx 构建 Word 文档。兼容模板（页眉/页脚/样式）。"""

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

        # 模板
        self.template_path = options.get('template')
        self._using_template = False
        self._template_revision_table = None

        # 字体（无模板时）
        self.font_name = options.get('font', '宋体')
        self.font_size = Pt(options.get('font_size', 12))

        # 流程图
        self._flowchart = FlowchartProcessor(**options)
        self._flowchart_counter = 0

        # 子模块
        self._inline_proc = InlineProcessor(self)
        self._table_builder = TableBuilder(self)
        self._footnote_injector = FootnoteInjector()
        self._list_builder = ListBuilder(self)
        self._image_builder = ImageBuilder()
        self._section_builder = SectionBuilder(self)

        # HTML 渲染器
        self._html_renderer = HtmlRenderer(flowchart_processor=self._flowchart, mermaid_render_mode='server')

        # 模板目录
        tmpl_dir = Path(__file__).parent.parent.parent
        self._template_dir = tmpl_dir

    # ============================================================
    # 公开接口
    # ============================================================

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """将 AST 转换为 Word 文档"""
        output_file = Path(output_path)

        # 0. 提取脚注定义并标记 label→ID 映射
        ast_clean = self._footnote_injector.extract_from_ast(ast)

        # 1. 渲染 HTML（使用清理后的 AST，不含 footnote_block）
        context = RenderContext(
            title=self.doc_title or output_file.stem,
            number=self.doc_number,
            version=self.doc_version,
            department=self.doc_department,
            company=self.doc_company,
            date=date.today().strftime('%Y.%m.%d'),
        )
        self._html_renderer.render(ast_clean, context)

        # 2. 创建 Word 文档
        doc = self._create_document()

        # 3. 插入 TOC（目录标题 + TOC字段 + 分页符）
        self._insert_toc_field(doc)

        # 4. 插入修订记录表（目录页之后，正文之前）
        md_has_revision = bool(context.revision_html)  # MD 中有修订记录表
        if self._template_revision_table is not None and not md_has_revision:
            # 模板有修订表且 MD 无修订数据 → 直接复用模板
            body = doc.element.body
            insert_pos = 3
            # 标题
            heading_p = OxmlElement('w:p')
            heading_pPr = OxmlElement('w:pPr')
            heading_jc = OxmlElement('w:jc')
            heading_jc.set(qn('w:val'), 'center')
            heading_pPr.append(heading_jc)
            heading_p.append(heading_pPr)
            heading_r = OxmlElement('w:r')
            heading_t = OxmlElement('w:t')
            heading_t.set(qn('xml:space'), 'preserve')
            heading_t.text = '文件修订履历表'
            heading_r.append(heading_t)
            heading_p.append(heading_r)
            body.insert(insert_pos, heading_p)
            # 表格
            body.insert(insert_pos + 1, copy.deepcopy(self._template_revision_table))
            # 尾部分页符
            page_break_p = self._section_builder.page_break_paragraph()
            body.insert(insert_pos + 2, page_break_p)
        else:
            # MD 有修订数据 或 无模板 → HTML 渲染
            revision_html = context.revision_html
            if not revision_html:
                revision_html = self._generate_default_revision_html(context)
            self._add_revision_section(doc, revision_html)

        # 5. 解析 body HTML 并逐元素转换（正文在修订记录之后）
        body_html = context.body_html
        if body_html:
            soup = BeautifulSoup(f"<body>{body_html}</body>", 'html.parser')
            self._process_body_elements(soup.body, doc)

        # 6. 注入原生脚注并输出
        output_file.parent.mkdir(parents=True, exist_ok=True)
        if self._footnote_injector.defs:
            self._footnote_injector.inject_into_docx(doc, str(output_file))
        else:
            doc.save(str(output_file))
        self._log(f"Word文档已生成: {output_path}")
        return True

    def _extract_footnotes_from_ast(self, ast: List[Dict]) -> List[Dict]:
        """(deprecated) 委托给 FootnoteInjector"""
        return self._footnote_injector.extract_from_ast(ast)

    def convert_file(self, input_path: str, output_path: Optional[str] = None) -> bool:
        """转换 Markdown 文件为 Word"""
        input_file = Path(input_path)
        if not input_file.exists():
            self._log(f"输入文件不存在: {input_path}", "error")
            return False

        self.input_dir = input_file.parent

        parser = MarkdownParser()
        ast = parser.parse_file(str(input_file))

        if output_path is None:
            if self.output_dir:
                out_dir = Path(self.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                output_path = str(out_dir / (input_file.stem + '.docx'))
            else:
                output_path = str(input_file.parent / (input_file.stem + '.docx'))

        return self.convert(ast, output_path)

    def get_output_path(self, input_path: str, format_ext: str = '.docx') -> str:
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

    # ============================================================
    # 文档创建 & 模板
    # ============================================================

    def _create_document(self) -> Document:
        """创建 Word 文档（模板优先）"""
        resolved = self._resolve_template_path()
        if resolved:
            doc = Document(resolved)
            self._using_template = True
            self._save_template_revision_table(doc)
            self._replace_header_fields(doc)
            self._clear_template_body(doc)
            self._log(f"已加载模板: {resolved}")
            ensure_styles(doc)
            return doc

        doc = Document()
        style = doc.styles['Normal']
        style.font.name = self.font_name
        style.font.size = self.font_size
        style.element.rPr.rFonts.set(qn('w:eastAsia'), self.font_name)
        ensure_styles(doc)
        return doc

    def _resolve_template_path(self) -> Optional[Path]:
        """解析模板路径：显式指定 > templates/ 目录 > 内置默认"""
        if self.template_path:
            p = Path(self.template_path)
            if p.exists():
                return p
            p = Path('templates') / self.template_path
            if p.exists():
                return p

        templates_dir = Path('templates')
        if templates_dir.exists():
            docx_files = list(templates_dir.glob('*.docx'))
            if docx_files:
                return docx_files[0]

        default = self._template_dir / 'default_template.docx'
        if default.exists():
            return default

        return None

    def _clear_template_body(self, doc: Document):
        """清除模板正文内容，保留样式/页面设置"""
        body = doc.element.body
        to_remove = []
        for child in body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag != 'sectPr':
                to_remove.append(child)
        for child in to_remove:
            body.remove(child)

    def _save_template_revision_table(self, doc: Document):
        """保存模板中的修订记录表 XML，后续复用"""
        body = doc.element.body
        for child in body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'tbl':
                self._template_revision_table = copy.deepcopy(child)
                break

    def _replace_header_fields(self, doc: Document):
        """替换页眉中的占位字段"""
        fields = {
            '制定部门：': f'制定部门：{self.doc_department}' if self.doc_department else None,
            '文件编号：': f'文件编号：{self.doc_number}' if self.doc_number else None,
            '版本：': f'版本：{self.doc_version}' if self.doc_version else None,
            '上海金脉电子科技有限公司': self.doc_company if self.doc_company else None,
            '软件模块命名规范': self.doc_title if self.doc_title else None,
        }
        # 日期字段
        today_str = date.today().strftime('%Y.%m.%d')

        for section in doc.sections:
            for header in [section.header, section.first_page_header]:
                if header is None:
                    continue
                for paragraph in header.paragraphs:
                    full_text = paragraph.text
                    for old, new in fields.items():
                        if new and old in full_text:
                            self._replace_header_text(paragraph, old, new)
                    # 日期
                    for date_key in ['制定日期', '修改日期']:
                        if date_key in full_text:
                            self._replace_header_text(paragraph, date_key, today_str)

    @staticmethod
    def _replace_header_text(paragraph, old: str, new: str):
        """替换页眉段落中的文本（合并跨 run 文本后替换到首个 run）"""
        full = paragraph.text
        if old not in full:
            return
        replaced = full.replace(old, new)
        runs = paragraph.runs
        if runs:
            runs[0].text = replaced
            for r in runs[1:]:
                r.text = ''

    # ============================================================
    # 正文元素处理
    # ============================================================

    def _process_body_elements(self, body: Tag, doc: Document):
        """遍历 body 子元素并分派到对应处理方法"""
        for element in body.children:
            if isinstance(element, NavigableString):
                continue
            tag = element.name.lower() if hasattr(element, 'name') else None
            if tag is None:
                continue

            if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._add_heading(element, doc)
            elif tag == 'p':
                self._add_paragraph(element, doc)
            elif tag in ('ul', 'ol'):
                self._add_list(element, doc, level=0)
            elif tag == 'table':
                self._table_builder.build(element, doc)
            elif tag == 'div' and 'prose-group' in element.get('class', []):
                self._process_body_elements(element, doc)
            elif tag == 'div' and 'code-block' in element.get('class', []):
                self._add_code_block(element, doc)
            elif tag == 'pre':
                self._add_code_block(element, doc)
            elif tag == 'blockquote':
                self._add_blockquote(element, doc)
            elif tag == 'figure':
                if 'flowchart' in element.get('class', []):
                    self._add_flowchart_element(element, doc)
                else:
                    self._add_image(element, doc)
            elif tag == 'hr':
                classes = element.get('class', [])
                if 'pagebreak' in classes:
                    self._add_pagebreak(doc)
                elif 'footnotes-sep' in classes:
                    pass  # 脚注分隔线由原生脚注处理
                else:
                    self._add_hr(doc)
            elif tag == 'dl':
                self._add_definition_list(element, doc)
            elif tag == 'div' and 'math' in element.get('class', []):
                self._add_math_block(element, doc)
            elif tag == 'ol' and 'footnotes' in element.get('class', []):
                # 脚注块：在正文末尾统一处理
                pass
            else:
                # 未知元素兜底：提取纯文本
                text = element.get_text(strip=True)
                if text:
                    self._add_paragraph_text(doc, text)

    # 匹配 MD 中手动编号前缀，如 "1.3 "、"2.1.3 "、"1. "、"1 " 等
    _HEADING_NUM_RE = re.compile(r'^\d+(\.\d+)*\.?\s+')

    def _add_heading(self, tag: Tag, doc: Document):
        """添加标题，去除 MD 中手动编号（Word 模板自动编号）"""
        level = int(tag.name[1])
        text = tag.get_text(strip=False)
        text = self._HEADING_NUM_RE.sub('', text)
        style_name = StyleMapper.get_paragraph_style(tag)
        self._safe_add_heading(doc, text, level, style_name)

    def _safe_add_heading(self, doc: Document, text: str, level: int, style_name: str):
        """安全添加标题（样式不存在时降级为 Normal + 粗体）"""
        if self._has_style(doc, style_name):
            heading = doc.add_heading(text, level=level)
            heading.style = doc.styles[style_name]
        else:
            heading = doc.add_paragraph()
            run = heading.add_run(text)
            run.font.bold = True
            run.font.size = Pt({1: 22, 2: 16, 3: 14, 4: 12, 5: 10, 6: 10}.get(level, 12))

    def _add_paragraph(self, tag: Tag, doc: Document):
        """添加段落（含内联格式），根据内容自动选择最佳样式"""
        style_name = StyleMapper.classify_paragraph(tag)
        para = doc.add_paragraph(style=style_name) if self._has_style(doc, style_name) else doc.add_paragraph()
        self._process_inline_runs(para, tag)
        # 对齐（样式已指定时跳过覆盖）
        align = StyleMapper.get_alignment(tag)
        if align is not None and style_name not in ('公式',):
            para.alignment = align

    def _add_paragraph_text(self, doc: Document, text: str):
        """添加纯文本段落（兜底），使用正文2样式"""
        style_name = '正文2'
        para = doc.add_paragraph(style=style_name) if self._has_style(doc, style_name) else doc.add_paragraph()
        para.add_run(text)

    def _add_list(self, tag: Tag, doc: Document, level: int = 0):
        """添加列表（委托给 ListBuilder）"""
        self._list_builder.build(tag, doc, level)

    def _add_code_block(self, tag: Tag, doc: Document):
        """添加代码块。若内容为规范语法条目则使用「规范」样式，否则用代码格式。
        混合内容（spec 行占比不足 40%）则逐行分类。"""
        code_tag = tag.find('code') if tag.name != 'code' else tag
        text = code_tag.get_text() if code_tag else tag.get_text()

        # 判断是否为规范语法条目
        spec_style = StyleMapper.classify_code_block(text)
        if spec_style and self._has_style(doc, spec_style):
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                para = doc.add_paragraph(style=spec_style)
                para.add_run(line)
            return

        # 混合内容：逐行分类（规范行 → 规范样式，其余 → 正文2）
        has_spec = self._has_style(doc, '规范')
        has_body = self._has_style(doc, '正文2')
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            line_style = StyleMapper.classify_code_line(stripped)
            if line_style == '规范' and has_spec:
                para = doc.add_paragraph(style='规范')
                para.add_run(stripped)
            elif has_body:
                para = doc.add_paragraph(style='正文2')
                para.add_run(stripped)
            else:
                para = doc.add_paragraph()
                run = para.add_run(stripped)
                run.font.name = 'Courier New'
                run.font.size = Pt(10)

    def _add_blockquote(self, tag: Tag, doc: Document, level: int = 0):
        """添加引用块，保留内联格式"""
        for child in tag.children:
            if isinstance(child, NavigableString):
                continue
            name = child.name if hasattr(child, 'name') else None
            if name is None:
                continue

            # 为引用块内元素统一添加缩进和左边框
            if name == 'p':
                body_style = '正文2'
                para = doc.add_paragraph(style=body_style) if self._has_style(doc, body_style) else doc.add_paragraph()
                self._process_inline_runs(para, child)
                self._style_blockquote_para(para, level)
            elif name in ('ul', 'ol'):
                self._add_list(child, doc)
            elif name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._add_heading(child, doc)
            elif name == 'table':
                self._table_builder.build(child, doc)
            elif name == 'div' and 'code-block' in child.get('class', []):
                self._add_code_block(child, doc)
            elif name == 'pre':
                self._add_code_block(child, doc)
            elif name == 'blockquote':
                self._add_blockquote(child, doc, level + 1)
            else:
                text = child.get_text(strip=True)
                if text:
                    para = doc.add_paragraph()
                    para.add_run(text)
                    self._style_blockquote_para(para, level)

    def _style_blockquote_para(self, para, level: int = 0):
        """为引用块段落添加缩进和左边框，level 递增缩进"""
        base_indent = 1 + level * 0.75
        para.paragraph_format.left_indent = Cm(base_indent)
        para.paragraph_format.right_indent = Cm(0.5)
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        left = OxmlElement('w:left')
        left.set(qn('w:val'), 'single')
        left.set(qn('w:sz'), '12')
        left.set(qn('w:space'), '8')
        left.set(qn('w:color'), 'BFBFBF')
        pBdr.append(left)
        pPr.append(pBdr)

    def _add_image(self, tag: Tag, doc: Document):
        """添加图片（委托给 ImageBuilder）"""
        self._image_builder.add_image(tag, doc)

    @classmethod
    def _get_image_physical_size(cls, data: bytes):
        """兼容旧调用：从图片字节数据获取物理尺寸（EMU）"""
        return ImageBuilder._get_image_physical_size(data)

    @classmethod
    def _get_image_physical_size_file(cls, path: str):
        """兼容旧调用：从文件获取图片物理尺寸（EMU）"""
        return ImageBuilder._get_image_physical_size_file(path)

    def _add_flowchart_element(self, tag: Tag, doc: Document):
        """添加流程图（委托给 ImageBuilder）"""
        self._image_builder.add_flowchart_element(tag, doc)

    def _add_hr(self, doc: Document):
        """添加水平分割线"""
        para = doc.add_paragraph()
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), '808080')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _add_pagebreak(self, doc: Document):
        """插入硬分页符（委托给 SectionBuilder）"""
        self._section_builder.add_pagebreak(doc)

    def _add_definition_list(self, tag: Tag, doc: Document):
        """添加定义列表，<dt> 使用「小标题」样式"""
        sub_heading_style = '小标题'
        has_sub_heading = self._has_style(doc, sub_heading_style)
        for child in tag.children:
            if isinstance(child, NavigableString):
                continue
            if child.name == 'dt':
                para = doc.add_paragraph(style=sub_heading_style) if has_sub_heading else doc.add_paragraph()
                run = para.add_run(child.get_text(strip=False).rstrip('；').rstrip(';'))
                if not has_sub_heading:
                    run.font.bold = True
            elif child.name == 'dd':
                para = doc.add_paragraph()
                para.paragraph_format.left_indent = Cm(0.85)
                para.add_run(child.get_text(strip=False))

    def _add_math_block(self, tag: Tag, doc: Document):
        """添加数学公式块，使用「公式」样式"""
        text = tag.get_text(strip=False)
        # 去除 \[ \] 定界符
        text = text.strip()
        if text.startswith('\\['):
            text = text[2:]
        if text.endswith('\\]'):
            text = text[:-2]
        text = text.strip()
        style_name = '公式'
        para = doc.add_paragraph(style=style_name) if self._has_style(doc, style_name) else doc.add_paragraph()
        if not self._has_style(doc, style_name):
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.font.name = 'Cambria Math'
        run.font.italic = True
        run.font.size = Pt(11)

    # ============================================================
    # 内联格式处理
    # ============================================================

    def _process_inline_runs(self, para, tag: Tag):
        """递归处理 HTML 内联元素，生成 Word runs"""
        self._inline_proc.process(para, tag)

    def _render_single_inline(self, para, element):
        """渲染单个内联元素（委托给 InlineProcessor）"""
        self._inline_proc._render_single(para, element)

    def _add_footnote_reference(self, para, label: str):
        """添加脚注引用（委托给 FootnoteInjector）"""
        self._footnote_injector.add_reference(para, label)

    def _add_hyperlink(self, para, text: str, url: str):
        """添加超链接"""
        r_id = para.part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
                                  is_external=True)
        hyperlink = OxmlElement('w:hyperlink')
        hyperlink.set(qn('r:id'), r_id)
        run_el = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        color = OxmlElement('w:color')
        color.set(qn('w:val'), '0563C1')
        rPr.append(color)
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        rPr.append(u)
        run_el.append(rPr)
        t_el = OxmlElement('w:t')
        t_el.set(qn('xml:space'), 'preserve')
        t_el.text = text
        run_el.append(t_el)
        hyperlink.append(run_el)
        para._p.append(hyperlink)

    # ============================================================
    # TOC & 修订记录
    # ============================================================

    def _insert_toc_field(self, doc: Document):
        """在正文开头插入 Word 原生 TOC 字段（委托给 SectionBuilder）"""
        self._section_builder.insert_toc_field(doc)

    @staticmethod
    def _generate_default_revision_html(context) -> str:
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
        return (
            '<h2 class="heading heading--2">文件修订履历表</h2>\n'
            '<table class="table table--revision">\n'
            f'<thead>\n{header}\n</thead>\n'
            f'<tbody>\n' + "\n".join(rows) + '\n</tbody>\n'
            '</table>'
        )

    def _add_revision_section(self, doc: Document, revision_html: str):
        """添加修订记录表（委托给 SectionBuilder）"""
        self._section_builder.add_revision_section(doc, revision_html)

    # ============================================================
    # 工具方法
    # ============================================================

    # 列表编号：abstractNumId 映射
    _BULLET_ABSTRACT_NUM = '0'   # bullet 字符
    _ORDERED_ABSTRACT_NUM = '1'  # %1、 %2) %3. 格式

    def _create_list_numId(self, doc: Document, is_ordered: bool) -> int:
        """创建新的 num 实例引用 abstractNum，返回 numId（每个列表独立编号）"""
        numbering = doc.part.numbering_part.element
        abstract_num_id = self._ORDERED_ABSTRACT_NUM if is_ordered else self._BULLET_ABSTRACT_NUM

        max_id = max((int(n.get(qn('w:numId'), '0'))
                      for n in numbering.findall(qn('w:num'))), default=0)

        new_id = max_id + 1
        new_num = OxmlElement('w:num')
        new_num.set(qn('w:numId'), str(new_id))
        abs_ref = OxmlElement('w:abstractNumId')
        abs_ref.set(qn('w:val'), abstract_num_id)
        new_num.append(abs_ref)
        numbering.append(new_num)
        return new_id

    @staticmethod
    def _apply_list_numbering(para, num_id: int, level: int):
        """为段落添加 Word 原生列表编号 (w:numPr) + 显式缩进"""
        pPr = para._p.get_or_add_pPr()
        # 移除可能存在的旧编号
        old_numPr = pPr.find(qn('w:numPr'))
        if old_numPr is not None:
            pPr.remove(old_numPr)
        numPr = OxmlElement('w:numPr')
        ilvl = OxmlElement('w:ilvl')
        ilvl.set(qn('w:val'), str(level))
        numPr.append(ilvl)
        numId_el = OxmlElement('w:numId')
        numId_el.set(qn('w:val'), str(num_id))
        numPr.append(numId_el)
        pPr.append(numPr)
        # 显式缩进（覆盖模板抽象编号定义中的大缩进值）
        # 与正文 Normal 样式的 firstLine=200 对齐，每级递增 240 twips
        base_left = 240 + level * 240
        old_ind = pPr.find(qn('w:ind'))
        if old_ind is not None:
            pPr.remove(old_ind)
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), str(base_left))
        ind.set(qn('w:hanging'), '240')
        pPr.append(ind)
        # 零间距避免列表项间空行
        spacing = OxmlElement('w:spacing')
        spacing.set(qn('w:before'), '0')
        spacing.set(qn('w:after'), '0')
        spacing.set(qn('w:line'), '240')
        spacing.set(qn('w:lineRule'), 'auto')
        pPr.append(spacing)

    @staticmethod
    def _has_style(doc, style_name: str) -> bool:
        """检查文档中是否存在指定样式"""
        try:
            doc.styles[style_name]
            return True
        except KeyError:
            return False

    @staticmethod
    def _ensure_element(parent, tag: str, first: bool = False, use_inner: bool = False):
        """确保父元素中存在指定子元素，不存在则创建"""
        child = parent.find(qn(tag))
        if child is None:
            child = OxmlElement(tag)
            if first:
                parent.insert(0, child)
            else:
                parent.append(child)
        return child

    def _log(self, message: str, level: str = "info"):
        if self.verbose or level == "error":
            print(f"[{level.upper()}] {message}")
