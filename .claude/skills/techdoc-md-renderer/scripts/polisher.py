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


# ---- 1. 表格列宽自动适配 ----

def _polish_table_columns(doc, report: PolishReport):
    """根据单元格内容长度自动调整表格列宽，替代均匀分配"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    for ti, table in enumerate(doc.tables, 1):
        rows = table.rows
        col_count = len(table.columns)
        if col_count == 0:
            continue

        # 计算每列的最大内容宽度（字符数）
        col_widths = [0] * col_count
        for row in rows:
            for ci in range(min(col_count, len(row.cells))):
                text = row.cells[ci].text
                # 中文字符算 2，其他算 1
                w = sum(2 if '一' <= c <= '鿿' or '　' <= c <= '〿'
                        else 1 for c in text)
                col_widths[ci] = max(col_widths[ci], w)

        # 计算总宽度并分配
        total_w = sum(col_widths) or 1
        available = _A4_CONTENT_WIDTH_DXA

        # 设置 gridCol
        tbl = table._tbl
        tblGrid = tbl.find(qn('w:tblGrid'))
        if tblGrid is None:
            tblGrid = OxmlElement('w:tblGrid')
            tblPr = tbl.find(qn('w:tblPr'))
            if tblPr is not None:
                tblPr.addnext(tblGrid)

        # 清除旧的 gridCol
        for gc in tblGrid.findall(qn('w:gridCol')):
            tblGrid.remove(gc)

        adjusted = False
        for cw in col_widths:
            gc = OxmlElement('w:gridCol')
            width_dxa = max(600, int(cw / total_w * available))
            gc.set(qn('w:w'), str(width_dxa))
            tblGrid.append(gc)
            if abs(width_dxa - available // col_count) > 200:
                adjusted = True

        if adjusted and col_count > 1:
            report.items.append(PolishItem(
                'table',
                f'表格 {ti} 列宽已按内容自动适配',
                f'{col_count} 列, 宽度范围 {min(col_widths)}~{max(col_widths)} 字符'
            ))


# ---- 2. 图片尺寸规范化 ----

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


# ---- 3. 章节间分页 ----

def _polish_page_breaks(doc, report: PolishReport):
    """在 H1 章节前插入分页符，H2 前可选"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    page_break_count = 0
    prev_heading_level = 0

    for i, para in enumerate(doc.paragraphs):
        style_name = para.style.name if para.style else ''

        level = None
        if style_name in _HEADING_STYLES:
            try:
                level = int(style_name.split()[-1])
            except (ValueError, IndexError):
                continue

        if level is None:
            prev_heading_level = 0
            continue

        # H1 前加 page break（第一个标题除外）
        if level == 1 and i > 0 and prev_heading_level == 0:
            # 检查前面是否已有分页符
            pPr = para._p.find(qn('w:pPr'))
            if pPr is not None:
                existing_break = pPr.find(qn('w:pageBreakBefore'))
                if existing_break is None:
                    # 在段落属性中设置段前分页（比插入独立分页符更稳定）
                    pb = OxmlElement('w:pageBreakBefore')
                    pPr.append(pb)
                    page_break_count += 1

        prev_heading_level = level

    if page_break_count > 0:
        report.items.append(PolishItem(
            'pagebreak',
            f'在 {page_break_count} 个 H1 章节前添加了分页符'
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
