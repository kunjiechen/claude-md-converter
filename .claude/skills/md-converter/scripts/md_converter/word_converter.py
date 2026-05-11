"""
Word文档转换器
将Markdown AST转换为Word文档
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
import tempfile
import copy
import re
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from .converter import BaseConverter
from .parser import MarkdownParser
from .flowchart_renderer import FlowchartProcessor


class WordConverter(BaseConverter):
    """Word文档转换器"""

    # 模板样式映射表：markdown元素 → Word样式名
    STYLE_MAP = {
        'paragraph': 'Normal',
        'list_bullet': 'List Bullet',
        'list_number': 'List Number',
        'table': 'Table Grid',
        'blockquote': 'Normal',       # 引用段落用Normal+左边框
        'code_block': 'Normal',       # 代码块用Normal+等宽字体
        'math_block': 'Normal',       # 公式块用Normal+居中
        'definition_term': 'Normal',  # 定义术语用Normal+粗体
        'definition_desc': 'Normal',  # 定义描述用Normal+缩进
        'footnote': 'Normal',         # 脚注用Normal+小字号
    }

    def __init__(self, **options):
        """
        初始化Word转换器

        Args:
            **options: 转换选项
                - template: Word模板文件路径(.docx/.dotx)
                - output_dir: 输出目录
                - font: 默认字体（仅无模板时生效）
                - font_size: 默认字号（仅无模板时生效）
                - flowchart_enabled: 是否启用流程图
                - doc_title/doc_number/doc_version/doc_department/doc_company: 页眉动态字段
        """
        super().__init__(**options)
        self.font = options.get('font', '宋体')
        self.font_size = options.get('font_size', 12)
        self.doc = None
        self.input_dir = None  # 输入文件所在目录，用于解析相对路径
        self._footnote_counter = 0  # 脚注计数器
        self._using_template = False  # 是否使用模板
        self._template_revision_table = None  # 模板中的修订记录表（XML元素）
        self._toc_inserted = False  # TOC是否已插入

        # 流程图处理器
        self.flowchart_enabled = options.get('flowchart_enabled', True)
        self.flowchart_processor = FlowchartProcessor(**options) if self.flowchart_enabled else None
        self.flowchart_counter = 0

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """
        将AST转换为Word文档，包含TOC和修订记录的智能处理。
        """
        try:
            self.doc = self._create_document()
            self._footnote_counter = 0
            self._toc_inserted = False
            self._revision_from_md = False

            # 第一遍：扫描识别TOC表和修订记录表
            toc_table_idx = -1
            revision_table_idx = -1

            for i, node in enumerate(ast):
                if node.get('type') == 'table':
                    if toc_table_idx < 0 and self._is_toc_table_node(node):
                        toc_table_idx = i
                    elif revision_table_idx < 0 and self._is_revision_table_node(node):
                        revision_table_idx = i

            # 第二遍：处理内容节点，跳过TOC表和修订表
            revision_node = None
            for i, node in enumerate(ast):
                if i == toc_table_idx:
                    continue
                if i == revision_table_idx:
                    revision_node = node
                    self._revision_from_md = True
                    continue
                self._process_node(node)

            # 后处理：先插入TOC到开头，再将修订表插入TOC下一页
            self._insert_toc_field(ast)
            if revision_node is not None:
                self._add_revision_table(revision_node, after_toc=True)
            elif self._template_revision_table is not None:
                self._insert_template_revision_table(after_toc=True)

            self.doc.save(output_path)
            self.log(f"Word文档已生成: {output_path}")
            return True

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            import traceback
            traceback.print_exc()
            return False

    def convert_file(self, input_path: str, output_path: str) -> bool:
        """
        转换Markdown文件为Word文档

        Args:
            input_path: 输入Markdown文件路径
            output_path: 输出Word文件路径

        Returns:
            转换是否成功
        """
        try:
            # 验证输入文件
            self.validate_input(input_path)

            # 记录输入文件目录，用于解析相对路径
            self.input_dir = Path(input_path).parent

            # 解析Markdown
            parser = MarkdownParser()
            ast = parser.parse_file(input_path)

            # 转换为Word
            return self.convert(ast, output_path)

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def _resolve_template_path(self) -> Optional[str]:
        """
        三级优先级解析模板路径：
          1. CLI/代码明确指定的 template_path
          2. 当前工作目录下的 templates/ 目录中第一个 .docx 文件
          3. 内置默认模板（G-C045）

        Returns:
            模板文件路径，找不到返回 None
        """
        # 1) 显式指定
        if self.template_path:
            p = Path(self.template_path)
            if p.exists():
                return str(p.resolve())
            # 也尝试在 templates/ 下找
            alt = Path('templates') / self.template_path
            if alt.exists():
                return str(alt.resolve())

        # 2) templates/ 目录下自动选用
        templates_dir = Path('templates')
        if templates_dir.is_dir():
            for f in sorted(templates_dir.glob('*.docx')):
                return str(f.resolve())

        # 3) 内置默认模板
        builtin = Path(__file__).parent / 'default_template.docx'
        if builtin.exists():
            return str(builtin)

        return None

    def _create_document(self):
        """
        创建Word文档，优先使用模板。
        模板仅提供样式、页眉页脚、页面设置和修订记录表结构，正文从md生成。
        """
        resolved = self._resolve_template_path()

        if resolved:
            self.doc = Document(resolved)
            self._using_template = True
            self._replace_header_fields()
            self._save_template_revision_table()
            self._clear_template_body()
            self.log(f"已加载模板: {resolved}")
        else:
            self.doc = Document()
            self._using_template = False
            style = self.doc.styles['Normal']
            font = style.font
            font.name = self.font
            font.size = Pt(self.font_size)
            style.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

        return self.doc

    def _save_template_revision_table(self):
        """保存模板中的修订记录表结构，用于后续填充或直接输出"""
        for table in self.doc.tables:
            if self._is_revision_table(table):
                self._template_revision_table = copy.deepcopy(table._tbl)
                break

    def _replace_header_fields(self):
        """
        替换模板页眉中的占位字段。
        扫描页眉中所有段落，查找已知模式并替换为对应值。
        支持的占位模式：
          - 制定部门：XXX → 替换部门
          - 公司名称（如"上海金脉电子科技有限公司"）→ 替换公司名
          - 文件编号：XXX → 替换编号
          - 制定日期：XXX / 修改日期：XXX → 替换日期
          - 文档标题（如"软件模块命名规范"）→ 替换标题
          - 版本：XXX → 替换版本
        """
        from datetime import date

        replacements = {}
        if self.doc_company:
            replacements['company'] = self.doc_company
        if self.doc_number:
            replacements['number'] = self.doc_number
        if self.doc_version:
            replacements['version'] = self.doc_version
        if self.doc_department:
            replacements['department'] = self.doc_department
        if self.doc_title:
            replacements['title'] = self.doc_title
        # 日期默认使用今天
        replacements['date'] = date.today().strftime('%Y.%m.%d')

        if not replacements:
            return

        for section in self.doc.sections:
            self._replace_in_header(section.header, replacements)
            # 第一节的页眉通常也链接到后续节
            if section.different_first_page_header_footer:
                self._replace_in_header(section.first_page_header, replacements)

    def _replace_in_header(self, header, replacements: dict):
        """在页眉中执行文本替换，处理跨run的文本"""
        if header is None or header.is_linked_to_previous:
            return

        all_paragraphs = list(header.paragraphs)
        for table in header.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_paragraphs.extend(cell.paragraphs)

        for para in all_paragraphs:
            runs = para.runs
            if not runs:
                continue

            # 收集所有run的文本和对应的run对象
            full_text = ''.join(r.text for r in runs)

            # 执行替换
            new_text = full_text
            if 'department' in replacements:
                new_text = re.sub(r'制定部门[：:]\s*\S+', f'制定部门：{replacements["department"]}', new_text)
            if 'number' in replacements:
                new_text = re.sub(r'文件编号[：:]\s*\S+', f'文件编号：{replacements["number"]}', new_text)
            if 'date' in replacements:
                new_text = re.sub(r'制定日期[：:]\s*\S+', f'制定日期：{replacements["date"]}', new_text)
                new_text = re.sub(r'修改日期[：:]\s*\S+', f'修改日期：{replacements["date"]}', new_text)
            if 'version' in replacements:
                new_text = re.sub(r'版本[：:]\s*\S+', f'版本：{replacements["version"]}', new_text)
            if 'company' in replacements:
                new_text = new_text.replace('上海金脉电子科技有限公司', replacements['company'])
            if 'title' in replacements:
                new_text = new_text.replace('软件模块命名规范', replacements['title'])

            if new_text == full_text:
                continue

            # 将修改后的文本分配回各run（保持第一个run承载内容，其余清空）
            runs[0].text = new_text
            for r in runs[1:]:
                r.text = ''

    def _clear_template_body(self):
        """清除模板正文内容，仅保留样式、页眉页脚、页面设置"""
        body = self.doc.element.body
        to_remove = []
        for child in body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag != 'sectPr':
                to_remove.append(child)
        for child in to_remove:
            body.remove(child)

    # ---------- TOC 检测与生成 ----------

    def _is_toc_table_node(self, node: Dict[str, Any]) -> bool:
        """检测AST节点是否为目录表"""
        children = node.get('children', [])
        if not children:
            return False
        # 检查第一行第一个单元格是否包含"目录"
        first_row = children[0]
        first_cell = (first_row.get('children', []) or [None])[0]
        if first_cell:
            text = (first_cell.get('content', '') or '').strip()
            if '目录' in text:
                return True
        # 检查是否有多行以数字结尾的条目（典型的TOC格式）
        toc_pattern_count = 0
        for row in children[1:]:
            cells = row.get('children', [])
            if cells:
                last_text = (cells[-1].get('content', '') or '').strip()
                if last_text.isdigit() and 0 < int(last_text) < 1000:
                    toc_pattern_count += 1
        return toc_pattern_count >= 3

    def _insert_toc_field(self, ast: List[Dict[str, Any]] = None):
        """插入Word原生TOC域，基于Heading 1-4，支持页码、超链接、打开自动更新"""
        if self._toc_inserted:
            return

        body = self.doc.element.body

        # 目录标题
        toc_title = OxmlElement('w:p')
        toc_pPr = OxmlElement('w:pPr')
        toc_pStyle = OxmlElement('w:pStyle')
        toc_pStyle.set(qn('w:val'), 'Title')
        toc_pPr.append(toc_pStyle)
        toc_title.append(toc_pPr)
        toc_r = OxmlElement('w:r')
        toc_t = OxmlElement('w:t')
        toc_t.text = '目录'
        toc_t.set(qn('xml:space'), 'preserve')
        toc_r.append(toc_t)
        toc_title.append(toc_r)

        # TOC域: TOC \o "1-4" \h \z \u
        #   \o "1-4" — 使用Heading 1-4层级
        #   \h — 目录条目为超链接，可点击跳转
        #   \z — Web视图中隐藏制表符前导符和页码
        #   \u — 使用段落的直接大纲级别
        toc_p = OxmlElement('w:p')
        toc_r1 = OxmlElement('w:r')
        fld_begin = OxmlElement('w:fldChar')
        fld_begin.set(qn('w:fldCharType'), 'begin')
        toc_r1.append(fld_begin)
        toc_p.append(toc_r1)

        toc_r2 = OxmlElement('w:r')
        instr = OxmlElement('w:instrText')
        instr.set(qn('xml:space'), 'preserve')
        instr.text = ' TOC \\o "1-2" \\h \\z \\u '
        toc_r2.append(instr)
        toc_p.append(toc_r2)

        toc_r3 = OxmlElement('w:r')
        fld_sep = OxmlElement('w:fldChar')
        fld_sep.set(qn('w:fldCharType'), 'separate')
        toc_r3.append(fld_sep)
        toc_p.append(toc_r3)

        # 占位文本（字段未更新时显示）
        toc_r4 = OxmlElement('w:r')
        toc_t2 = OxmlElement('w:t')
        toc_t2.text = '（请右键点击此处，选择"更新域"生成目录；若Word设置了打开时自动更新域，则会自动生成）'
        toc_r4.append(toc_t2)
        toc_p.append(toc_r4)

        toc_r5 = OxmlElement('w:r')
        fld_end = OxmlElement('w:fldChar')
        fld_end.set(qn('w:fldCharType'), 'end')
        toc_r5.append(fld_end)
        toc_p.append(toc_r5)

        # 插入到body最前面
        body.insert(0, toc_title)
        body.insert(1, toc_p)

        # 分页符
        page_break = OxmlElement('w:p')
        pb_r = OxmlElement('w:r')
        br = OxmlElement('w:br')
        br.set(qn('w:type'), 'page')
        pb_r.append(br)
        page_break.append(pb_r)
        body.insert(2, page_break)

        # 设置文档打开时自动更新域（TOC等）
        settings_elem = self.doc.settings.element
        existing = settings_elem.find(qn('w:updateFields'))
        if existing is None:
            update_fields = OxmlElement('w:updateFields')
            update_fields.set(qn('w:val'), 'true')
            settings_elem.append(update_fields)

        self._toc_inserted = True

    # ---------- 修订记录表检测与生成 ----------

    REVISION_HEADER_KEYWORDS = ['版次', '修订人', '修订日期', '修订内容', '修订原因', '修订描述', '备注']

    def _is_revision_table(self, table) -> bool:
        """检测python-docx表格是否为修订记录表"""
        if len(table.rows) == 0:
            return False
        header_texts = set()
        for row in table.rows[:2]:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    header_texts.add(text)
        if not header_texts:
            return False
        hits = sum(1 for kw in self.REVISION_HEADER_KEYWORDS if kw in header_texts)
        if hits >= 2:
            return True
        # 宽松匹配：拼接所有表头文本，检查是否包含"修订"+"版"或"修订"+"日期"
        all_text = ' '.join(header_texts)
        if '修订' in all_text and ('版' in all_text or '日期' in all_text):
            return True
        return False

    def _is_revision_table_node(self, node: Dict[str, Any]) -> bool:
        """检测AST表格节点是否为修订记录表"""
        children = node.get('children', [])
        if len(children) < 2:
            return False
        header_texts = set()
        for row in children[:2]:
            for cell in row.get('children', []):
                text = (cell.get('content', '') or '').strip()
                if text:
                    header_texts.add(text)
        if not header_texts:
            return False
        hits = sum(1 for kw in self.REVISION_HEADER_KEYWORDS if kw in header_texts)
        if hits >= 2:
            return True
        all_text = ' '.join(header_texts)
        if '修订' in all_text and ('版' in all_text or '日期' in all_text):
            return True
        # 检查第一列是否以版次格式开头（如 A/0, A/1, V1.0 等）
        version_pattern_count = 0
        for row in children[1:]:
            cells = row.get('children', [])
            if cells:
                first_cell = (cells[0].get('content', '') or '').strip()
                if re.match(r'^[A-Za-z]/\d+', first_cell) or re.match(r'^V\d', first_cell):
                    version_pattern_count += 1
        return version_pattern_count >= 2

    def _add_revision_table(self, node: Dict[str, Any], after_toc: bool = False):
        """用模板格式渲染md中的修订记录数据"""
        if not self._using_template or self._template_revision_table is None:
            # 无模板时按普通表格渲染
            self._add_table(node)
            return

        children = node.get('children', [])
        col_count = 6  # 模板标准6列: 版次/修订人/修订原因/修订内容/修订日期/备注
        tmpl_headers = ['版次', '修订人', '修订原因', '修订内容', '修订日期', '备注']

        # 检测md列数
        md_col_count = max((len(row.get('children', [])) for row in children), default=0)
        md_col_count = min(md_col_count, col_count)

        # 确定数据起始行：检查首行是表头还是数据
        data_start = 0
        if children:
            first_cells = children[0].get('children', [])
            first_text = (first_cells[0].get('content', '') if first_cells else '').strip()
            # 首行是版本号（如 A/0, V1.0）→ 直接是数据
            if first_text and not re.match(r'^[A-Za-z]/\d+', first_text) and not re.match(r'^V\d', first_text):
                data_start = 1  # 首行是表头，跳过
                # 检查第二行是否为分隔行
                if len(children) > 1:
                    second_cells = children[1].get('children', [])
                    if all(not (c.get('content', '') or '').strip() for c in second_cells):
                        data_start = 2

        # 收集每列的header文本（仅表头行）
        col_texts = [''] * md_col_count
        for row_node in children[:data_start]:
            cells = row_node.get('children', [])
            for j, cell in enumerate(cells):
                if j < md_col_count:
                    col_texts[j] += (cell.get('content', '') or '').strip()

        # 收集数据样本用于模式匹配（仅数据行，跳过空行）
        col_samples = [[] for _ in range(md_col_count)]
        for row_node in children[data_start:]:
            if row_node.get('type') != 'table_row':
                continue
            cells = row_node.get('children', [])
            for j in range(md_col_count):
                if j < len(cells):
                    val = (cells[j].get('content', '') or '').strip()
                    if val:
                        col_samples[j].append(val)

        # 用数据模式检测列类型
        def _detect_col_type(samples):
            if not samples:
                return -1
            if any(re.match(r'^[A-Za-z]/\d+', s) for s in samples):
                return 0
            if any(re.match(r'^\d{4}\.\d{2}\.\d{2}', s) for s in samples):
                return 4
            if any(len(s) > 10 or re.search(r'[,，.。;；、]', s) for s in samples):
                return 3
            if all(2 <= len(s) <= 4 and re.match(r'^[一-鿿]+$', s) for s in samples):
                return 1
            if any(len(s) <= 6 for s in samples):
                return 3
            return -1

        # 先用数据模式检测
        md_to_tmpl = [-1] * md_col_count
        used_tmpl = set()
        for md_j, samples in enumerate(col_samples):
            col_type = _detect_col_type(samples)
            if col_type >= 0 and col_type not in used_tmpl:
                md_to_tmpl[md_j] = col_type
                used_tmpl.add(col_type)

        # 再用header文本补充未识别的列
        col_keywords = [
            (0, ['版次', '版']),
            (4, ['修订日期', '日期']),
            (1, ['修订人']),
            (3, ['修订内容', '内容']),
            (2, ['修订原因', '原因']),
            (5, ['备注']),
        ]
        for tmpl_idx, keywords in col_keywords:
            if tmpl_idx in used_tmpl:
                continue
            for md_j, col_text in enumerate(col_texts):
                if md_to_tmpl[md_j] >= 0:
                    continue
                for kw in keywords:
                    if kw in col_text:
                        md_to_tmpl[md_j] = tmpl_idx
                        used_tmpl.add(tmpl_idx)
                        break

        # 填充未映射的列
        next_tmpl = 0
        for md_j in range(md_col_count):
            if md_to_tmpl[md_j] == -1:
                while next_tmpl in used_tmpl and next_tmpl < col_count:
                    next_tmpl += 1
                if next_tmpl < col_count:
                    md_to_tmpl[md_j] = next_tmpl
                    used_tmpl.add(next_tmpl)

        # 解析数据行
        data_rows = []
        for row_node in children[data_start:]:
            if row_node.get('type') != 'table_row':
                continue
            cells = row_node.get('children', [])
            # 按映射重组数据到模板列
            row_data = [''] * col_count
            for md_j, tmpl_j in enumerate(md_to_tmpl):
                if md_j < len(cells) and tmpl_j >= 0:
                    row_data[tmpl_j] = self._clean_cell_text(cells[md_j].get('content', '') or '')
            # 补充不足的列
            while len(row_data) < col_count:
                row_data.append('')
            # 跳过空行
            if not any(v.strip() if v else '' for v in row_data):
                continue
            data_rows.append(row_data)

        if not data_rows:
            return

        # 插入"文件修订履历表"标题
        body = self.doc.element.body
        title_p = OxmlElement('w:p')
        title_pPr = OxmlElement('w:pPr')
        title_pStyle = OxmlElement('w:pStyle')
        title_pStyle.set(qn('w:val'), 'Title')
        title_pPr.append(title_pStyle)
        title_p.append(title_pPr)
        title_r = OxmlElement('w:r')
        title_t = OxmlElement('w:t')
        title_t.text = '文件修订履历表'
        title_r.append(title_t)
        title_p.append(title_r)

        if after_toc:
            # TOC占body前3个元素（标题、TOC域、分页符），修订表插入到位置3
            body.insert(3, title_p)
        else:
            body.append(title_p)

        # 创建修订记录表
        table = self.doc.add_table(rows=len(data_rows) + 1, cols=col_count)

        if after_toc:
            # add_table 默认追加到末尾，将其移到标题之后
            tbl_element = body[-1]
            body.remove(tbl_element)
            body.insert(4, tbl_element)
        self._configure_table_properties(table)

        # 表头列类型（修订记录表：版次=center, 修订人=center, 修订原因=desc, 修订内容=desc, 修订日期=center, 备注=desc）
        rev_col_types = ['numeric', 'general', 'desc', 'desc', 'numeric', 'desc']

        # 表头行
        tmpl_headers = ['版次', '修订人', '修订原因', '修订内容', '修订日期', '备注']
        header_cell_data = [{'content': h, 'children': [], 'attributes': {}} for h in tmpl_headers]
        self._set_row_properties(table.rows[0], True)
        for j, h in enumerate(tmpl_headers):
            if j < col_count:
                cell_node = header_cell_data[j]
                self._format_cell(table.cell(0, j), cell_node, rev_col_types[j], is_header=True)

        # 数据行
        for i, row_data in enumerate(data_rows):
            row_idx = i + 1
            self._set_row_properties(table.rows[row_idx], False)
            for j, val in enumerate(row_data):
                if j < col_count:
                    cell_node = {'content': val, 'children': [], 'attributes': {}}
                    self._format_cell(table.cell(row_idx, j), cell_node, rev_col_types[j], is_header=False)

        self._apply_column_widths(table, [], col_count, rev_col_types)

    def _insert_template_revision_table(self, after_toc: bool = False):
        """插入模板的修订记录表（md无修订数据时）"""
        if self._template_revision_table is None:
            return
        body = self.doc.element.body
        if after_toc:
            body.insert(3, self._template_revision_table)
        else:
            body.append(self._template_revision_table)

    # ---------- 表格列宽优化 ----------

    # ---------- 表格属性配置 ----------

    TABLE_FONT_WEST = 'Consolas'
    TABLE_FONT_EAST = 'Microsoft YaHei'
    TABLE_FONT_SIZE = Pt(10)
    TABLE_ROW_HEIGHT = 360  # twips, atLeast
    TABLE_CELL_MARGIN = 40  # dxa
    TABLE_HEADER_BG = 'D9D9D9'
    TABLE_BORDER_COLOR = '808080'
    TABLE_BORDER_SIZE = 4  # eighths of a point
    TABLE_TOTAL_WIDTH_DXA = 9000  # A4正文宽度
    TABLE_COL_MIN_WIDTH = 600
    TABLE_COL_MAX_WIDTH = 5000

    def _configure_table_properties(self, table):
        """设置表格级属性：宽度、边框、autofit、tblLook、cellMar"""
        tbl = table._tbl
        tblPr = self._ensure_element(tbl, 'w:tblPr', first=True)

        # 表格宽度 100%
        tblW = self._ensure_element(tblPr, 'w:tblW', first=True)
        tblW.set(qn('w:w'), '5000')
        tblW.set(qn('w:type'), 'pct')

        # 表格居中
        jc = self._ensure_element(tblPr, 'w:jc')
        jc.set(qn('w:val'), 'center')

        # 固定列宽布局（关闭 autofit）
        tblLayout = self._ensure_element(tblPr, 'w:tblLayout')
        tblLayout.set(qn('w:type'), 'fixed')

        # tblLook — professional look
        tblLook = self._ensure_element(tblPr, 'w:tblLook')
        tblLook.set(qn('w:firstRow'), '1')
        tblLook.set(qn('w:lastRow'), '0')
        tblLook.set(qn('w:firstColumn'), '0')
        tblLook.set(qn('w:lastColumn'), '0')
        tblLook.set(qn('w:noHBand'), '0')
        tblLook.set(qn('w:noVBand'), '1')
        tblLook.set(qn('w:val'), '0480')

        # 表格边框
        tblBorders = self._ensure_element(tblPr, 'w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = self._ensure_element(tblBorders, f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), str(self.TABLE_BORDER_SIZE))
            border.set(qn('w:color'), self.TABLE_BORDER_COLOR)
            border.set(qn('w:space'), '0')

        # 表格级 cell margin
        tblCellMar = self._ensure_element(tblPr, 'w:tblCellMar')
        for margin_name in ['top', 'left', 'bottom', 'right']:
            m = self._ensure_element(tblCellMar, f'w:{margin_name}')
            m.set(qn('w:w'), str(self.TABLE_CELL_MARGIN))
            m.set(qn('w:type'), 'dxa')

    def _set_row_properties(self, row, is_header: bool):
        """设置行级属性：行高、表头标记、cantSplit"""
        tr = row._tr
        trPr = self._ensure_element(tr, 'w:trPr', first=True)

        # 统一行高
        trHeight = self._ensure_element(trPr, 'w:trHeight')
        trHeight.set(qn('w:val'), str(self.TABLE_ROW_HEIGHT))
        trHeight.set(qn('w:hRule'), 'atLeast')

        # 表头跨页重复
        if is_header:
            tblHeader = OxmlElement('w:tblHeader')
            tblHeader.set(qn('w:val'), 'true')
            trPr.insert(0, tblHeader)

        # 不允许行跨页断裂
        cantSplit = OxmlElement('w:cantSplit')
        cantSplit.set(qn('w:val'), 'true')
        trPr.append(cantSplit)

    def _format_cell(self, cell, cell_node: Dict[str, Any], col_type: str, is_header: bool):
        """格式化单个单元格：字体、对齐、背景、边距"""
        segments = cell_node.get('children', [])
        raw_content = cell_node.get('content', '')
        clean_content = self._clean_cell_text(raw_content)
        md_align = cell_node.get('attributes', {}).get('align', '')

        tc = cell._tc
        tcPr = self._ensure_element(tc, 'w:tcPr', first=True)

        # 清除旧 cell margin，设新边距
        old_mar = tcPr.find(qn('w:tcMar'))
        if old_mar is not None:
            tcPr.remove(old_mar)
        tcMar = OxmlElement('w:tcMar')
        m = OxmlElement('w:top')
        m.set(qn('w:w'), str(self.TABLE_CELL_MARGIN))
        m.set(qn('w:type'), 'dxa')
        tcMar.append(m)
        m = OxmlElement('w:left')
        m.set(qn('w:w'), str(self.TABLE_CELL_MARGIN + 20))
        m.set(qn('w:type'), 'dxa')
        tcMar.append(m)
        m = OxmlElement('w:bottom')
        m.set(qn('w:w'), str(self.TABLE_CELL_MARGIN))
        m.set(qn('w:type'), 'dxa')
        tcMar.append(m)
        m = OxmlElement('w:right')
        m.set(qn('w:w'), str(self.TABLE_CELL_MARGIN + 20))
        m.set(qn('w:type'), 'dxa')
        tcPr.append(tcMar)

        # 垂直居中
        vAlign = self._ensure_element(tcPr, 'w:vAlign')
        vAlign.set(qn('w:val'), 'center')

        # 表头灰底
        if is_header:
            shd = self._ensure_element(tcPr, 'w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), self.TABLE_HEADER_BG)

        # 写入内容
        if segments:
            for seg in segments:
                if 'content' in seg:
                    seg['content'] = self._clean_cell_text(seg['content'])
            first_para = cell.paragraphs[0]
            first_para.clear()
            self._process_inline_content(first_para, clean_content, segments)
        else:
            cell.text = ''
            first_para = cell.paragraphs[0]
            first_para.clear()
            run = first_para.add_run(clean_content)
            run.font.name = self.TABLE_FONT_WEST
            run.font.size = self.TABLE_FONT_SIZE
            run.element.rPr.rFonts.set(qn('w:eastAsia'), self.TABLE_FONT_EAST)

        # 对齐方式
        if is_header:
            align = 'center'
        elif md_align == 'center':
            align = 'center'
        elif md_align == 'right':
            align = 'right'
        elif col_type == 'desc':
            align = 'left'
        elif col_type == 'numeric':
            align = 'center'
        else:
            align = 'left'

        for para in cell.paragraphs:
            pPr = self._ensure_element(para._p, 'w:pPr', first=True)

            # 显式设置零缩进（覆盖样式继承，需同时归零 twip 和 character 单位）
            ind = pPr.find(qn('w:ind'))
            if ind is not None:
                pPr.remove(ind)
            ind = OxmlElement('w:ind')
            ind.set(qn('w:left'), '0')
            ind.set(qn('w:leftChars'), '0')
            ind.set(qn('w:right'), '0')
            ind.set(qn('w:rightChars'), '0')
            ind.set(qn('w:firstLine'), '0')
            ind.set(qn('w:firstLineChars'), '0')
            ind.set(qn('w:hanging'), '0')
            ind.set(qn('w:hangingChars'), '0')
            pPr.append(ind)

            # 清除段间距
            old_spacing = pPr.find(qn('w:spacing'))
            if old_spacing is not None:
                pPr.remove(old_spacing)

            # 设置对齐
            pJc = pPr.find(qn('w:jc'))
            if pJc is None:
                pJc = OxmlElement('w:jc')
                pPr.append(pJc)
            if align == 'center':
                pJc.set(qn('w:val'), 'center')
            elif align == 'right':
                pJc.set(qn('w:val'), 'right')
            else:
                pJc.set(qn('w:val'), 'left')

            # 字体
            for run in para.runs:
                run.font.name = self.TABLE_FONT_WEST
                run.font.size = self.TABLE_FONT_SIZE
                run.element.rPr.rFonts.set(qn('w:eastAsia'), self.TABLE_FONT_EAST)
                if is_header:
                    run.font.bold = True

    def _is_likely_header(self, rows: List[Dict[str, Any]]) -> bool:
        """判断第一行是否为表头：第一行是短标签，数据行内容显著不同"""
        if len(rows) < 2:
            return False
        first = rows[0].get('children', [])
        rest = rows[1].get('children', [])
        if not first or not rest:
            return False

        # 第一行平均字符长度
        first_lens = [len(self._clean_cell_text(c.get('content', '') or '')) for c in first]
        first_avg = sum(first_lens) / max(len(first_lens), 1)

        # 数据行平均字符长度
        rest_lens = [len(self._clean_cell_text(c.get('content', '') or '')) for c in rest]
        rest_avg = sum(rest_lens) / max(len(rest_lens), 1)

        # 第一行短 + 与数据行差异显著
        if first_avg <= 20 and (rest_avg == 0 or first_avg < rest_avg * 0.7):
            return True
        # 或者第一行全是单行短文本(< 30 chars)
        if all(l < 30 for l in first_lens) and any(l > 15 for l in rest_lens):
            return True
        return False

    def _classify_columns(self, rows: List[Dict[str, Any]], col_count: int, header_count: int) -> List[str]:
        """检测各列语义类型：desc(长文本) / numeric(数字/代码) / general"""
        types = []
        data_start = header_count
        for j in range(col_count):
            texts = []
            for row_node in rows[data_start:]:
                cells = row_node.get('children', [])
                if j < len(cells):
                    t = self._clean_cell_text(cells[j].get('content', '') or '')
                    if t:
                        texts.append(t)
            types.append(self._guess_column_type(texts))
        return types

    def _guess_column_type(self, texts: List[str]) -> str:
        """根据文本内容猜测列类型"""
        if not texts:
            return 'general'
        avg_len = sum(len(t) for t in texts) / len(texts)
        # 长文本 → description
        if avg_len > 20:
            return 'desc'
        # 检查是否为数字/日期/版本号/编号
        numeric_count = 0
        for t in texts:
            t_clean = t.replace(',', '').replace('.', '').replace('-', '').replace('/', '').replace(' ', '').replace('%', '')
            if t_clean.isdigit() or re.match(r'^[\d.\-/: Vv]+$', t):
                numeric_count += 1
        if numeric_count >= len(texts) * 0.6:
            return 'numeric'
        return 'general'

    def _apply_column_widths(self, table, rows: List[Dict[str, Any]], col_count: int, col_types: List[str]):
        """内容感知列宽分配，使用开方软化比例，强制最小/最大比例"""
        if col_count <= 0:
            return

        total_width = self.TABLE_TOTAL_WIDTH_DXA
        min_width = int(total_width * 0.08)   # 最少 8%
        max_width = int(total_width * 0.55)   # 最多 55%

        # 计算每列内容权重（用开方软化差异）
        weights = [1.0] * col_count
        for j in range(col_count):
            max_chars = 4
            for row_node in rows:
                cells = row_node.get('children', [])
                if j < len(cells):
                    t = self._clean_cell_text(cells[j].get('content', '') or '')
                    max_chars = max(max_chars, self._estimate_char_width(t))
            # 开方软化 + desc 列加权
            w = max_chars ** 0.6
            if j < len(col_types) and col_types[j] == 'desc':
                w *= 1.3
            weights[j] = w

        weight_total = sum(weights)
        if weight_total <= 0:
            weight_total = col_count

        # 按权重分配
        col_widths = []
        for j in range(col_count):
            w = int(total_width * weights[j] / weight_total)
            col_widths.append(max(min_width, min(w, max_width)))

        # 归一化
        current_total = sum(col_widths)
        if current_total > 0 and current_total != total_width:
            # 按比例缩放，保持最小宽度约束
            surplus = total_width - current_total
            # 将 surplus 按权重分配给未达到 max 的列
            eligible = [j for j in range(col_count) if col_widths[j] < max_width]
            while surplus != 0 and eligible:
                share = surplus // len(eligible) if surplus > 0 else -((-surplus) // len(eligible))
                if share == 0:
                    share = 1 if surplus > 0 else -1
                for j in eligible[:]:
                    new_w = col_widths[j] + share
                    if surplus > 0:
                        new_w = min(new_w, max_width)
                    else:
                        new_w = max(new_w, min_width)
                    delta = new_w - col_widths[j]
                    col_widths[j] = new_w
                    surplus -= delta
                    if new_w == max_width:
                        eligible.remove(j)
                    if surplus == 0:
                        break

        # 微调至精确总宽
        delta = total_width - sum(col_widths)
        if delta != 0 and col_count > 0:
            col_widths[col_count - 1] += delta

        # 应用列宽
        for row in table.rows:
            for j in range(col_count):
                if j < len(row.cells):
                    cell = row.cells[j]
                    tc = cell._tc
                    tcPr = self._ensure_element(tc, 'w:tcPr', first=True)
                    tcW = self._ensure_element(tcPr, 'w:tcW', first=True)
                    tcW.set(qn('w:w'), str(col_widths[j]))
                    tcW.set(qn('w:type'), 'dxa')

    def _estimate_char_width(self, text: str) -> int:
        """估算文本的等宽字符数（近似）"""
        if not text:
            return 0
        count = 0
        for ch in text:
            if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯':
                count += 2  # CJK字符 ≈ 2个等宽字符
            else:
                count += 1
        return count

    @staticmethod
    def _ensure_element(parent, tag: str, first: bool = False):
        """查找或创建子元素"""
        existing = parent.find(qn(tag))
        if existing is not None:
            return existing
        el = OxmlElement(tag)
        if first:
            parent.insert(0, el)
        else:
            parent.append(el)
        return el

    def _process_node(self, node: Dict[str, Any]):
        """
        处理AST节点

        Args:
            node: AST节点
        """
        node_type = node.get('type')

        if node_type == 'heading':
            self._add_heading(node)
        elif node_type == 'paragraph':
            self._add_paragraph(node)
        elif node_type == 'list':
            self._add_list(node)
        elif node_type == 'table':
            self._add_table(node)
        elif node_type == 'code_block':
            # 检查是否为流程图
            if self.flowchart_enabled and self.flowchart_processor:
                content = node.get('content', '')
                chart_type = self.flowchart_processor.detect_flowchart(content)
                if chart_type:
                    self._add_flowchart(node, chart_type)
                else:
                    self._add_code_block(node)
            else:
                self._add_code_block(node)
        elif node_type == 'blockquote':
            self._add_blockquote(node)
        elif node_type == 'image':
            self._add_image(node)
        elif node_type == 'hr':
            self._add_hr(node)
        elif node_type == 'footnote_block':
            self._add_footnote_block(node)
        elif node_type == 'math_block':
            self._add_math_block(node)
        elif node_type == 'math_inline':
            self._add_math_inline_para(node)
        elif node_type == 'definition_list':
            self._add_definition_list(node)

    def _add_heading(self, node: Dict[str, Any]):
        level = node.get('level', 1)
        content = node.get('content', '')
        segments = node.get('children', [])

        heading = self._add_heading_safe(level, content)

        if segments:
            heading.clear()
            self._process_inline_content(heading, content, segments)
        elif heading.runs:
            heading.runs[0].text = content
        else:
            heading.add_run(content)

        if not self._using_template:
            for run in heading.runs:
                run.font.name = self.font
                run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

    def _add_heading_safe(self, level: int, content: str):
        """添加标题，模板无对应级别时降级到最接近的可用级别"""
        if not self._using_template:
            return self.doc.add_heading(content, level=level)

        for l in range(level, 0, -1):
            style_name = f'Heading {l}'
            try:
                self.doc.styles[style_name]
                return self.doc.add_heading(content, level=l)
            except KeyError:
                continue

        para = self.doc.add_paragraph(style='Normal')
        run = para.add_run(content)
        run.font.bold = True
        return para

    def _safe_style(self, preferred: str, fallback: str) -> str:
        """安全获取样式名：模板存在则用，不存在则降级"""
        if not self._using_template:
            return fallback
        try:
            self.doc.styles[preferred]
            return preferred
        except KeyError:
            try:
                self.doc.styles[fallback]
                return fallback
            except KeyError:
                return 'Normal'

    def _add_paragraph(self, node: Dict[str, Any]):
        content = node.get('content', '')
        segments = node.get('children', [])

        style_name = self._safe_style(self.STYLE_MAP['paragraph'], 'Normal') if self._using_template else None
        para = self.doc.add_paragraph(style=style_name) if style_name else self.doc.add_paragraph()

        self._process_inline_content(para, content, segments if segments else None)

        if not self._using_template:
            for run in para.runs:
                if not run.font.name:
                    run.font.name = self.font
                    run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

    def _process_inline_content(self, para, content: str, segments: List[Dict[str, Any]] = None):
        """处理内联内容，使用模板样式时跳过硬编码字体，仅设置格式偏离"""
        if not segments:
            run = para.add_run(content)
            if not self._using_template:
                run.font.name = self.font
                run.font.size = Pt(self.font_size)
            return

        for seg in segments:
            seg_type = seg.get("type", "text")

            if seg_type == "text":
                text = seg.get("content", "")
                if not text:
                    continue
                run = para.add_run(text)
                if not self._using_template:
                    run.font.name = self.font
                    run.font.size = Pt(self.font_size)
                    run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)
                if seg.get("bold"):
                    run.font.bold = True
                if seg.get("italic"):
                    run.font.italic = True
                if seg.get("strikethrough"):
                    run.font.strike = True
                if seg.get("underline"):
                    run.font.underline = True

            elif seg_type == "code_inline":
                text = seg.get("content", "")
                run = para.add_run(text)
                run.font.name = 'Courier New'
                run.font.size = Pt((self.font_size - 1) if not self._using_template else 9)
                shading = OxmlElement('w:shd')
                shading.set(qn('w:val'), 'clear')
                shading.set(qn('w:color'), 'auto')
                shading.set(qn('w:fill'), 'F0F0F0')
                run.element.rPr.append(shading)

            elif seg_type == "link":
                text = seg.get("content", "")
                href = seg.get("href", "")
                if href:
                    self._add_hyperlink(para, text, href)
                else:
                    run = para.add_run(text)
                    if not self._using_template:
                        run.font.name = self.font
                        run.font.size = Pt(self.font_size)

            elif seg_type == "image":
                pass

            elif seg_type == "footnote_ref":
                label = seg.get("label", "")
                self._footnote_counter += 1
                run = para.add_run(f'[{self._footnote_counter}]')
                run.font.size = Pt(8)
                run.font.superscript = True
                run.font.color.rgb = RGBColor(0, 102, 204)

            elif seg_type == "softbreak":
                para.add_run('\n')

            elif seg_type == "hardbreak":
                para.add_run('\n')

            elif seg_type == "math_inline":
                text = seg.get("content", "")
                run = para.add_run(f' ${text}$ ')
                run.font.name = 'Cambria Math'
                run.font.italic = True
                shading = OxmlElement('w:shd')
                shading.set(qn('w:val'), 'clear')
                shading.set(qn('w:color'), 'auto')
                shading.set(qn('w:fill'), 'F0F4FF')
                run.element.rPr.append(shading)

            elif seg_type == "kbd":
                text = seg.get("content", "")
                run = para.add_run(text)
                run.font.name = 'Courier New'
                run.font.size = Pt(9)
                shading = OxmlElement('w:shd')
                shading.set(qn('w:val'), 'clear')
                shading.set(qn('w:color'), 'auto')
                shading.set(qn('w:fill'), 'EBEBEB')
                run.element.rPr.append(shading)
                bdr = OxmlElement('w:bdr')
                bdr.set(qn('w:val'), 'single')
                bdr.set(qn('w:sz'), '4')
                bdr.set(qn('w:space'), '1')
                bdr.set(qn('w:color'), 'A0A0A0')
                run.element.rPr.append(bdr)

            elif seg_type == "sub":
                text = seg.get("content", "")
                run = para.add_run(text)
                run.font.size = Pt((self.font_size - 2) if not self._using_template else 10)
                run.font.subscript = True

            elif seg_type == "sup":
                text = seg.get("content", "")
                run = para.add_run(text)
                run.font.size = Pt((self.font_size - 2) if not self._using_template else 10)
                run.font.superscript = True

            elif seg_type == "highlight":
                text = seg.get("content", "")
                run = para.add_run(text)
                if not self._using_template:
                    run.font.name = self.font
                    run.font.size = Pt(self.font_size)
                shading = OxmlElement('w:shd')
                shading.set(qn('w:val'), 'clear')
                shading.set(qn('w:color'), 'auto')
                shading.set(qn('w:fill'), 'FFFF00')
                run.element.rPr.append(shading)

    def _add_hyperlink(self, para, text: str, url: str):
        """
        在段落中添加超链接

        Args:
            para: 段落对象
            text: 链接显示文本
            url: 链接URL
        """
        # 获取文档关系部分
        part = para.part
        r_id = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)

        # 创建超链接元素
        hyperlink = OxmlElement('w:hyperlink')
        hyperlink.set(qn('r:id'), r_id)

        # 创建run
        new_run = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')

        # 蓝色字体
        color = OxmlElement('w:color')
        color.set(qn('w:val'), '0563C1')
        rPr.append(color)

        # 下划线
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        rPr.append(u)

        # 字体设置（使用模板时跳过，由段落样式决定）
        if not self._using_template:
            rFonts = OxmlElement('w:rFonts')
            rFonts.set(qn('w:ascii'), self.font)
            rFonts.set(qn('w:eastAsia'), self.font)
            rPr.append(rFonts)

            sz = OxmlElement('w:sz')
            sz.set(qn('w:val'), str(int(self.font_size * 2)))
            rPr.append(sz)

        new_run.append(rPr)

        # 文本内容
        t = OxmlElement('w:t')
        t.text = text
        new_run.append(t)

        hyperlink.append(new_run)
        para._p.append(hyperlink)

    def _add_list(self, node: Dict[str, Any], level: int = 0):
        children = node.get('children', [])
        ordered = node.get('attributes', {}).get('ordered', False)

        for item in children:
            if item.get('type') == 'list_item':
                if ordered:
                    style_name = self._safe_style(self.STYLE_MAP['list_number'], 'List Number')
                else:
                    style_name = self._safe_style(self.STYLE_MAP['list_bullet'], 'List Bullet')
                para = self.doc.add_paragraph(style=style_name)

                para.paragraph_format.left_indent = Cm(1.27 * level)

                item_paragraphs = [c for c in item.get('children', []) if c.get('type') == 'paragraph']
                if item_paragraphs:
                    first_para = item_paragraphs[0]
                    segments = first_para.get('children', [])
                    content = first_para.get('content', '')

                    task_checked = first_para.get('attributes', {}).get('task_checked')
                    if task_checked is not None:
                        checkbox = '☑ ' if task_checked else '☐ '
                        cb_run = para.add_run(checkbox)

                    self._process_inline_content(para, content, segments if segments else None)
                else:
                    item_content = self._get_list_item_content(item)
                    para.add_run(item_content)

                if not self._using_template:
                    for run in para.runs:
                        if not run.font.name:
                            run.font.name = self.font
                            run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

                for child in item.get('children', []):
                    if child.get('type') == 'list':
                        self._add_list(child, level + 1)

    def _get_list_item_content(self, node: Dict[str, Any]) -> str:
        """
        获取列表项内容

        Args:
            node: 列表项节点

        Returns:
            内容文本
        """
        content_parts = []
        for child in node.get('children', []):
            if child.get('type') == 'paragraph':
                content_parts.append(child.get('content', ''))
        return ' '.join(content_parts)

    def _add_table(self, node: Dict[str, Any]):
        children = node.get('children', [])
        if not children:
            return

        # 过滤空行
        valid_rows = []
        for row_node in children:
            row_cells = row_node.get('children', [])
            if row_cells:
                has_content = any(
                    cell.get('content', '').strip() or cell.get('children')
                    for cell in row_cells
                )
                if has_content:
                    valid_rows.append(row_node)

        if not valid_rows:
            return

        rows = len(valid_rows)
        cols = max(
            len(row.get('children', [])) for row in valid_rows
        )
        if rows == 0 or cols == 0:
            return

        # 检测表头：第一行短标签 + 数据行内容显著不同
        has_header = self._is_likely_header(valid_rows)

        table = self.doc.add_table(rows=rows, cols=cols)
        self._configure_table_properties(table)

        # 检测各列的语义类型
        col_types = self._classify_columns(valid_rows, cols, 1 if has_header else 0)

        for i, row_node in enumerate(valid_rows):
            row_cells = row_node.get('children', [])
            is_header = has_header and i == 0

            # 设置行属性
            self._set_row_properties(table.rows[i], is_header)

            for j, cell_node in enumerate(row_cells):
                if j >= cols:
                    break
                cell = table.cell(i, j)
                self._format_cell(cell, cell_node, col_types[j], is_header)

        self._apply_column_widths(table, valid_rows, cols, col_types)

    def _clean_cell_text(self, text: str) -> str:
        """清理表格单元格文本：去除自定义标签、合并连续空白、去除首尾空格"""
        if not text:
            return text
        # 去除 <pp>, <dd>, <id>, <lowercase letter=""> 等自定义标签
        cleaned = re.sub(r'<[^>]*>', '', text)
        # 保留换行，合并其他连续空白
        cleaned = re.sub(r'[^\S\n]+', ' ', cleaned)
        return cleaned.strip()

    def _add_code_block(self, node: Dict[str, Any]):
        content = node.get('content', '')
        language = node.get('attributes', {}).get('language', '')

        style_name = self._safe_style(self.STYLE_MAP['code_block'], 'Normal') if self._using_template else None
        para = self.doc.add_paragraph(style=style_name) if style_name else self.doc.add_paragraph()

        para.paragraph_format.left_indent = Cm(1)
        para.paragraph_format.right_indent = Cm(1)
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(6)

        run = para.add_run(content)
        run.font.name = 'Courier New'
        run.font.size = Pt(10)

        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F5F5F5')
        pPr.append(shd)

        if language:
            lang_para = self.doc.add_paragraph()
            lang_run = lang_para.add_run(f'Language: {language}')
            lang_run.font.size = Pt(8)
            lang_run.font.color.rgb = RGBColor(128, 128, 128)

    def _add_flowchart(self, node: Dict[str, Any], chart_type: str):
        """
        添加流程图

        Args:
            node: 代码块节点
            chart_type: 流程图类型（mermaid, plantuml）
        """
        content = node.get('content', '')

        # 生成输出路径
        self.flowchart_counter += 1
        output_dir = Path(self.output_dir) if self.output_dir else Path('.')
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f'flowchart_{self.flowchart_counter}.png'

        # 渲染流程图
        success = self.flowchart_processor.render_flowchart(
            content, chart_type, str(image_path)
        )

        if success and image_path.exists():
            # 插入流程图图片（限制尺寸，带标题）
            self._add_image_with_caption(
                str(image_path),
                f'图 {self.flowchart_counter}',
                max_width=5.5, max_height=6.0
            )
        else:
            # 渲染失败，添加代码块
            self.log(f"流程图渲染失败，添加为代码块", "warning")
            self._add_code_block(node)

    def _add_blockquote(self, node: Dict[str, Any]):
        children = node.get('children', [])

        for child in children:
            if child.get('type') == 'paragraph':
                style_name = self._safe_style(self.STYLE_MAP['blockquote'], 'Normal') if self._using_template else None
                para = self.doc.add_paragraph(style=style_name) if style_name else self.doc.add_paragraph()

                para.paragraph_format.left_indent = Cm(2)
                para.paragraph_format.right_indent = Cm(2)

                content = child.get('content', '')
                segments = child.get('children', [])
                if segments:
                    self._process_inline_content(para, content, segments)
                else:
                    run = para.add_run(content)
                    if not self._using_template:
                        run.font.name = self.font
                        run.font.size = Pt(self.font_size)
                    run.font.italic = True

                pPr = para._p.get_or_add_pPr()
                pBdr = OxmlElement('w:pBdr')
                left = OxmlElement('w:left')
                left.set(qn('w:val'), 'single')
                left.set(qn('w:sz'), '18')
                left.set(qn('w:space'), '4')
                left.set(qn('w:color'), 'BFBFBF')
                pBdr.append(left)
                pPr.append(pBdr)

    def _add_image_with_caption(self, image_path: str, caption_text: str,
                                max_width: float = 5.5, max_height: float = 6.0):
        """
        插入图片并附带标题，限制图片尺寸防止撑满整页。

        通过限制最大宽高、设置段落分页控制，确保图片和标题在同一页面内。

        Args:
            image_path: 图片文件路径
            caption_text: 标题文本（可为空）
            max_width: 最大宽度（英寸），默认5.5
            max_height: 最大高度（英寸），默认6.0
        """
        try:
            from PIL import Image as PILImage
            with PILImage.open(image_path) as img:
                img_w, img_h = img.size
        except Exception:
            img_w, img_h = 800, 600  # 回退默认比例

        # 按比例缩放到限制范围内
        width = min(max_width, img_w / 96)  # 假设96dpi
        height = width * img_h / img_w
        if height > max_height:
            height = max_height
            width = height * img_w / img_h

        # 插入图片
        para = self.doc.add_paragraph()
        run = para.add_run()
        run.add_picture(image_path, width=Inches(width))

        # 设置段落属性：居中 + 与下段同页
        pPr = para._p.get_or_add_pPr()
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), 'center')
        pPr.append(jc)
        keepNext = OxmlElement('w:keepNext')
        pPr.append(keepNext)

        # 添加标题（紧跟图片）
        if caption_text:
            cap = self.doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap.add_run(caption_text)
            run.font.size = Pt(9)
            if not self._using_template:
                run.font.name = self.font
            run.font.color.rgb = RGBColor(128, 128, 128)

    def _add_image(self, node: Dict[str, Any]):
        """
        添加图片

        Args:
            node: 图片节点
        """
        src = node.get('attributes', {}).get('src', '')
        alt = node.get('attributes', {}).get('alt', '')

        if not src:
            self.log(f"图片路径为空: {alt}", "warning")
            return

        try:
            image_path = None

            if src.startswith('http://') or src.startswith('https://'):
                # 远程图片，下载到临时目录
                image_path = self._download_remote_image(src)
                if not image_path:
                    return
            else:
                # 本地图片
                p = Path(src)
                if p.exists():
                    image_path = p
                elif self.input_dir:
                    # 尝试相对于输入文件的路径
                    p = self.input_dir / src
                    if p.exists():
                        image_path = p

                if not image_path:
                    self.log(f"图片不存在: {src}", "warning")
                    return

            # 插入图片（限制尺寸，避免撑满整页）
            self._add_image_with_caption(str(image_path), alt, max_width=5.5, max_height=6.0)

        except Exception as e:
            self.log(f"插入图片失败: {e}", "error")

    def _download_remote_image(self, url: str) -> Path:
        """
        下载远程图片到临时目录

        Args:
            url: 图片URL

        Returns:
            临时文件路径，失败返回None
        """
        try:
            # 从URL推断文件扩展名
            ext = Path(url.split('?')[0]).suffix or '.png'
            # 创建临时文件
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp_path = Path(tmp.name)
            # 下载
            self.log(f"下载远程图片: {url}")
            with urlopen(url, timeout=15) as resp:
                tmp.write(resp.read())
            tmp.close()
            return tmp_path
        except (URLError, OSError, TimeoutError) as e:
            self.log(f"远程图片下载失败: {url} ({e})", "warning")
            return None

    def _add_hr(self, node: Dict[str, Any]):
        """
        添加分割线

        Args:
            node: 分割线节点（用于接口一致性）
        """
        para = self.doc.add_paragraph()

        # 通过段落底部边框实现水平分割线
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), 'BFBFBF')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _add_footnote_block(self, node: Dict[str, Any]):
        """
        添加脚注块（文档末尾的脚注列表）

        Args:
            node: 脚注块节点
        """
        children = node.get('children', [])
        if not children:
            return

        # 添加脚注分隔线
        sep_para = self.doc.add_paragraph()
        pPr = sep_para._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), 'BFBFBF')
        pBdr.append(bottom)
        pPr.append(pBdr)

        for i, footnote in enumerate(children):
            if footnote.get('type') != 'footnote':
                continue
            label = footnote.get('attributes', {}).get('label', '')
            fn_children = footnote.get('children', [])

            fn_style = self._safe_style(self.STYLE_MAP['footnote'], 'Normal') if self._using_template else None
            para = self.doc.add_paragraph(style=fn_style) if fn_style else self.doc.add_paragraph()
            para.paragraph_format.space_before = Pt(2)
            para.paragraph_format.space_after = Pt(2)

            num_run = para.add_run(f'[{i + 1}] ')
            num_run.font.size = Pt(9)
            num_run.font.superscript = True
            num_run.font.color.rgb = RGBColor(0, 102, 204)

            for fn_child in fn_children:
                if fn_child.get('type') == 'paragraph':
                    content = fn_child.get('content', '')
                    segments = fn_child.get('children', [])
                    if segments:
                        self._process_inline_content(para, content, segments)
                    else:
                        run = para.add_run(content)
                        run.font.size = Pt(9)
                        if not self._using_template:
                            run.font.name = self.font

    def _add_math_block(self, node: Dict[str, Any]):
        content = node.get('content', '')

        style_name = self._safe_style(self.STYLE_MAP['math_block'], 'Normal') if self._using_template else None
        para = self.doc.add_paragraph(style=style_name) if style_name else self.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(6)

        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F0F4FF')
        pPr.append(shd)

        pBdr = OxmlElement('w:pBdr')
        left = OxmlElement('w:left')
        left.set(qn('w:val'), 'single')
        left.set(qn('w:sz'), '12')
        left.set(qn('w:space'), '8')
        left.set(qn('w:color'), '4472C4')
        pBdr.append(left)
        pPr.append(pBdr)

        run = para.add_run(content)
        run.font.name = 'Cambria Math'
        run.font.italic = True

    def _add_math_inline_para(self, node: Dict[str, Any]):
        content = node.get('content', '')
        para = self.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(f'${content}$')
        run.font.name = 'Cambria Math'
        run.font.italic = True
        shading = OxmlElement('w:shd')
        shading.set(qn('w:val'), 'clear')
        shading.set(qn('w:color'), 'auto')
        shading.set(qn('w:fill'), 'F0F4FF')
        run.element.rPr.append(shading)

    def _add_definition_list(self, node: Dict[str, Any]):
        items = node.get('children', [])
        for item in items:
            terms = item.get('terms', [])
            term_texts = [t.get('content', '') for t in terms]
            if term_texts:
                term_style = self._safe_style(self.STYLE_MAP['definition_term'], 'Normal') if self._using_template else None
                term_para = self.doc.add_paragraph(style=term_style) if term_style else self.doc.add_paragraph()
                term_para.paragraph_format.space_after = Pt(2)
                term_para.paragraph_format.left_indent = Cm(1)
                run = term_para.add_run('; '.join(term_texts))
                run.font.bold = True
                if not self._using_template:
                    run.font.name = self.font
                    run.font.size = Pt(self.font_size)
                    run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)

            desc = item.get('description', {})
            desc_content = desc.get('content', '')
            if desc_content:
                desc_style = self._safe_style(self.STYLE_MAP['definition_desc'], 'Normal') if self._using_template else None
                desc_para = self.doc.add_paragraph(style=desc_style) if desc_style else self.doc.add_paragraph()
                desc_para.paragraph_format.left_indent = Cm(2)
                desc_para.paragraph_format.space_after = Pt(8)
                run = desc_para.add_run(desc_content)
                if not self._using_template:
                    run.font.name = self.font
                    run.font.size = Pt(self.font_size)
                    run.element.rPr.rFonts.set(qn('w:eastAsia'), self.font)