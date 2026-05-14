"""输出文件质量修正器 —— 转换后修正渲染缺陷

preflight 检查源文件语法，postflight 检查输出有无崩溃级问题，
polisher 修正在转换过程中产生的格式损耗（信息已存在但渲染不佳）。

@tool
name: polish_output
description: 对转换后的输出文件进行格式修正和自动补全。修正表格列宽、
             图片尺寸、段落间距、字体一致性等转换过程中产生的渲染损失。
             不同于 postflight（只读检查），polisher 直接修改输出文件。
when_to_use: 转换完成后、postflight 检查通过后。Word 格式效果最显著，
             HTML 格式做基础修正。
input: 输出文件路径 (str)，支持 .docx / .html
output: PolishReport (修正项列表, modified 数量)
side_effect: 直接修改输出文件（原地修正）

用法:
    from polisher import polish

    report = polish("output/doc.docx")
    print(f"已修正 {report.modified} 项: {[i.description for i in report.items]}")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List
from dataclasses import dataclass, field


@dataclass
class PolishItem:
    """单个修正项"""
    category: str       # "table" | "image" | "pagebreak" | "font" | "spacing" | "cleanup" | "metadata"
    description: str
    detail: str = ""


@dataclass
class PolishReport:
    """修正报告"""
    file_path: str
    format: str
    items: List[PolishItem] = field(default_factory=list)

    @property
    def modified(self) -> int:
        return len(self.items)

    @property
    def has_changes(self) -> bool:
        return self.modified > 0


def polish(file_path: str) -> PolishReport:
    """对输出文件执行所有适用的修正，自动检测格式"""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = p.suffix.lower()
    if suffix == '.docx':
        return _polish_docx(p)
    elif suffix in ('.html', '.htm'):
        return _polish_html(p)
    elif suffix == '.pdf':
        # PDF 是二进制渲染结果，应在 HTML→PDF 前修正 HTML
        return PolishReport(file_path=str(p), format='pdf')
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


# ============================================================================
#  Word 修正器
# ============================================================================

# A4 可用宽度（带标准页边距 2.54cm）
_A4_CONTENT_WIDTH_EMU = 6285600   # ~17cm（Word 默认 A4 正文区）
_A4_CONTENT_WIDTH_DXA = 9000      # ~15.8cm
_MAX_IMAGE_WIDTH_EMU = int(15 * 360000)  # 15cm（比当前的 12cm 合理）
_HEADING_STYLES = {'Heading 1', 'Heading 2', 'Heading 3',
                   'Heading 4', 'Heading 5', 'Heading 6',
                   'heading 1', 'heading 2', 'heading 3',
                   'heading 4', 'heading 5', 'heading 6',
                   '标题 1', '标题 2', '标题 3',
                   '标题 4', '标题 5', '标题 6',
                   '标题1', '标题2', '标题3',
                   '标题4', '标题5', '标题6',
                   '1', '2', '3', '4', '5', '6'}


def _polish_docx(file_path: Path) -> PolishReport:
    """对 Word 文档执行所有修正"""
    report = PolishReport(file_path=str(file_path), format='docx')

    try:
        from docx import Document
        from docx.shared import Inches, Cm, Pt, Emu
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        report.items.append(PolishItem('cleanup', '跳过（python-docx 不可用）'))
        return report

    doc = Document(str(file_path))

    _polish_table_columns(doc, report)
    _polish_image_sizes(doc, report)
    _polish_page_breaks(doc, report)
    _polish_font_consistency(doc, report)
    _polish_paragraph_spacing(doc, report)
    _polish_clean_empty_trailing(doc, report)

    if report.has_changes:
        doc.save(str(file_path))

    return report


# ---- 1. 表格列宽智能适配 ----

def _polish_table_columns(doc, report: PolishReport):
    """按各列实际内容长度智能分配列宽。

    原则：
    1. 扫描每列所有行，找出各列的实际渲染宽度
    2. 每列给「刚好够 + 少量余量」，绝不撑大短列
    3. 剩余宽度按内容占比分配给文字多的列
    4. 总宽溢出时等比压缩，保证不超页面
    5. 横表自动使用更宽的可用区域
    """
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    _MIN_COL = 600          # 单列最小宽度
    _PADDING_RATIO = 1.12   # 在测量宽度上留的余量比例

    def _char_width_dxa(text: str) -> float:
        w = 0.0
        for c in text:
            if '一' <= c <= '鿿' or '　' <= c <= '〿' or '＀' <= c <= '￯':
                w += 240
            elif '぀' <= c <= 'ゟ' or '゠' <= c <= 'ヿ':
                w += 220
            else:
                w += 120
        return w

    def _table_available_width(table) -> int:
        """Determine available content width for a table.

        In OOXML, content belongs to the section defined by the NEXT sectPr
        (the one that terminates the section). We find the first sectPr
        FOLLOWING the table in document order.
        """
        try:
            body = table._tbl.getparent()
            if body is None:
                return 9000
            nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            children = list(body)
            tbl_idx = children.index(table._tbl)
            # Walk forwards from the table to find the terminating sectPr
            for child in children[tbl_idx:]:
                for sect in child.iterfind('.//w:sectPr', nsmap):
                    pgSz = sect.find('w:pgSz', nsmap)
                    if pgSz is not None:
                        w_val = int(pgSz.get(qn('w:w'), '0'))
                        h_val = int(pgSz.get(qn('w:h'), '0'))
                        if w_val > 0 and h_val > 0 and w_val > h_val:
                            return 13200
                        return 9000
            # No following sectPr — use last section
            if doc.sections and doc.sections[-1].page_width > doc.sections[-1].page_height:
                return 13200
        except Exception:
            pass
        return 9000

    # ---- 收集每列文本（扫描所有行） ----
    for ti, table in enumerate(doc.tables, 1):
        rows = table.rows
        col_count = len(table.columns)
        if col_count <= 1:
            continue

        # 为每表计算可用宽度（横表用更宽的可用区域）
        _available = _table_available_width(table)

        col_texts: list[list[str]] = [[] for _ in range(col_count)]
        for row in rows:
            for ci in range(min(col_count, len(row.cells))):
                col_texts[ci].append(row.cells[ci].text)

        # ---- 计算每列的「目标宽度」和「内容总量」 ----
        col_practical = [0.0] * col_count   # 刚好够用的宽度
        col_content = [0.0] * col_count     # 内容总量（用于分配剩余空间）

        for ci, texts in enumerate(col_texts):
            if not texts:
                continue

            # 扫描该列所有行，取完整文本渲染宽度的最大值 + 余量
            max_full_width = max((_char_width_dxa(t) for t in texts), default=0)
            col_practical[ci] = max(_MIN_COL, max_full_width * _PADDING_RATIO)

            # 内容总量 = 所有行文本宽度之和（代表该列「需要多少空间」）
            col_content[ci] = sum(_char_width_dxa(t) for t in texts)

        # ---- 分配宽度 ----
        allocated = [0.0] * col_count

        # Phase A: 先满足最小安全宽度
        sum_practical = sum(col_practical)
        if sum_practical <= _available:
            for ci in range(col_count):
                allocated[ci] = col_practical[ci]
            remaining = _available - sum_practical
        else:
            # 最小宽度之和超出可用 → 等比压缩
            scale = _available / sum_practical
            for ci in range(col_count):
                allocated[ci] = max(_MIN_COL, col_practical[ci] * scale)
            remaining = 0

        # Phase B: 剩余空间按「内容总量」占比分配给内容多的列
        if remaining > 10:
            total_content = sum(col_content)
            if total_content > 0:
                for ci in range(col_count):
                    extra = remaining * (col_content[ci] / total_content)
                    allocated[ci] += extra
                remaining = 0

        # Phase C: 仍有剩余 → 均匀分配
        if remaining > 10:
            for ci in range(col_count):
                allocated[ci] += remaining / col_count
            remaining = 0

        # ---- 表头宽度硬保障：确保每个列表头文字不折行 ----
        if rows:
            # 表头单元格的 margin 约 120 dxa (left+right)，加 60 dxa 缓冲
            _CELL_H_MARGIN = 180
            for ci in range(col_count):
                if ci >= len(rows[0].cells):
                    continue
                h_text = rows[0].cells[ci].text
                if not h_text:
                    continue
                h_width = _char_width_dxa(h_text) + _CELL_H_MARGIN
                if allocated[ci] >= h_width:
                    continue
                deficit = h_width - allocated[ci]
                # 从最宽的列拆借（跳过自身和已经到表头底线的列）
                widest = max(
                    (i for i in range(col_count) if i != ci),
                    key=lambda i: allocated[i]
                )
                max_take = allocated[widest] - _MIN_COL
                # 被拆借列也要留够自己的表头宽度
                if widest < len(rows[0].cells):
                    w_text = rows[0].cells[widest].text
                    if w_text:
                        w_min = _char_width_dxa(w_text) + _CELL_H_MARGIN
                        max_take = min(max_take, allocated[widest] - w_min)
                take = min(deficit, max(max_take, 0))
                if take > 0:
                    allocated[widest] -= take
                    allocated[ci] += take

        # ---- 美观均衡：防止单列过宽或边列过窄 ----
        # 对列数少的表，头尾列被挤到 600dxa 而中间列 85% 太难看。
        # 约束：单列上限 ≤ _available * max_single_ratio
        #       边列下限 ≥ _available * min_edge_ratio
        if col_count in (2, 3):
            max_single_ratio = 0.68 if col_count == 3 else 0.78
            min_edge_ratio = 0.12 if col_count == 3 else 0.18

            # 单列上限约束
            cap = _available * max_single_ratio
            for ci in range(col_count):
                if allocated[ci] > cap:
                    excess = allocated[ci] - cap
                    allocated[ci] = cap
                    others = [c for c in range(col_count) if c != ci]
                    other_content = sum(col_content[c] for c in others)
                    if other_content > 0:
                        for c in others:
                            allocated[c] += excess * (col_content[c] / other_content)

            # 边列下限约束
            edge_min = _available * min_edge_ratio
            for ci in (0, col_count - 1):
                if allocated[ci] < edge_min:
                    deficit = edge_min - allocated[ci]
                    widest = max(range(col_count), key=lambda i: allocated[i])
                    if allocated[widest] - deficit > _MIN_COL:
                        allocated[widest] -= deficit
                        allocated[ci] = edge_min

        # ---- 整数化 + 确保总和不超 _available ----
        int_widths = [max(_MIN_COL, int(w)) for w in allocated]
        diff = _available - sum(int_widths)
        if diff != 0 and col_count > 0:
            # 差值加给内容最多的列
            max_content_idx = max(range(col_count), key=lambda i: col_content[i])
            int_widths[max_content_idx] = max(_MIN_COL, int_widths[max_content_idx] + diff)

        # ---- 写入 gridCol ----
        tbl = table._tbl
        tblGrid = tbl.find(qn('w:tblGrid'))
        if tblGrid is None:
            tblGrid = OxmlElement('w:tblGrid')
            tblPr = tbl.find(qn('w:tblPr'))
            if tblPr is not None:
                tblPr.addnext(tblGrid)
        for gc in tblGrid.findall(qn('w:gridCol')):
            tblGrid.remove(gc)

        equal_w = _available // col_count
        for ci, w in enumerate(int_widths):
            gc = OxmlElement('w:gridCol')
            gc.set(qn('w:w'), str(w))
            tblGrid.append(gc)

        # ---- 同时校正 cell 级别的 tcW ----
        for row in table.rows:
            for ci in range(min(col_count, len(row.cells))):
                tcPr = row.cells[ci]._tc.find(qn('w:tcPr'))
                if tcPr is None:
                    tcPr = OxmlElement('w:tcPr')
                    row.cells[ci]._tc.insert(0, tcPr)
                tcW = tcPr.find(qn('w:tcW'))
                if tcW is None:
                    tcW = OxmlElement('w:tcW')
                    tcPr.append(tcW)
                tcW.set(qn('w:w'), str(int_widths[ci]))
                tcW.set(qn('w:type'), 'dxa')

        if any(abs(w - equal_w) > 300 for w in int_widths):
            report.items.append(PolishItem(
                'table',
                f'表格 {ti} 列宽智能适配',
                ', '.join(f'C{ci+1}={w}dxa' for ci, w in enumerate(int_widths))
            ))

    # ---- 连续同列数表格列宽对齐 ----
    # 当多个同列数表格紧邻排列（如产品列表拆分为多个 table 块），
    # 各自独立计算会导致竖线不对齐。这里对连续、同列数的表格取
    # 每列最大宽度，等比缩放到可用宽度后统一写入。
    try:
        _harmonize_consecutive_tables(doc, report)
    except Exception:
        pass


# ---- 连续表格列宽对齐实现 ----

def _harmonize_consecutive_tables(doc, report: PolishReport):
    """Align gridCol of consecutive same-column-count tables."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    body = doc.element.body
    nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    # 收集 body 中所有 tbl 元素及其索引
    tbl_entries = []  # [(index_in_body, tbl_element)]
    children = list(body)
    for idx, child in enumerate(children):
        if child.tag == qn('w:tbl'):
            tbl_entries.append((idx, child))

    if len(tbl_entries) < 2:
        return

    # 找出连续表格组（中间只有空白段落/空元素）
    groups = []
    current_group = [tbl_entries[0]]
    for i in range(1, len(tbl_entries)):
        prev_idx = tbl_entries[i - 1][0]
        curr_idx = tbl_entries[i][0]
        # 检查中间元素是否可以忽略（空段落、sectPr 等）
        gap_is_empty = True
        for j in range(prev_idx + 1, curr_idx):
            child = children[j]
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag in ('p',):
                # 检查段落是否为空
                text = (child.text or '') + ''.join(
                    (e.text or '') + (e.tail or '')
                    for e in child.iter()
                )
                if text.strip():
                    gap_is_empty = False
                    break
            elif tag in ('sectPr',):
                continue  # sectPr 不算内容间隔
            elif tag in ('tbl',):
                continue
            else:
                gap_is_empty = False
                break

        if gap_is_empty:
            current_group.append(tbl_entries[i])
        else:
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [tbl_entries[i]]

    if len(current_group) >= 2:
        groups.append(current_group)

    aligned_count = 0
    for group in groups:
        # 按列数分组（同一连续组内可能列数不同）
        by_cols: dict = {}
        for idx, tbl in group:
            tblGrid = tbl.find(qn('w:tblGrid'))
            if tblGrid is None:
                continue
            gc_list = tblGrid.findall(qn('w:gridCol'))
            col_count = len(gc_list)
            if col_count <= 1:
                continue
            by_cols.setdefault(col_count, []).append((idx, tbl, gc_list))

        for col_count, entries in by_cols.items():
            if len(entries) < 2:
                continue

            # 取每列的最大宽度
            max_widths = [0] * col_count
            for _, _, gc_list in entries:
                for ci, gc in enumerate(gc_list):
                    w = int(gc.get(qn('w:w'), '0'))
                    if w > max_widths[ci]:
                        max_widths[ci] = w

            # 确定可用宽度（取组内第一个表的可用宽度）
            first_tbl = entries[0][1]
            available = 9000
            try:
                tbl_idx_in_body = children.index(first_tbl)
                for child in children[tbl_idx_in_body:]:
                    for sect in child.iterfind('.//w:sectPr', nsmap):
                        pgSz = sect.find('w:pgSz', nsmap)
                        if pgSz is not None:
                            w_val = int(pgSz.get(qn('w:w'), '0'))
                            h_val = int(pgSz.get(qn('w:h'), '0'))
                            if w_val > 0 and h_val > 0 and w_val > h_val:
                                available = 13200
                            break
            except Exception:
                pass

            total_max = sum(max_widths)
            if total_max <= 0:
                continue

            # 等比缩放到可用宽度
            if total_max > available:
                scale = available / total_max
                aligned = [max(600, int(w * scale)) for w in max_widths]
            else:
                aligned = [int(w) for w in max_widths]
            # 补齐差值
            diff = available - sum(aligned)
            if diff != 0:
                aligned[-1] += diff

            # 如果对齐后宽度和原宽度完全一致，跳过
            all_same = True
            for _, _, gc_list in entries:
                for ci, gc in enumerate(gc_list):
                    if int(gc.get(qn('w:w'), '0')) != aligned[ci]:
                        all_same = False
                        break
                if not all_same:
                    break
            if all_same:
                continue

            # 统一写入
            for _, tbl, gc_list in entries:
                for gc in gc_list:
                    tblGrid_elem = tbl.find(qn('w:tblGrid'))
                    if tblGrid_elem is not None:
                        for old_gc in list(tblGrid_elem.findall(qn('w:gridCol'))):
                            tblGrid_elem.remove(old_gc)
                        for ci, w in enumerate(aligned):
                            gc_new = OxmlElement('w:gridCol')
                            gc_new.set(qn('w:w'), str(w))
                            tblGrid_elem.append(gc_new)

                # 同步更新 cell tcW
                for row in tbl.findall(qn('w:tr')):
                    cells = row.findall(qn('w:tc'))
                    for ci in range(min(col_count, len(cells))):
                        tcPr = cells[ci].find(qn('w:tcPr'))
                        if tcPr is not None:
                            tcW = tcPr.find(qn('w:tcW'))
                            if tcW is not None:
                                tcW.set(qn('w:w'), str(aligned[ci]))

            aligned_count += len(entries)

    if aligned_count > 0:
        report.items.append(PolishItem(
            'table',
            f'对齐 {aligned_count} 个连续表格的列宽'
        ))

