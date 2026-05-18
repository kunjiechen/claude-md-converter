"""AST → HTML 主渲染器

将Markdown AST节点列表转换为语义化HTML字符串。
每个节点类型输出带CSS class的HTML元素，供CSS统一控制样式。
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import re

from .inline_renderer import InlineRenderer
from .context import RenderContext
from analyzers.paragraph_classifier import ParagraphClassifier
from analyzers.table_classifier import TableClassifier


class HtmlRenderer:
    """AST → HTML 渲染器"""

    # 修订记录表检测关键字
    REVISION_HEADER_KEYWORDS = ['版次', '修订人', '修订日期', '修订内容', '修订原因', '修订描述', '备注']

    def __init__(self, flowchart_processor=None, mermaid_render_mode: str = "auto",
                 inline_images: bool = False):
        self._inline = InlineRenderer()
        self._toc_html = ""
        self._revision_html = ""
        self._flowcharts = []
        self._flowchart_counter = 0
        self._footnote_counter = 0
        self._input_dir = None
        self._flowchart_processor = flowchart_processor
        self._mermaid_render_mode = mermaid_render_mode
        self._inline_images = inline_images

    def render(self, ast: List[Dict[str, Any]], context: RenderContext = None) -> str:
        """将AST渲染为完整HTML文档（body部分）"""
        if context is None:
            context = RenderContext()

        self._flowcharts = []
        self._flowchart_counter = 0
        self._footnote_counter = 0

        # 构建章节编号映射（用于目录和正文标题的一致性编号）
        self._heading_number_map: dict = {}
        self._build_heading_number_map(ast)
        self._heading_seq = 0
        ParagraphClassifier.annotate(ast)

        # 第一遍：扫描识别TOC表和修订记录表
        toc_table_idx = -1
        toc_para_range = None  # (start, end) for paragraph-based TOC
        revision_table_idx = -1
        for i, node in enumerate(ast):
            if node.get('type') == 'table':
                if toc_table_idx < 0 and self._is_toc_table_node(node):
                    toc_table_idx = i
                elif revision_table_idx < 0 and self._is_revision_table_node(node):
                    revision_table_idx = i
        if toc_table_idx < 0:
            toc_para_range = self._find_paragraph_toc_range(ast)

        # 第二遍：渲染节点
        body_parts = []
        i = 0
        while i < len(ast):
            node = ast[i]
            if i == toc_table_idx:
                i += 1
                continue  # TOC由模板层处理
            if toc_para_range and toc_para_range[0] <= i < toc_para_range[1]:
                i += 1
                continue  # 跳过源文件手动目录段落
            if i == revision_table_idx:
                self._revision_html = self._render_revision_table(node)
                # 跳过修订表前面的修订标题（避免与 _add_revision_section 重复）
                if i > 0:
                    prev = ast[i - 1]
                    is_heading = prev.get('type') == 'heading'
                    is_para = prev.get('type') == 'paragraph'
                    if (is_heading or is_para) and self._is_revision_heading(
                        self._clean_heading_text(prev.get('content', ''))
                    ):
                        prev_html = self._process_node(prev)
                        if prev_html in body_parts:
                            body_parts.remove(prev_html)
                i += 1
                continue
            group_html, next_idx = self._render_compact_paragraph_group(ast, i)
            if group_html:
                body_parts.append(group_html)
                i = next_idx
                continue
            html = self._process_node(node)
            if html:
                body_parts.append(html)
            i += 1

        context.body_html = "\n".join(body_parts)
        # 若md未显式提供目录表，则从标题自动生成
        if toc_table_idx < 0 and toc_para_range is None and not self._toc_html:
            self._toc_html = self._generate_toc_from_headings(ast)
        context.toc_html = self._toc_html
        context.revision_html = self._revision_html
        context.flowcharts = self._flowcharts
        return context.body_html

    def render_body(self, ast: List[Dict[str, Any]]) -> str:
        """仅渲染正文body HTML（不含TOC/修订记录）"""
        ctx = RenderContext()
        self.render(ast, ctx)
        return ctx.body_html

    def _process_node(self, node: Dict[str, Any]) -> str:
        node_type = node.get('type')

        if node_type == 'heading':
            return self._render_heading(node)
        elif node_type == 'paragraph':
            return self._render_paragraph(node)
        elif node_type == 'list':
            return self._render_list(node)
        elif node_type == 'table':
            return self._render_table(node)
        elif node_type == 'code_block':
            return self._render_code_block(node)
        elif node_type == 'blockquote':
            return self._render_blockquote(node)
        elif node_type == 'image':
            return self._render_image(node)
        elif node_type == 'hr':
            return '<hr class="hr">'
        elif node_type == 'footnote_block':
            return self._render_footnote_block(node)
        elif node_type == 'math_block':
            return self._render_math_block(node)
        elif node_type == 'math_inline':
            return self._render_math_inline_para(node)
        elif node_type == 'definition_list':
            return self._render_definition_list(node)
        elif node_type == 'pagebreak':
            return '<hr class="pagebreak">'
        elif node_type == 'raw_html':
            return self._render_raw_html(node)
        return ""

    # ---------- 标题 ----------

    def _build_heading_number_map(self, ast: List[Dict]) -> None:
        """构建章节编号映射，与 Word 多级编号一致。

        在渲染前遍历 AST，为每个标题分配层级编号（如 1. / 1.1. / 1.1.1.），
        存入 self._heading_number_map，key 为 heading_index。
        """
        counters = [0] * 6
        heading_idx = 0
        for node in ast:
            if node.get('type') != 'heading':
                continue
            level = min(node.get('level', 1), 6)
            content = self._clean_heading_text(node.get('content', ''))

            # 跳过不参与编号的标题
            if content == '目录' or self._is_revision_heading(content):
                continue

            # 递增当前层级，清零更深层级
            idx = level - 1
            counters[idx] += 1
            for i in range(idx + 1, 6):
                counters[i] = 0
            # 跳层时补齐中间层级为 1
            for i in range(0, idx):
                if counters[i] == 0:
                    counters[i] = 1

            number_str = '.'.join(str(c) for c in counters[:level] if c > 0)
            self._heading_number_map[heading_idx] = number_str
            heading_idx += 1

    def _render_heading(self, node: Dict[str, Any]) -> str:
        level = min(node.get('level', 1), 6)
        content = node.get('content', '')
        tag = f"h{level}"

        clean = self._clean_heading_text(content)
        inner = self._escape(clean)
        number = ''
        if clean not in ('目录',) and not self._is_revision_heading(clean):
            number = self._heading_number_map.get(self._heading_seq, '')
            if number:
                number += ' '
            self._heading_seq += 1

        return f'<{tag} class="heading heading--{level}" id="{self._slugify(clean)}">{number}{inner}</{tag}>'

    # ---------- 段落 ----------

    def _render_paragraph(self, node: Dict[str, Any]) -> str:
        content = node.get('content', '')
        segments = node.get('children', [])
        inner = self._inline.render(segments, content)
        if not inner.strip():
            return ""
        attrs = node.get('attributes', {})
        prose_kind = attrs.get('prose_kind', 'body')
        classes = f'paragraph paragraph--{self._escape_attr(prose_kind)}'
        if attrs.get('prose_group') is not None:
            classes += ' paragraph--grouped'
        return f'<p class="{classes}" data-prose-kind="{self._escape_attr(prose_kind)}">{inner}</p>'

    def _render_compact_paragraph_group(self, ast: List[Dict[str, Any]], start: int) -> tuple[str, int]:
        node = ast[start]
        if node.get('type') != 'paragraph':
            return "", start
        group = node.get('attributes', {}).get('prose_group')
        if group is None:
            return "", start

        parts = []
        i = start
        while i < len(ast):
            current = ast[i]
            if current.get('type') != 'paragraph':
                break
            if current.get('attributes', {}).get('prose_group') != group:
                break
            rendered = self._render_paragraph(current)
            if rendered:
                parts.append(rendered)
            i += 1
        if len(parts) < 2:
            return "", start
        return (
            f'<div class="prose-group prose-group--compact" data-prose-group="{self._escape_attr(str(group))}">\n'
            + "\n".join(parts)
            + "\n</div>",
            i,
        )

    # ---------- 列表 ----------

    def _render_list(self, node: Dict[str, Any], level: int = 0) -> str:
        children = node.get('children', [])
        ordered = node.get('attributes', {}).get('ordered', False)
        tag = "ol" if ordered else "ul"
        list_class = "list list--ordered" if ordered else "list list--bullet"
        if level > 0:
            list_class += f" list--nested list--level-{level}"

        items = []
        for item in children:
            if item.get('type') != 'list_item':
                continue
            item_html = self._render_list_item(item, level)
            if item_html:
                items.append(item_html)

        if not items:
            return ""
        return f'<{tag} class="{list_class}">\n' + "\n".join(items) + f'\n</{tag}>'

    def _render_list_item(self, item: Dict[str, Any], level: int) -> str:
        parts = []
        for child in item.get('children', []):
            if child.get('type') == 'paragraph':
                content = child.get('content', '')
                segments = child.get('children', [])
                inner = self._inline.render(segments, content)

                task_checked = child.get('attributes', {}).get('task_checked')
                if task_checked is not None:
                    checkbox = '<input type="checkbox" disabled' + (' checked' if task_checked else '') + '>'
                    inner = f'{checkbox} {inner}'

                parts.append(inner)
            elif child.get('type') == 'list':
                parts.append(self._render_list(child, level + 1))
        return f"<li>{' '.join(parts)}</li>"

    # ---------- 表格 ----------

    def _render_table(self, node: Dict[str, Any]) -> str:
        children = node.get('children', [])
        if not children:
            return ""

        valid_rows = [r for r in children
                      if r.get('children') and any(
                          (c.get('content', '') or '').strip() or c.get('children')
                          for c in r.get('children', []))]
        if not valid_rows:
            return ""

        # 内容特征校验优先于解析器的 is_header 标记：
        # markdown-it 把 |---| 前的任何行都标记为 thead，但那个位置
        # 放的可能是数据行（如定义表的首条术语）。用内容特征做最终判断。
        if len(valid_rows) >= 2:
            has_header = self._is_likely_header(valid_rows)
        else:
            has_header = any(r.get('is_header') for r in valid_rows)
        cols = max(len(r.get('children', [])) for r in valid_rows)
        col_types = self._classify_columns(valid_rows, cols, 1 if has_header else 0)
        explicit_kind = node.get('attributes', {}).get('table_kind', '')
        analysis = TableClassifier.classify(
            TableClassifier.rows_from_ast({"children": valid_rows}),
            explicit_kind=explicit_kind,
        )
        table_classes = f"table table--data table--{analysis.kind}"
        table_attrs = (
            f'class="{table_classes}" '
            f'data-table-kind="{analysis.kind}" '
            f'data-table-confidence="{analysis.confidence:.2f}"'
        )

        rows_html = []
        for i, row_node in enumerate(valid_rows):
            cells = row_node.get('children', [])
            # 只用内容特征判断：parser 的 is_header 只是 |---| 语法的位置标记
            is_header = has_header and i == 0
            cell_tag = "th" if is_header else "td"
            cells_html = []
            for j, cell_node in enumerate(cells):
                if j >= cols:
                    break
                attrs = cell_node.get('attributes', {})
                align = self._get_cell_align(cell_node, col_types[j] if j < len(col_types) else 'general', is_header)
                raw = cell_node.get('content', '') or ''
                clean = self._clean_cell_text(raw)
                segments = cell_node.get('children', [])
                raw_html = attrs.get('raw_html', '')
                inner = raw_html if raw_html else self._inline.render(segments, clean)
                classes = f"align-{align}"
                extra = ''
                colspan = attrs.get('colspan', 1)
                if colspan > 1:
                    extra += f' colspan="{colspan}"'
                rowspan = attrs.get('rowspan', 1)
                if rowspan > 1:
                    extra += f' rowspan="{rowspan}"'
                cells_html.append(f'<{cell_tag} class="{classes}"{extra}>{inner}</{cell_tag}>')
            rows_html.append(f'<tr>{"".join(cells_html)}</tr>')

        return f'<table {table_attrs}>\n<thead>\n{rows_html[0]}\n</thead>\n<tbody>\n' + \
               "\n".join(rows_html[1:]) + '\n</tbody>\n</table>' if has_header else \
               f'<table {table_attrs}>\n<tbody>\n' + "\n".join(rows_html) + '\n</tbody>\n</table>'

    def _get_cell_align(self, cell_node: Dict, col_type: str, is_header: bool) -> str:
        md_align = cell_node.get('attributes', {}).get('align', '')
        if is_header:
            return 'center'
        if md_align == 'center':
            return 'center'
        if md_align == 'right':
            return 'right'
        if col_type == 'desc':
            return 'left'
        if col_type == 'numeric':
            return 'center'
        return 'left'

    def _is_likely_header(self, rows: List[Dict]) -> bool:
        """判断首行是否为表头。

        用内容特征而非仅长度做判断：真正的表头是「标签式」文本，
        不含代码符号、不含数字主导、不含管道符等数据特征。
        取前 3 行数据的中位数消除占位符（如 -）干扰。
        """
        if len(rows) < 2:
            return False
        first = rows[0].get('children', [])
        if not first:
            return False

        first_texts = [self._clean_cell_text(c.get('content', '') or '') for c in first]
        first_lens = [len(t) for t in first_texts]
        first_avg = sum(first_lens) / max(len(first_lens), 1)

        # 用前 3 个数据行取每列中位数，消弭占位符影响
        data_rows = rows[1:min(len(rows), 4)]
        col_medians = []
        for ci in range(len(first_texts)):
            col_vals = []
            for dr in data_rows:
                cells = dr.get('children', [])
                if ci < len(cells):
                    t = self._clean_cell_text(cells[ci].get('content', '') or '')
                    if t.strip():
                        col_vals.append(len(t))
            if col_vals:
                col_vals.sort()
                col_medians.append(col_vals[len(col_vals) // 2])
        if not col_medians:
            return False
        rest_median_avg = sum(col_medians) / len(col_medians)

        # 宽松比率：首行短+数据行长 → 表头特征
        # 0.80 替代原先的 0.65：避免“文件名称/归档索引 vs 软件命名规范/G-C047”
        # 这类首尾均短的表格被误判为无表头。
        ratio_ok = first_avg < rest_median_avg * 0.80
        short_both = (first_avg <= 10 and rest_median_avg <= 18
                      and first_avg < rest_median_avg)
        if not (first_avg <= 25 and rest_median_avg > 0
                and (ratio_ok or short_both)):
            return False

        # 内容特征：首行每个单元格都必须是"标签式"文本
        import re
        _code_pattern = re.compile(
            r'[|{}\[\]<>]'            # 管道符/括号（数据分隔符）
            r'|[_\.]{2,}'             # 连续下划线/点
            r'|^\d+[\.\)、]\s*'        # 编号开头
            r'|^[\d\s+\-*/%<=>|&^~]+$' # 纯数字/运算符
        )
        _word_pattern = re.compile(r'[\w一-鿿]')

        header_cells = 0
        for t in first_texts:
            if not t.strip():
                continue
            if _code_pattern.search(t):
                return False
            if _word_pattern.search(t):
                header_cells += 1

        non_empty = [t for t in first_texts if t.strip()]
        if not non_empty:
            return False
        return header_cells >= len(non_empty) * 0.5

    def _classify_columns(self, rows: List[Dict], col_count: int, header_count: int) -> List[str]:
        types = []
        for j in range(col_count):
            texts = []
            for row_node in rows[header_count:]:
                cells = row_node.get('children', [])
                if j < len(cells):
                    t = self._clean_cell_text(cells[j].get('content', '') or '')
                    if t:
                        texts.append(t)
            types.append(self._guess_column_type(texts))
        return types

    def _guess_column_type(self, texts: List[str]) -> str:
        if not texts:
            return 'general'
        avg_len = sum(len(t) for t in texts) / len(texts)
        if avg_len > 20:
            return 'desc'
        numeric_count = 0
        for t in texts:
            t_clean = t.replace(',', '').replace('.', '').replace('-', '').replace('/', '').replace(' ', '').replace('%', '')
            if t_clean.isdigit() or re.match(r'^[\d.\-/: Vv]+$', t):
                numeric_count += 1
        if numeric_count >= len(texts) * 0.6:
            return 'numeric'
        return 'general'

    def _clean_cell_text(self, text: str) -> str:
        if not text:
            return text
        cleaned = re.sub(r'<[^>]*>', '', text)
        cleaned = re.sub(r'[^\S\n]+', ' ', cleaned)
        return cleaned.strip()

    # ---------- TOC / 修订记录 检测 ----------

    def _is_toc_table_node(self, node: Dict) -> bool:
        """仅通过首单元格包含「目录」关键词检测"""
        children = node.get('children', [])
        if not children:
            return False
        first_cell = (children[0].get('children', []) or [None])[0]
        if first_cell:
            text = (first_cell.get('content', '') or '').strip()
            return '目录' in text
        return False

    def _find_paragraph_toc_range(self, ast: List[Dict]) -> Optional[tuple]:
        """检测段落形式的目录（非表格），返回 (start, end) 索引范围。

        典型模式：「目录」段落后跟着一系列链接段落，每条含 [text](#anchor)。
        跳过范围包含「目录」段落本身及其后续链接条目。
        """
        for i, node in enumerate(ast):
            if node.get('type') != 'paragraph':
                continue
            content = (node.get('content', '') or '').strip()
            if content != '目录':
                continue
            # 检查后续段落是否为链接条目
            j = i + 1
            link_count = 0
            while j < len(ast):
                next_node = ast[j]
                if next_node.get('type') != 'paragraph':
                    break
                children = next_node.get('children', [])
                if not children or all(
                    c.get('type') in ('link', 'text') for c in children
                ):
                    has_link = any(c.get('type') == 'link' for c in children)
                    nc = (next_node.get('content', '') or '').strip()
                    # 典型的目录条目: [text](#anchor) 格式
                    if has_link and '](#' in nc:
                        link_count += 1
                        j += 1
                        continue
                break
            if link_count >= 3:
                return (i, j)
        return None

    def _generate_toc_from_headings(self, ast: List[Dict]) -> str:
        """从AST标题节点自动生成目录HTML（含章节编号，与Word一致）

        编号索引与 _build_heading_number_map 同步：遍历全部标题节点，
        仅将 h1-h3 且非目录/修订的标题写入 TOC，确保 TOC 中的编号与正文一致。
        """
        items = []
        heading_idx = 0
        for node in ast:
            if node.get('type') != 'heading':
                continue
            level = node.get('level', 1)
            content = self._clean_heading_text(node.get('content', ''))
            if content == '目录' or self._is_revision_heading(content):
                continue
            number = self._heading_number_map.get(heading_idx, '')
            heading_idx += 1
            if level > 3:
                continue
            slug = self._slugify(content)
            label = f'{number} {content}' if number else content
            indent = "  " * (level - 1)
            items.append(f'{indent}<li class="toc-item toc-level-{level}">'
                         f'<a href="#{slug}">{self._escape(label)}</a></li>')
        if not items:
            return ""
        return '<ul class="toc-list">\n' + "\n".join(items) + '\n</ul>'

    @staticmethod
    def _is_revision_heading(text: str) -> bool:
        """检测标题是否为修订记录相关（避免与自动生成的修订表重复）"""
        keywords = ['修订', '履历', '变更', '修改记录', '版本历史']
        return any(kw in text for kw in keywords)

    @staticmethod
    def _clean_heading_text(text: str) -> str:
        """去除标题中的 Markdown 格式标记和手写编号，与 Word 导出保持一致。"""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        text = re.sub(r'^\s*\d+(?:\.\d+)*\.?\s+', '', text)
        return text.strip()

    def _is_revision_table_node(self, node: Dict) -> bool:
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
        version_pattern_count = 0
        for row in children[1:]:
            cells = row.get('children', [])
            if cells:
                first_cell = (cells[0].get('content', '') or '').strip()
                if re.match(r'^[A-Za-z]/\d+', first_cell) or re.match(r'^V\d', first_cell):
                    version_pattern_count += 1
        return version_pattern_count >= 2

    def _render_revision_table(self, node: Dict) -> str:
        """渲染修订记录表为HTML"""
        children = node.get('children', [])
        tmpl_headers = ['版次', '修订人', '修订原因', '修订内容', '修订日期', '备注']
        col_count = 6

        # 确定数据起始行（跳过复杂表头：可能有 2 行表头，含 rowspan/colspan）
        # 原始 HTML 表头结构通常为：「版次/修订人/修订描述/修订日期/备注」+ 子行「修订原因/修订内容」
        data_start = 0
        if children:
            first_cells = children[0].get('children', [])
            first_text = (first_cells[0].get('content', '') if first_cells else '').strip()
            if first_text and not re.match(r'^[A-Za-z]/\d+', first_text) and not re.match(r'^V\d', first_text):
                data_start = 1
                if len(children) > 1:
                    second_cells = children[1].get('children', [])
                    # 第二行为空或为子表头（修订原因/修订内容），则跳过
                    second_texts = [(c.get('content', '') or '').strip() for c in second_cells]
                    if all(not t for t in second_texts):
                        data_start = 2
                    elif any(t in ('修订原因', '修订内容', '修订描述') for t in second_texts):
                        data_start = 2

        header_row = '<tr>' + ''.join(f'<th class="align-center">{h}</th>' for h in tmpl_headers) + '</tr>'

        data_rows_html = []
        for row_node in children[data_start:]:
            if row_node.get('type') != 'table_row':
                continue
            cells = row_node.get('children', [])
            row_data = [self._clean_cell_text(cells[j].get('content', '') or '') if j < len(cells) else ''
                        for j in range(col_count)]
            if not any(v.strip() for v in row_data):
                continue
            aligns = ['center', 'center', 'left', 'left', 'center', 'left']
            cells_html = ''.join(
                self._render_revision_cell(cells, j, row_data[j], aligns[j])
                for j in range(col_count)
            )
            data_rows_html.append(f'<tr>{cells_html}</tr>')

        title_html = '<h2 class="heading heading--2">文件修订履历表</h2>'
        table_html = f'<table class="table table--revision">\n<thead>\n{header_row}\n</thead>\n<tbody>\n' + \
                     "\n".join(data_rows_html) + '\n</tbody>\n</table>'
        return f'{title_html}\n{table_html}'

    def _render_revision_cell(self, cells: list, j: int, content: str,
                               align: str) -> str:
        """渲染修订表单个单元格，保留原始 rowspan/colspan 属性"""
        extra = ''
        if j < len(cells):
            attrs = cells[j].get('attributes', {})
            colspan = attrs.get('colspan', 1)
            rowspan = attrs.get('rowspan', 1)
            if colspan > 1:
                extra += f' colspan="{colspan}"'
            if rowspan > 1:
                extra += f' rowspan="{rowspan}"'
        return f'<td class="align-{align}"{extra}>{self._escape(content)}</td>'

    # ---------- 代码块 & 流程图 ----------

    def _render_code_block(self, node: Dict[str, Any]) -> str:
        content = node.get('content', '')
        language = node.get('attributes', {}).get('language', '')

        # 检测流程图
        if self._flowchart_processor:
            chart_type = self._flowchart_processor.detect_flowchart(content)
            if chart_type:
                return self._render_flowchart(node, chart_type)

        lang_class = f' class="language-{self._escape_attr(language)}"' if language else ''
        lang_label = f'<span class="code-lang">{self._escape(language)}</span>' if language else ''
        return f'<div class="code-block">\n{lang_label}<pre><code{lang_class}>{self._escape(content)}</code></pre>\n</div>'

    def _render_flowchart(self, node: Dict[str, Any], chart_type: str) -> str:
        content = node.get('content', '')
        self._flowchart_counter += 1
        fid = self._flowchart_counter

        # browser 模式：输出 <pre class="mermaid"> 由浏览器端 mermaid.js 渲染
        if self._mermaid_render_mode == 'browser':
            return f'<pre class="mermaid">{self._escape(content)}</pre>'

        # server 模式：预渲染为 base64 图片
        output_dir = Path('output')
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / f'flowchart_{fid}.png'

        success = False
        if self._flowchart_processor:
            success = self._flowchart_processor.render_flowchart(content, chart_type, str(image_path))

        if success and image_path.exists():
            import base64
            with open(image_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = image_path.suffix.lower()
            mime = 'image/svg+xml' if ext == '.svg' else 'image/png'
            self._flowcharts.append({"id": fid, "mime": mime, "data": b64})
            return (
                f'<figure class="flowchart" data-flowchart-id="{fid}">\n'
                f'  <img src="data:{mime};base64,{b64}" alt="图 {fid}">\n'
                f'  <figcaption>图 {fid}</figcaption>\n'
                f'</figure>'
            )
        else:
            return f'<pre class="mermaid">{self._escape(content)}</pre>'

    # ---------- 其他块元素 ----------

    def _render_blockquote(self, node: Dict[str, Any], level: int = 0) -> str:
        children = node.get('children', [])
        parts = []
        for child in children:
            child_type = child.get('type')
            if child_type == 'paragraph':
                content = child.get('content', '')
                segments = child.get('children', [])
                inner = self._inline.render(segments, content)
                parts.append(f"<p>{inner}</p>")
            elif child_type == 'blockquote':
                rendered = self._render_blockquote(child, level + 1)
                if rendered:
                    parts.append(rendered)
            else:
                rendered = self._process_node(child)
                if rendered:
                    parts.append(rendered)
        if not parts:
            return ""
        level_class = f' blockquote--level-{level}' if level > 0 else ''
        return f'<blockquote class="blockquote{level_class}">\n' + "\n".join(parts) + '\n</blockquote>'

    def _render_image(self, node: Dict[str, Any]) -> str:
        src = node.get('attributes', {}).get('src', '')
        alt = node.get('attributes', {}).get('alt', '')
        if not src:
            return ""

        resolved_src = src
        if self._inline_images:
            resolved_src = self._maybe_inline_src(src)

        return f'<figure class="image">\n  <img src="{self._escape_attr(resolved_src)}" alt="{self._escape_attr(alt)}">\n  <figcaption>{self._escape(alt)}</figcaption>\n</figure>'

    def _maybe_inline_src(self, src: str) -> str:
        """如果是本地文件路径，base64 编码为 data URI；否则原样返回"""
        import base64
        import mimetypes
        # 跳过远程 URL 和已内联的 data URI
        if src.startswith(('http://', 'https://', 'data:')):
            return src
        p = Path(src)
        if not p.is_absolute() and self._input_dir:
            p = Path(self._input_dir) / src
        if not p.exists():
            return src
        try:
            mime, _ = mimetypes.guess_type(str(p))
            mime = mime or 'application/octet-stream'
            with open(p, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            return f'data:{mime};base64,{b64}'
        except Exception:
            return src

    def _render_footnote_block(self, node: Dict[str, Any]) -> str:
        children = node.get('children', [])
        if not children:
            return ""
        items = []
        for i, fn in enumerate(children):
            if fn.get('type') != 'footnote':
                continue
            label = fn.get('attributes', {}).get('label', str(i + 1))
            fn_children = fn.get('children', [])
            parts = []
            for c in fn_children:
                if c.get('type') == 'paragraph':
                    content = c.get('content', '')
                    segments = c.get('children', [])
                    parts.append(self._inline.render(segments, content))
            inner = " ".join(parts)
            items.append(f'<li id="fn-{self._escape_attr(label)}" class="footnote-item"><span class="footnote-num">[{i + 1}]</span> {inner}</li>')
        return '<hr class="footnotes-sep">\n<ol class="footnotes">\n' + "\n".join(items) + '\n</ol>'

    def _render_math_block(self, node: Dict[str, Any]) -> str:
        content = node.get('content', '')
        return f'<div class="math math--block">\\[{self._escape(content)}\\]</div>'

    def _render_math_inline_para(self, node: Dict[str, Any]) -> str:
        content = node.get('content', '')
        return f'<p class="math math--inline-block">\\({self._escape(content)}\\)</p>'

    def _render_definition_list(self, node: Dict[str, Any]) -> str:
        items = node.get('children', [])
        parts = []
        for item in items:
            terms = item.get('terms', [])
            term_texts = [self._escape(t.get('content', '')) for t in terms]
            desc = item.get('description', {})
            desc_content = self._escape(desc.get('content', ''))
            if term_texts and desc_content:
                parts.append(f'<dt>{"；".join(term_texts)}</dt>\n<dd>{desc_content}</dd>')
        if not parts:
            return ""
        return '<dl class="definition-list">\n' + "\n".join(parts) + '\n</dl>'

    def _render_raw_html(self, node: Dict[str, Any]) -> str:
        """Preserve raw HTML blocks explicitly instead of silently dropping them."""
        content = node.get('content', '') or ''
        if not content.strip():
            return ""
        return content

    # ---------- 辅助 ----------

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _escape_attr(text: str) -> str:
        return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")

    @staticmethod
    def _slugify(text: str) -> str:
        """生成标题的slug ID"""
        slug = re.sub(r'[^\w一-鿿]+', '-', text.strip())
        return slug.strip('-').lower()
