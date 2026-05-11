"""Word 导出器 — HTML → python-docx

将 HtmlRenderer 生成的语义化 HTML 转换为 Word 文档。
通过 BeautifulSoup4 解析 HTML DOM，StyleMapper 映射 CSS class，python-docx 构建输出。
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import date
import re
import copy
import base64
import tempfile
import os

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None  # type: ignore
    HAS_REQUESTS = False

from bs4 import BeautifulSoup, Tag, NavigableString
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from parser import MarkdownParser
from html_engine.renderer import HtmlRenderer
from html_engine.context import RenderContext
from html_engine.themes import ThemeRegistry
from flowchart import FlowchartProcessor
from .style_mapper import StyleMapper, ALIGN_MAP


# — 表格常量 —
TABLE_FONT_WEST = 'Consolas'
TABLE_FONT_EAST = 'Microsoft YaHei'
TABLE_FONT_SIZE = Pt(10)
TABLE_HEADER_BG = 'D9D9D9'
TABLE_BORDER_COLOR = '808080'
TABLE_BORDER_SIZE = 4
TABLE_CELL_MARGIN = 40
TABLE_TOTAL_WIDTH_CM = 16


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

        # 脚注
        self._footnote_counter = 0

        # HTML 渲染器
        self._html_renderer = HtmlRenderer(flowchart_processor=self._flowchart)

        # 模板目录
        tmpl_dir = Path(__file__).parent.parent.parent
        self._template_dir = tmpl_dir

    # ============================================================
    # 公开接口
    # ============================================================

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """将 AST 转换为 Word 文档"""
        output_file = Path(output_path)

        # 1. 渲染 HTML
        context = RenderContext(
            title=self.doc_title or output_file.stem,
            number=self.doc_number,
            version=self.doc_version,
            department=self.doc_department,
            company=self.doc_company,
            date=date.today().strftime('%Y.%m.%d'),
        )
        self._html_renderer.render(ast, context)

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
            page_break_p = OxmlElement('w:p')
            pb_r = OxmlElement('w:r')
            br = OxmlElement('w:br')
            br.set(qn('w:type'), 'page')
            pb_r.append(br)
            page_break_p.append(pb_r)
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

        # 6. 输出
        output_file.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_file))
        self._log(f"Word文档已生成: {output_path}")
        return True

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
            return doc

        doc = Document()
        style = doc.styles['Normal']
        style.font.name = self.font_name
        style.font.size = self.font_size
        style.element.rPr.rFonts.set(qn('w:eastAsia'), self.font_name)
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
                self._add_table(element, doc)
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
        """添加段落（含内联格式）"""
        style_name = StyleMapper.get_paragraph_style(tag)
        para = doc.add_paragraph(style=style_name) if self._has_style(doc, style_name) else doc.add_paragraph()
        self._process_inline_runs(para, tag)
        # 对齐
        align = StyleMapper.get_alignment(tag)
        if align is not None:
            para.alignment = align

    def _add_paragraph_text(self, doc: Document, text: str):
        """添加纯文本段落（兜底）"""
        para = doc.add_paragraph()
        para.add_run(text)

    # 无序列表多层符号
    _BULLET_CHARS = ['•', '◦', '▪', '▸']

    def _add_list(self, tag: Tag, doc: Document, level: int = 0):
        """添加列表（ul/ol），使用 Unicode 项目符号/编号 + 悬挂缩进"""
        is_ordered = tag.name == 'ol'
        # 每级缩进 0.75cm，悬挂缩进 0.4cm（子弹/编号在文字左侧）
        left = Cm(0.75 + level * 0.75)
        hang = Cm(-0.4)
        counter = 1

        for li in tag.find_all('li', recursive=False):
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = left
            para.paragraph_format.first_line_indent = hang
            # 无段间距
            para.paragraph_format.space_before = Pt(0)
            para.paragraph_format.space_after = Pt(0)

            # 添加项目符号或编号
            task_checked = None
            for child in li.children:
                if isinstance(child, NavigableString):
                    continue
                if child.name == 'input':
                    task_checked = child.get('checked')
                    break

            if task_checked is not None:
                prefix = '☑ ' if task_checked else '☐ '
            elif is_ordered:
                prefix = f'{counter}、'
                counter += 1
            else:
                prefix = self._BULLET_CHARS[level % len(self._BULLET_CHARS)]

            para.add_run(prefix + ' ')

            # 渲染 li 的直接子元素（跳过嵌套列表和已处理的 input）
            for child in li.children:
                if isinstance(child, NavigableString):
                    t = child.strip()
                    if t:
                        para.add_run(t)
                elif child.name in ('ul', 'ol'):
                    continue
                elif child.name == 'input':
                    continue  # 已作为 prefix 处理
                else:
                    self._render_single_inline(para, child)

            # 如果段落仅含前缀无实质内容（纯嵌套列表情况），移除
            content_runs = [r for r in para.runs if r.text.strip()]
            if len(content_runs) == 1 and content_runs[0].text.strip() in (*self._BULLET_CHARS, '☑', '☐') or \
               (len(content_runs) == 1 and content_runs[0].text.strip().endswith('、')):
                body = para._p.getparent()
                if body is not None:
                    body.remove(para._p)

            # 处理嵌套子列表
            for nested in li.find_all(['ul', 'ol'], recursive=False):
                self._add_list(nested, doc, level + 1)

    def _add_table(self, tag: Tag, doc: Document):
        """添加表格"""
        # 收集所有行
        rows_data = []
        has_thead = tag.find('thead') is not None
        header_rows = []

        # 处理 thead
        thead = tag.find('thead')
        if thead:
            for tr in thead.find_all('tr', recursive=False):
                cells = list(StyleMapper.cell_collector(tr, True))
                if cells:
                    header_rows.append(cells)

        # 处理 tbody
        tbody = tag.find('tbody') or tag
        body_rows = []
        for tr in tbody.find_all('tr', recursive=False):
            # 跳过 thead 中的行
            if has_thead and tr.parent and tr.parent.name == 'thead':
                continue
            is_header = (not has_thead and len(body_rows) == 0 and
                         (tr.find('th') or StyleMapper.is_thead_row(tr)))
            cells = list(StyleMapper.cell_collector(tr, is_header if not has_thead else False))
            if cells:
                body_rows.append(cells)

        all_rows = header_rows + body_rows
        if not all_rows:
            return

        col_count = max(len(r) for r in all_rows)

        # 添加表格
        table = doc.add_table(rows=len(all_rows), cols=col_count)
        table_style_name = StyleMapper.get_table_style(tag)
        if self._has_style(doc, table_style_name):
            table.style = doc.styles[table_style_name]

        # 设置边框和宽度
        self._set_table_borders(table)

        # 填充数据
        for row_idx, row_data in enumerate(all_rows):
            row = table.rows[row_idx]
            is_header_row = row_idx < len(header_rows)
            if not has_thead and row_idx == 0:
                # 判断首行是否为表头（基于 th 标签或样式）
                first_tag = tag.find_all('tr')[row_idx] if row_idx < len(tag.find_all('tr')) else None
                is_header_row = bool(first_tag and first_tag.find('th'))

            for col_idx, cell_data in enumerate(row_data):
                if col_idx >= col_count:
                    break
                cell = row.cells[col_idx]
                self._format_cell_html(cell, cell_data, is_header_row)

    def _format_cell_html(self, cell, cell_data: dict, is_header: bool):
        """格式化单个表格单元格"""
        text = cell_data.get('text', '')
        align_cls = cell_data.get('align')

        tc = cell._tc
        tcPr = self._ensure_element(tc, 'w:tcPr', first=True)

        # 边距
        old_mar = tcPr.find(qn('w:tcMar'))
        if old_mar is not None:
            tcPr.remove(old_mar)
        tcMar = OxmlElement('w:tcMar')
        for side, val in [('top', TABLE_CELL_MARGIN), ('left', TABLE_CELL_MARGIN + 20),
                          ('bottom', TABLE_CELL_MARGIN), ('right', TABLE_CELL_MARGIN + 20)]:
            m = OxmlElement(f'w:{side}')
            m.set(qn('w:w'), str(val))
            m.set(qn('w:type'), 'dxa')
            tcMar.append(m)
        tcPr.append(tcMar)

        # 垂直居中
        vAlign = self._ensure_element(tcPr, 'w:vAlign')
        vAlign.set(qn('w:val'), 'center')

        # 表头灰底
        if is_header:
            shd = self._ensure_element(tcPr, 'w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), TABLE_HEADER_BG)

        # 写入文本
        para = cell.paragraphs[0]
        para.clear()
        run = para.add_run(text)
        run.font.name = TABLE_FONT_WEST
        run.font.size = TABLE_FONT_SIZE
        run.element.rPr.rFonts.set(qn('w:eastAsia'), TABLE_FONT_EAST)
        if is_header:
            run.font.bold = True

        # 对齐
        if is_header or align_cls == 'align-center':
            align = WD_ALIGN_PARAGRAPH.CENTER
        elif align_cls == 'align-right':
            align = WD_ALIGN_PARAGRAPH.RIGHT
        else:
            align = WD_ALIGN_PARAGRAPH.LEFT

        for p in cell.paragraphs:
            pPr = self._ensure_element(p._p, 'w:pPr', first=True)

            # 零缩进
            ind = pPr.find(qn('w:ind'))
            if ind is not None:
                pPr.remove(ind)
            ind = OxmlElement('w:ind')
            for attr in ['left', 'leftChars', 'right', 'rightChars', 'firstLine', 'firstLineChars', 'hanging', 'hangingChars']:
                ind.set(qn(f'w:{attr}'), '0')
            pPr.append(ind)

            # 段间距
            old_sp = pPr.find(qn('w:spacing'))
            if old_sp is not None:
                pPr.remove(old_sp)

            # 对齐
            jc = pPr.find(qn('w:jc'))
            if jc is None:
                jc = OxmlElement('w:jc')
                pPr.append(jc)
            jc.set(qn('w:val'), {WD_ALIGN_PARAGRAPH.CENTER: 'center',
                                WD_ALIGN_PARAGRAPH.RIGHT: 'right',
                                WD_ALIGN_PARAGRAPH.LEFT: 'left'}.get(align, 'left'))

            for r in p.runs:
                r.font.name = TABLE_FONT_WEST
                r.font.size = TABLE_FONT_SIZE
                r.element.rPr.rFonts.set(qn('w:eastAsia'), TABLE_FONT_EAST)
                if is_header:
                    r.font.bold = True

    def _add_code_block(self, tag: Tag, doc: Document):
        """添加代码块"""
        code_tag = tag.find('code') if tag.name != 'code' else tag
        text = code_tag.get_text() if code_tag else tag.get_text()

        for line in text.split('\n'):
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.5)
            run = para.add_run(line)
            run.font.name = 'Courier New'
            run.font.size = Pt(10)
            # 灰底
            shd = self._ensure_element(run._r, 'w:rPr', first=True, use_inner=True)
            shd_el = OxmlElement('w:shd')
            shd_el.set(qn('w:val'), 'clear')
            shd_el.set(qn('w:color'), 'auto')
            shd_el.set(qn('w:fill'), 'F5F5F5')
            shd.insert(0, shd_el)

    def _add_blockquote(self, tag: Tag, doc: Document):
        """添加引用块，保留内联格式"""
        for child in tag.children:
            if isinstance(child, NavigableString):
                continue
            name = child.name if hasattr(child, 'name') else None
            if name is None:
                continue

            # 为引用块内元素统一添加缩进和左边框
            if name == 'p':
                para = doc.add_paragraph()
                self._process_inline_runs(para, child)
                self._style_blockquote_para(para)
            elif name in ('ul', 'ol'):
                self._add_list(child, doc)
            elif name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self._add_heading(child, doc)
            elif name == 'table':
                self._add_table(child, doc)
            elif name == 'div' and 'code-block' in child.get('class', []):
                self._add_code_block(child, doc)
            elif name == 'pre':
                self._add_code_block(child, doc)
            elif name == 'blockquote':
                self._add_blockquote(child, doc)
            else:
                text = child.get_text(strip=True)
                if text:
                    para = doc.add_paragraph()
                    para.add_run(text)
                    self._style_blockquote_para(para)

    def _style_blockquote_para(self, para):
        """为引用块段落添加缩进和左边框"""
        para.paragraph_format.left_indent = Cm(1)
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

    # 图片最大宽度（内嵌 DPI 未知时回退到 96dpi，同 CSS 规范）
    # A4=21cm，模板 margin 约 2cm → 内容区 ≈ 17cm，图片取 70% 留白
    _MAX_IMAGE_W_EMU = int(12 * 360000)  # 12cm
    _IMG_DPI_FALLBACK = 96

    def _add_image(self, tag: Tag, doc: Document):
        """添加图片，等比缩放适配页面宽度（与 PDF max-width:100% 行为一致）"""
        img_tag = tag.find('img')
        if not img_tag:
            return
        src = img_tag.get('src', '')
        alt = img_tag.get('alt', '')
        caption = tag.find('figcaption')
        caption_text = caption.get_text() if caption else alt

        if not src:
            if caption_text:
                para = doc.add_paragraph()
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = para.add_run(f'[图片: {caption_text}]')
                run.font.italic = True
            return

        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        try:
            img_w, img_h = (None, None)
            image_arg = src

            if src.startswith('data:'):
                header, encoded = src.split(',', 1)
                ext = header.split(';')[0].split('/')[-1] if 'image/' in header else 'png'
                data = base64.b64decode(encoded)
                img_w, img_h = self._get_image_physical_size(data)
                with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as f:
                    f.write(data)
                    image_arg = f.name
            elif src.startswith(('http://', 'https://')):
                try:
                    resp = requests.get(src, timeout=10)
                    resp.raise_for_status()
                    img_w, img_h = self._get_image_physical_size(resp.content)
                except Exception:
                    pass
                image_arg = src
            elif Path(src).exists():
                img_w, img_h = self._get_image_physical_size_file(src)
                image_arg = src
            else:
                run = para.add_run(f'[图片: {caption_text or src}]')
                run.font.italic = True
                return

            # 仅当宽度超过内容区时等比缩小，否则保持原始大小（等同于 PDF max-width:100%）
            if img_w and img_h:
                if img_w > self._MAX_IMAGE_W_EMU:
                    ratio = self._MAX_IMAGE_W_EMU / img_w
                    img_w = self._MAX_IMAGE_W_EMU
                    img_h = int(img_h * ratio)
                para.add_run().add_picture(image_arg, width=img_w, height=img_h)
            else:
                para.add_run().add_picture(image_arg, width=self._MAX_IMAGE_W_EMU)

            # 清理临时文件
            if src.startswith('data:') and image_arg != src:
                try:
                    os.unlink(image_arg)
                except OSError:
                    pass
        except Exception:
            run = para.add_run(f'[图片: {caption_text or src}]')
            run.font.italic = True

        if caption_text:
            cap_para = doc.add_paragraph()
            cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap_run = cap_para.add_run(f'图 {caption_text}')
            cap_run.font.size = Pt(9)
            cap_run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    @classmethod
    def _get_image_physical_size(cls, data: bytes):
        """从图片字节数据获取物理尺寸（EMU），基于内嵌 DPI，与 CSS 渲染行为一致"""
        from io import BytesIO
        from PIL import Image
        img = Image.open(BytesIO(data))
        dpi = img.info.get('dpi', (cls._IMG_DPI_FALLBACK, cls._IMG_DPI_FALLBACK))
        dpi_x = dpi[0] if dpi[0] and dpi[0] > 0 else cls._IMG_DPI_FALLBACK
        dpi_y = dpi[1] if dpi[1] and dpi[1] > 0 else cls._IMG_DPI_FALLBACK
        w_emu = int(img.width / dpi_x * 914400)
        h_emu = int(img.height / dpi_y * 914400)
        return w_emu, h_emu

    @classmethod
    def _get_image_physical_size_file(cls, path: str):
        """从文件获取图片物理尺寸（EMU）"""
        with open(path, 'rb') as f:
            return cls._get_image_physical_size(f.read())

    def _add_flowchart_element(self, tag: Tag, doc: Document):
        """添加流程图（已渲染为图片）"""
        img_tag = tag.find('img')
        if img_tag:
            self._add_image(tag, doc)

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

    def _add_definition_list(self, tag: Tag, doc: Document):
        """添加定义列表"""
        for child in tag.children:
            if isinstance(child, NavigableString):
                continue
            if child.name == 'dt':
                para = doc.add_paragraph()
                run = para.add_run(child.get_text(strip=False).rstrip('；').rstrip(';'))
                run.font.bold = True
            elif child.name == 'dd':
                para = doc.add_paragraph()
                para.paragraph_format.left_indent = Cm(0.85)
                para.add_run(child.get_text(strip=False))

    def _add_math_block(self, tag: Tag, doc: Document):
        """添加数学公式块"""
        text = tag.get_text(strip=False)
        # 去除 \[ \] 定界符
        text = text.strip()
        if text.startswith('\\['):
            text = text[2:]
        if text.endswith('\\]'):
            text = text[:-2]
        text = text.strip()
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # 灰底公式框
        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F5F5F5')
        pPr.append(shd)
        run = para.add_run(text)
        run.font.name = 'Cambria Math'
        run.font.italic = True
        run.font.size = Pt(11)

    # ============================================================
    # 内联格式处理
    # ============================================================

    def _process_inline_runs(self, para, tag: Tag):
        """递归处理 HTML 内联元素，生成 Word runs"""
        self._render_inline_children(para, tag)

    def _render_inline_children(self, para, element):
        """递归渲染内联子元素"""
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip() or text == ' ':
                    para.add_run(text)
            else:
                self._render_single_inline(para, child)

    def _render_single_inline(self, para, element):
        """渲染单个内联元素，支持嵌套格式叠加（如 <em><strong>）"""
        name = element.name
        if name is None:
            return

        if name in ('strong', 'em', 'del', 'ins'):
            self._render_nested_format(para, element, name)
        elif name == 'code':
            run = para.add_run(element.get_text())
            run.font.name = 'Courier New'
            run.font.size = Pt(10)
            shd = self._ensure_element(run._r, 'w:rPr', first=True, use_inner=True)
            shd_el = OxmlElement('w:shd')
            shd_el.set(qn('w:val'), 'clear')
            shd_el.set(qn('w:color'), 'auto')
            shd_el.set(qn('w:fill'), 'F0F0F0')
            shd.insert(0, shd_el)
        elif name == 'a':
            text = element.get_text()
            href = element.get('href', '')
            if href:
                self._add_hyperlink(para, text, href)
            else:
                para.add_run(text)
        elif name == 'kbd':
            run = para.add_run(element.get_text())
            run.font.name = 'Courier New'
            run.font.size = Pt(9)
        elif name == 'sub':
            run = para.add_run(element.get_text())
            run.font.subscript = True
        elif name == 'sup':
            run = para.add_run(element.get_text())
            run.font.superscript = True
        elif name == 'mark':
            run = para.add_run(element.get_text())
            shd = self._ensure_element(run._r, 'w:rPr', first=True, use_inner=True)
            shd_el = OxmlElement('w:shd')
            shd_el.set(qn('w:val'), 'clear')
            shd_el.set(qn('w:color'), 'auto')
            shd_el.set(qn('w:fill'), 'FFFF00')
            shd.insert(0, shd_el)
        elif name == 'br':
            para.add_run('\n')
        elif name == 'img':
            alt = element.get('alt', '[图片]')
            para.add_run(f'[图片: {alt}]')
        elif name == 'span':
            classes = element.get('class', [])
            if 'math' in classes:
                # 内联公式：去除 \( \) 定界符，用 Cambria Math 斜体
                text = element.get_text()
                text = text.strip()
                if text.startswith('\\('):
                    text = text[2:]
                if text.endswith('\\)'):
                    text = text[:-2]
                run = para.add_run(text.strip())
                run.font.name = 'Cambria Math'
                run.font.italic = True
                run.font.size = Pt(11)
            else:
                self._render_inline_children(para, element)
        elif name == 'input':
            checked = element.get('checked')
            para.add_run('☑ ' if checked is not None else '☐ ')
        else:
            t = element.get_text()
            if t:
                para.add_run(t)

    _FORMAT_ATTR = {'strong': 'bold', 'em': 'italic', 'del': 'strike', 'ins': 'underline'}

    def _render_nested_format(self, para, element, fmt_name):
        """递归渲染 strong/em/del/ins，支持嵌套子元素叠加格式"""
        attr = self._FORMAT_ATTR[fmt_name]
        for child in element.children:
            if isinstance(child, NavigableString):
                t = str(child)
                if t.strip() or t == ' ':
                    run = para.add_run(t)
                    setattr(run.font, attr, True)
            elif child.name in self._FORMAT_ATTR:
                self._render_nested_format(para, child, child.name)
                if para.runs:
                    setattr(para.runs[-1].font, attr, True)
            else:
                self._render_single_inline(para, child)
                if para.runs:
                    setattr(para.runs[-1].font, attr, True)

    @staticmethod
    def _add_hyperlink(para, text: str, url: str):
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
        """在正文开头插入 Word 原生 TOC 字段（含目录标题和分页符）"""
        body = doc.element.body

        # 目录标题
        title_para = OxmlElement('w:p')
        title_pPr = OxmlElement('w:pPr')
        title_pStyle = OxmlElement('w:pStyle')
        title_pStyle.set(qn('w:val'), 'Heading1')
        title_pPr.append(title_pStyle)
        title_para.append(title_pPr)
        title_run = OxmlElement('w:r')
        title_t = OxmlElement('w:t')
        title_t.set(qn('xml:space'), 'preserve')
        title_t.text = '目录'
        title_run.append(title_t)
        title_para.append(title_run)
        body.insert(0, title_para)

        # TOC 字段
        toc_para = OxmlElement('w:p')
        toc_r = OxmlElement('w:r')
        fldChar_begin = OxmlElement('w:fldChar')
        fldChar_begin.set(qn('w:fldCharType'), 'begin')
        toc_r.append(fldChar_begin)
        toc_para.append(toc_r)

        instr_r = OxmlElement('w:r')
        instr = OxmlElement('w:instrText')
        instr.set(qn('xml:space'), 'preserve')
        instr.text = 'TOC \\o "1-2" \\h \\z \\u'
        instr_r.append(instr)
        toc_para.append(instr_r)

        sep_r = OxmlElement('w:r')
        fldChar_sep = OxmlElement('w:fldChar')
        fldChar_sep.set(qn('w:fldCharType'), 'separate')
        sep_r.append(fldChar_sep)
        toc_para.append(sep_r)

        end_r = OxmlElement('w:r')
        fldChar_end = OxmlElement('w:fldChar')
        fldChar_end.set(qn('w:fldCharType'), 'end')
        end_r.append(fldChar_end)
        toc_para.append(end_r)
        body.insert(1, toc_para)

        # 分页符
        page_break_para = OxmlElement('w:p')
        pb_r = OxmlElement('w:r')
        br = OxmlElement('w:br')
        br.set(qn('w:type'), 'page')
        pb_r.append(br)
        page_break_para.append(pb_r)
        body.insert(2, page_break_para)

        # 自动更新 TOC
        settings = doc.settings.element
        updateFields = settings.find(qn('w:updateFields'))
        if updateFields is None:
            updateFields = OxmlElement('w:updateFields')
            settings.append(updateFields)
        updateFields.set(qn('w:val'), 'true')

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
        """添加修订记录表（紧接 TOC 分页符之后）"""
        if not revision_html:
            return

        soup = BeautifulSoup(revision_html, 'html.parser')
        heading_tag = soup.find('h2')
        table_tag = soup.find('table')

        if not table_tag:
            return

        # 标题
        if heading_tag:
            self._add_heading(heading_tag, doc)

        # 表格
        self._add_table(table_tag, doc)

        # 尾部分页符（与正文分隔）
        pb_para = doc.add_paragraph()
        pb_run = pb_para.add_run()
        br = OxmlElement('w:br')
        br.set(qn('w:type'), 'page')
        pb_run._r.append(br)

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

    def _set_table_borders(self, table):
        """设置表格边框（全边框 0.5pt 灰色）"""
        tbl = table._tbl
        tblPr = self._ensure_element(tbl, 'w:tblPr', first=True)

        tblBorders = tblPr.find(qn('w:tblBorders'))
        if tblBorders is not None:
            tblPr.remove(tblBorders)

        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), str(TABLE_BORDER_SIZE))
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), TABLE_BORDER_COLOR)
            tblBorders.append(border)
        tblPr.append(tblBorders)

        # 表格宽度
        tblW = tblPr.find(qn('w:tblW'))
        if tblW is None:
            tblW = OxmlElement('w:tblW')
            tblPr.append(tblW)
        tblW.set(qn('w:w'), '9000')
        tblW.set(qn('w:type'), 'dxa')

    def _log(self, message: str, level: str = "info"):
        if self.verbose or level == "error":
            print(f"[{level.upper()}] {message}")