def _polish_image_sizes(doc, report: PolishReport):
    """检查并修正图片尺寸，确保不超出页面且保持比例"""
    from docx.oxml.ns import qn
    from docx.shared import Emu
    try:
        from PIL import Image
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False

    img_count = 0
    for para in doc.paragraphs:
        for run in para.runs:
            for drawing in run._element.findall(
                    '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                # 提取图片尺寸
                blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                if blip is None:
                    continue
                ext = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
                if ext is None:
                    continue
                try:
                    cx = int(ext.get('cx', '0'))
                except ValueError:
                    continue

                if cx > _MAX_IMAGE_WIDTH_EMU:
                    # 需要缩小
                    scale = _MAX_IMAGE_WIDTH_EMU / cx
                    cy = int(ext.get('cy', '0'))
                    ext.set('cx', str(_MAX_IMAGE_WIDTH_EMU))
                    if cy:
                        ext.set('cy', str(int(cy * scale)))
                    img_count += 1

    if img_count > 0:
        report.items.append(PolishItem(
            'image',
            f'修正 {img_count} 张超宽图片的尺寸',
            f'最大宽度限制 {_MAX_IMAGE_WIDTH_EMU // 360000}cm'
        ))


# ---- 3. 标题分页策略 ----

def _polish_page_breaks(doc, report: PolishReport):
    """清理标题强制分页，只保留显式分页，并避免标题孤悬。"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    removed_break_count = 0
    keep_count = 0

    def heading_level(style_name: str) -> int | None:
        if style_name not in _HEADING_STYLES:
            return None
        match = re.search(r'([1-6])$', style_name)
        if not match:
            return None
        return int(match.group(1))

    def remove_page_break_before(pPr) -> int:
        if pPr is None:
            return 0
        removed = 0
        for page_break in list(pPr.findall(qn('w:pageBreakBefore'))):
            pPr.remove(page_break)
            removed += 1
        return removed

    def ensure_flag(pPr, tag_name: str) -> bool:
        if pPr.find(qn(tag_name)) is not None:
            return False
        pPr.append(OxmlElement(tag_name))
        return True

    # 有些模板会把“段前分页”写在 Heading 样式里，先从样式层清理。
    for style in doc.styles:
        style_name = getattr(style, 'name', '')
        level = heading_level(style_name)
        if level is None:
            continue
        style_pPr = getattr(style.element, 'pPr', None)
        removed_break_count += remove_page_break_before(style_pPr)

    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ''
        level = heading_level(style_name)
        if level is None:
            continue

        pPr = para._p.get_or_add_pPr()
        removed_break_count += remove_page_break_before(pPr)

        if level <= 3:
            changed = ensure_flag(pPr, 'w:keepNext')
            changed = ensure_flag(pPr, 'w:keepLines') or changed
            if changed:
                keep_count += 1

    if removed_break_count > 0:
        report.items.append(PolishItem(
            'pagebreak',
            f'移除 {removed_break_count} 个标题段前强制分页',
            '章节不再默认另起一页，仅保留目录、修订记录和 Markdown 显式分页'
        ))

    if keep_count > 0:
        report.items.append(PolishItem(
            'pagebreak',
            f'设置 {keep_count} 个标题与下段同页',
            '避免标题落在页尾导致阅读断裂'
        ))


# ---- 4. 字体一致性 ----

_WEST_FONT = 'Calibri'
_CJK_FONT = 'Microsoft YaHei'
_MONO_FONT = 'Consolas'
_MONO_CJK = 'Microsoft YaHei'


def _polish_font_consistency(doc, report: PolishReport):
    """确保每个 run 都同时设置了西文和中文字体，避免 Word 字体回退异常"""
    from docx.oxml.ns import qn
    from docx.shared import Pt

    fixed_runs = 0
    for para in doc.paragraphs:
        for run in para.runs:
            rPr = run._element.find(qn('w:rPr'))
            if rPr is None:
                continue

            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is None:
                continue

            west = rFonts.get(qn('w:ascii')) or rFonts.get(qn('w:hAnsi'))
            east = rFonts.get(qn('w:eastAsia'))

            text = run.text
            has_cjk = bool(re.search(r'[一-鿿　-〿＀-￯]', text))
            has_west = bool(re.search(r'[a-zA-Z0-9]', text))

            is_code = (run.font.name and
                       run.font.name.lower() in ('consolas', 'courier new', 'monaco'))

            if is_code:
                if not west:
                    rFonts.set(qn('w:ascii'), _MONO_FONT)
                    fixed_runs += 1
                if has_cjk and not east:
                    rFonts.set(qn('w:eastAsia'), _MONO_CJK)
                    fixed_runs += 1
            else:
                if has_west and not west:
                    rFonts.set(qn('w:ascii'), _WEST_FONT)
                    rFonts.set(qn('w:hAnsi'), _WEST_FONT)
                    fixed_runs += 1
                if has_cjk and not east:
                    rFonts.set(qn('w:eastAsia'), _CJK_FONT)
                    fixed_runs += 1

    if fixed_runs > 0:
        report.items.append(PolishItem(
            'font',
            f'修正 {fixed_runs} 处字体回退缺失',
            f'西文→{_WEST_FONT}, 中文→{_CJK_FONT}'
        ))


# ---- 5. 段落间距规范化 ----

def _polish_paragraph_spacing(doc, report: PolishReport):
    """确保段落间距一致：正文段落有合理的段后间距，标题有合适的段前间距"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Pt

    adjusted = 0
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ''

        is_heading = style_name in _HEADING_STYLES
        is_normal = style_name == 'Normal' or style_name == 'Normal Style'
        is_list = style_name == 'List Bullet' or style_name == 'List Number'

        if not para.text.strip() and not is_heading:
            continue  # 空段落跳过

        pPr = para._p.find(qn('w:pPr'))
        if pPr is None:
            continue

        spacing = pPr.find(qn('w:spacing'))
        need_spacing = False

        if is_normal and spacing is None:
            spacing = OxmlElement('w:spacing')
            pPr.append(spacing)
            need_spacing = True

        if is_normal and need_spacing:
            spacing.set(qn('w:after'), '120')  # 6pt after
            spacing.set(qn('w:line'), '276')   # 1.15x line height
            spacing.set(qn('w:lineRule'), 'auto')
            adjusted += 1

        elif is_list and spacing is None:
            spacing = OxmlElement('w:spacing')
            pPr.append(spacing)
            spacing.set(qn('w:after'), '60')   # 3pt after
            spacing.set(qn('w:line'), '276')
            spacing.set(qn('w:lineRule'), 'auto')
            adjusted += 1

    if adjusted > 0:
        report.items.append(PolishItem(
            'spacing',
            f'规范 {adjusted} 个段落间距',
            '正文 6pt 段后, 1.15x 行距'
        ))


# ---- 6. 清理尾部空段落 ----

def _polish_clean_empty_trailing(doc, report: PolishReport):
    """删除文档末尾的连续空段落"""
    from docx.oxml.ns import qn

    body = doc.element.body
    paragraphs = body.findall(qn('w:p'))
    if not paragraphs:
        return

    removed = 0
    for p in reversed(paragraphs):
        # 检查段落是否为空
        text_elements = p.findall('.//' + qn('w:t'))
        text = ''.join(t.text or '' for t in text_elements).strip()

        # 检查是否有图片或其它非文本内容
        has_drawing = p.findall('.//' + qn('w:drawing'))
        has_object = p.findall('.//' + qn('w:object'))

        if text or has_drawing or has_object:
            break  # 遇到第一个非空段落就停止

        # 移除前检查是否有分页符（保留分页符）
        pPr = p.find(qn('w:pPr'))
        if pPr is not None:
            sectPr = p.find(qn('w:sectPr'))
            if sectPr is not None:
                break  # 最后一节的分节符不能删

        body.remove(p)
        removed += 1

    if removed > 0:
        report.items.append(PolishItem(
            'cleanup',
            f'清理文档末尾 {removed} 个空白段落'
        ))


# ============================================================================
#  HTML 修正器
# ============================================================================

def _polish_html(file_path: Path) -> PolishReport:
    """对 HTML 文件执行基础修正"""
    report = PolishReport(file_path=str(file_path), format='html')

    html = file_path.read_text(encoding='utf-8')
    modified = False

    # 1. 确保有 viewport meta
    if '<meta name="viewport"' not in html and '<head>' in html:
        html = html.replace('<head>',
                            '<head>\n<meta name="viewport" content="width=device-width, initial-scale=1.0">',
                            1)
        report.items.append(PolishItem('metadata', '添加 viewport meta 标签'))
        modified = True

    # 2. 确保有 lang 属性
    if '<html' in html and 'lang=' not in html.split('<html')[1].split('>')[0]:
        html = html.replace('<html', '<html lang="zh-CN"', 1)
        report.items.append(PolishItem('metadata', '添加 lang="zh-CN" 属性'))
        modified = True

    # 3. 确保图片有 alt 属性
    img_re = re.compile(r'<img((?:(?!alt=)[^>])*)>')
    missing_alt = 0
    for m in img_re.finditer(html):
        if 'alt=' not in m.group(0):
            old = m.group(0)
            new = old.replace('<img', '<img alt=""', 1)
            html = html.replace(old, new, 1)
            missing_alt += 1
    if missing_alt > 0:
        report.items.append(PolishItem('image', f'为 {missing_alt} 张图片添加空 alt 属性'))
        modified = True

    # 4. 确保有打印样式（如果含 pre.mermaid）
    if '<pre class="mermaid">' in html and '@media print' not in html:
        print_css = (
            '\n<style>\n@media print {\n'
            '  pre.mermaid { page-break-inside: avoid; }\n'
            '  h1, h2, h3 { page-break-after: avoid; }\n'
            '  table { page-break-inside: avoid; }\n'
            '  tr { page-break-inside: avoid; }\n'
            '}\n</style>\n'
        )
        if '</head>' in html:
            html = html.replace('</head>', print_css + '</head>', 1)
            report.items.append(PolishItem('metadata', '添加打印样式（避免图表跨页截断）'))
            modified = True

    # 5. 为宽表格添加响应式容器
    table_re = re.compile(r'(<table[^>]*>)', re.IGNORECASE)
    wide_table_count = 0
    for m in table_re.finditer(html):
        tag = m.group(0)
        if 'class=' in tag:
            if 'table--data' in tag or 'table--revision' in tag:
                start = m.start()
                # 找到对应的 </table>
                end = html.find('</table>', start)
                if end > 0:
                    end += 8
                    original = html[start:end]
                    if not html[max(0, start-30):start].strip().endswith('<div class="table-wrapper">'):
                        wrapped = f'<div class="table-wrapper">\n{original}\n</div>'
                        html = html.replace(original, wrapped, 1)
                        wide_table_count += 1
    if wide_table_count > 0:
        report.items.append(PolishItem(
            'table', f'为 {wide_table_count} 个宽表格添加响应式容器'))

    if modified:
        file_path.write_text(html, encoding='utf-8')

    return report
