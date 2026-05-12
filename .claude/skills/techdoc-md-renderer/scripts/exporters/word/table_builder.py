"""HTML 表格 → Word 表格构建器

将 BeautifulSoup4 解析的 HTML <table> 转换为 python-docx 表格对象。
处理表头灰底、边框、列对齐、单元格边距等样式。
"""

from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from .style_mapper import StyleMapper

# 表格样式常量
FONT_WEST = 'Consolas'
FONT_EAST = 'Microsoft YaHei'
FONT_SIZE = Pt(10)
HEADER_BG = 'D9D9D9'
BORDER_COLOR = '808080'
BORDER_SIZE = 4
CELL_MARGIN = 40


class TableBuilder:
    """将 HTML <table> 标签转换为 python-docx 表格"""

    def __init__(self, exporter):
        """
        Args:
            exporter: WordExporter 实例，提供 _has_style / _ensure_element 工具方法
        """
        self._exp = exporter

    def build(self, tag, doc):
        """从 HTML table 标签构建 Word 表格"""
        # 收集所有行
        all_rows = self._collect_rows(tag)
        if not all_rows:
            return

        col_count = max(len(r) for r in all_rows)
        has_thead = tag.find('thead') is not None

        table = doc.add_table(rows=len(all_rows), cols=col_count)
        table_style_name = StyleMapper.get_table_style(tag)
        if self._exp._has_style(doc, table_style_name):
            table.style = doc.styles[table_style_name]

        self._set_borders(table)

        # 填充数据
        header_count = len(self._collect_header_rows(tag))
        for row_idx, row_data in enumerate(all_rows):
            row = table.rows[row_idx]
            is_header_row = row_idx < header_count
            if not has_thead and row_idx == 0:
                first_tag = tag.find_all('tr')
                if row_idx < len(first_tag):
                    is_header_row = bool(first_tag[row_idx].find('th'))

            for col_idx, cell_data in enumerate(row_data):
                if col_idx >= col_count:
                    break
                cell = row.cells[col_idx]
                self._format_cell(cell, cell_data, is_header_row)

    @staticmethod
    def _collect_header_rows(tag):
        """收集 thead 中的行"""
        rows = []
        thead = tag.find('thead')
        if thead:
            for tr in thead.find_all('tr', recursive=False):
                cells = list(StyleMapper.cell_collector(tr, True))
                if cells:
                    rows.append(cells)
        return rows

    @staticmethod
    def _collect_rows(tag):
        """收集所有行（thead + tbody）"""
        header_rows = TableBuilder._collect_header_rows(tag)
        has_thead = tag.find('thead') is not None

        tbody = tag.find('tbody') or tag
        body_rows = []
        for tr in tbody.find_all('tr', recursive=False):
            if has_thead and tr.parent and tr.parent.name == 'thead':
                continue
            is_header = (not has_thead and len(body_rows) == 0 and
                         (tr.find('th') or StyleMapper.is_thead_row(tr)))
            cells = list(StyleMapper.cell_collector(tr, is_header if not has_thead else False))
            if cells:
                body_rows.append(cells)

        return header_rows + body_rows

    def _format_cell(self, cell, cell_data: dict, is_header: bool):
        """格式化单个表格单元格"""
        text = cell_data.get('text', '')
        align_cls = cell_data.get('align')

        tc = cell._tc
        tcPr = self._exp._ensure_element(tc, 'w:tcPr', first=True)

        # 边距
        old_mar = tcPr.find(qn('w:tcMar'))
        if old_mar is not None:
            tcPr.remove(old_mar)
        tcMar = OxmlElement('w:tcMar')
        for side, val in [('top', CELL_MARGIN), ('left', CELL_MARGIN + 20),
                          ('bottom', CELL_MARGIN), ('right', CELL_MARGIN + 20)]:
            m = OxmlElement(f'w:{side}')
            m.set(qn('w:w'), str(val))
            m.set(qn('w:type'), 'dxa')
            tcMar.append(m)
        tcPr.append(tcMar)

        # 垂直居中
        vAlign = self._exp._ensure_element(tcPr, 'w:vAlign')
        vAlign.set(qn('w:val'), 'center')

        # 表头灰底
        if is_header:
            shd = self._exp._ensure_element(tcPr, 'w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), HEADER_BG)

        # 写入文本
        para = cell.paragraphs[0]
        para.clear()
        run = para.add_run(text)
        run.font.name = FONT_WEST
        run.font.size = FONT_SIZE
        run.element.rPr.rFonts.set(qn('w:eastAsia'), FONT_EAST)
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
            pPr = self._exp._ensure_element(p._p, 'w:pPr', first=True)

            # 零缩进
            ind = pPr.find(qn('w:ind'))
            if ind is not None:
                pPr.remove(ind)
            ind = OxmlElement('w:ind')
            for attr in ['left', 'leftChars', 'right', 'rightChars',
                         'firstLine', 'firstLineChars', 'hanging', 'hangingChars']:
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
                r.font.name = FONT_WEST
                r.font.size = FONT_SIZE
                r.element.rPr.rFonts.set(qn('w:eastAsia'), FONT_EAST)
                if is_header:
                    r.font.bold = True

    def _set_borders(self, table):
        """设置表格边框（全边框 0.5pt 灰色）"""
        tbl = table._tbl
        tblPr = self._exp._ensure_element(tbl, 'w:tblPr', first=True)

        tblBorders = tblPr.find(qn('w:tblBorders'))
        if tblBorders is not None:
            tblPr.remove(tblBorders)

        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), str(BORDER_SIZE))
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), BORDER_COLOR)
            tblBorders.append(border)
        tblPr.append(tblBorders)

        # 表格宽度
        tblW = tblPr.find(qn('w:tblW'))
        if tblW is None:
            tblW = OxmlElement('w:tblW')
            tblPr.append(tblW)
        tblW.set(qn('w:w'), '9000')
        tblW.set(qn('w:type'), 'dxa')
