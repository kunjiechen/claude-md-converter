"""AST → HTML 主渲染器

将Markdown AST节点列表转换为语义化HTML字符串。
每个节点类型输出带CSS class的HTML元素，供CSS统一控制样式。
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import re

from .inline_renderer import InlineRenderer
from .context import RenderContext


class HtmlRenderer:
    """AST → HTML 渲染器"""

    # 修订记录表检测关键字
    REVISION_HEADER_KEYWORDS = ['版次', '修订人', '修订日期', '修订内容', '修订原因', '修订描述', '备注']

    def __init__(self, flowchart_processor=None):
        self._inline = InlineRenderer()
        self._toc_html = ""
        self._revision_html = ""
        self._flowcharts = []
        self._flowchart_counter = 0
        self._footnote_counter = 0
        self._input_dir = None
        self._flowchart_processor = flowchart_processor

    def render(self, ast: List[Dict[str, Any]], context: RenderContext = None) -> str:
        """将AST渲染为完整HTML文档（body部分）"""
        if context is None:
            context = RenderContext()

        self._flowcharts = []
        self._flowchart_counter = 0
        self._footnote_counter = 0

        # 第一遍：扫描识别TOC表和修订记录表
        toc_table_idx = -1
        revision_table_idx = -1
        for i, node in enumerate(ast):
            if node.get('type') == 'table':
                if toc_table_idx < 0 and self._is_toc_table_node(node):
                    toc_table_idx = i
                elif revision_table_idx < 0 and self._is_revision_table_node(node):
                    revision_table_idx = i

        # 第二遍：渲染节点
        body_parts = []
        for i, node in enumerate(ast):
            if i == toc_table_idx:
                continue  # TOC由模板层处理
            if i == revision_table_idx:
                self._revision_html = self._render_revision_table(node)
                # 跳过修订表前面的修订标题（避免与 _add_revision_section 重复）
                if i > 0:
                    prev = ast[i - 1]
                    if prev.get('type') == 'heading' and self._is_revision_heading(prev.get('content', '')):
                        # 从 body_parts 中移除该标题
                        heading_html = self._process_node(prev)
                        if heading_html in body_parts:
                            body_parts.remove(heading_html)
                continue
            html = self._process_node(node)
            if html:
                body_parts.append(html)

        context.body_html = "\n".join(body_parts)
        # 若md未显式提供目录表，则从标题自动生成
        if toc_table_idx < 0 and not self._toc_html:
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
        return ""

    # ---------- 标题 ----------

    def _render_heading(self, node: Dict[str, Any]) -> str:
        level = min(node.get('level', 1), 6)
        content = node.get('content', '')
        segments = node.get('children', [])
        inner = self._inline.render(segments, content)
        tag = f"h{level}"
        return f'<{tag} class="heading heading--{level}" id="{self._slugify(content)}">{inner}</{tag}>'

    # ---------- 段落 ----------

    def _render_paragraph(self, node: Dict[str, Any]) -> str:
        content = node.get('content', '')
        segments = node.get('children', [])
        inner = self._inline.render(segments, content)
        if not inner.strip():
            return ""
        return f'<p class="paragraph">{inner}</p>'

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

        # 优先使用 AST 中的 is_header 标记（来自 markdown-it thead 解析）
        has_header = any(r.get('is_header') for r in valid_rows)
        if not has_header:
            has_header = self._is_likely_header(valid_rows)
        cols = max(len(r.get('children', [])) for r in valid_rows)
        col_types = self._classify_columns(valid_rows, cols, 1 if has_header else 0)

        rows_html = []
        for i, row_node in enumerate(valid_rows):
            cells = row_node.get('children', [])
            # 优先用 AST 标记，其次用首行推断
            is_header = row_node.get('is_header', False) or (has_header and i == 0)
            cell_tag = "th" if is_header else "td"
            cells_html = []
            for j, cell_node in enumerate(cells):
                if j >= cols:
                    break
                align = self._get_cell_align(cell_node, col_types[j] if j < len(col_types) else 'general', is_header)
                raw = cell_node.get('content', '') or ''
                clean = self._clean_cell_text(raw)
                segments = cell_node.get('children', [])
                inner = self._inline.render(segments, clean)
                classes = f"align-{align}"
                cells_html.append(f'<{cell_tag} class="{classes}">{inner}</{cell_tag}>')
            rows_html.append(f'<tr>{"".join(cells_html)}</tr>')

        return f'<table class="table table--data">\n<thead>\n{rows_html[0]}\n</thead>\n<tbody>\n' + \
               "\n".join(rows_html[1:]) + '\n</tbody>\n</table>' if has_header else \
               f'<table class="table table--data">\n<tbody>\n' + "\n".join(rows_html) + '\n</tbody>\n</table>'

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
        if len(rows) < 2:
            return False
        first = rows[0].get('children', [])
        rest = rows[1].get('children', [])
        if not first or not rest:
            return False
        first_lens = [len(self._clean_cell_text(c.get('content', '') or '')) for c in first]
        rest_lens = [len(self._clean_cell_text(c.get('content', '') or '')) for c in rest]
        first_avg = sum(first_lens) / max(len(first_lens), 1)
        rest_avg = sum(rest_lens) / max(len(rest_lens), 1)
        # 第一行是短标签且数据行显著更长 → 表头
        if first_avg <= 20 and rest_avg > 0 and first_avg < rest_avg * 0.6:
            return True
        return False

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

    def _generate_toc_from_headings(self, ast: List[Dict]) -> str:
        """从AST标题节点自动生成目录HTML"""
        headings = [n for n in ast if n.get('type') == 'heading' and n.get('level', 1) <= 4]
        if len(headings) < 2:
            return ""
        items = []
        for h in headings:
            level = h.get('level', 1)
            content = self._clean_heading_text(h.get('content', ''))
            slug = self._slugify(content)
            indent = "  " * (level - 1)
            items.append(f'{indent}<li class="toc-item toc-level-{level}">'
                         f'<a href="#{slug}">{self._escape(content)}</a></li>')
        return '<ul class="toc-list">\n' + "\n".join(items) + '\n</ul>'

    @staticmethod
    def _is_revision_heading(text: str) -> bool:
        """检测标题是否为修订记录相关（避免与自动生成的修订表重复）"""
        keywords = ['修订', '履历', '变更', '修改记录', '版本历史']
        return any(kw in text for kw in keywords)

    @staticmethod
    def _clean_heading_text(text: str) -> str:
        """去除标题中的 Markdown 格式标记（**bold**、*italic*、`code` 等）"""
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'~~(.+?)~~', r'\1', text)
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

        # 确定数据起始行
        data_start = 0
        if children:
            first_cells = children[0].get('children', [])
            first_text = (first_cells[0].get('content', '') if first_cells else '').strip()
            if first_text and not re.match(r'^[A-Za-z]/\d+', first_text) and not re.match(r'^V\d', first_text):
                data_start = 1
                if len(children) > 1:
                    second_cells = children[1].get('children', [])
                    if all(not (c.get('content', '') or '').strip() for c in second_cells):
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
                f'<td class="align-{aligns[j]}">{self._escape(row_data[j])}</td>'
                for j in range(col_count)
            )
            data_rows_html.append(f'<tr>{cells_html}</tr>')

        title_html = '<h2 class="heading heading--2">文件修订履历表</h2>'
        table_html = f'<table class="table table--revision">\n<thead>\n{header_row}\n</thead>\n<tbody>\n' + \
                     "\n".join(data_rows_html) + '\n</tbody>\n</table>'
        return f'{title_html}\n{table_html}'

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

    def _render_blockquote(self, node: Dict[str, Any]) -> str:
        children = node.get('children', [])
        parts = []
        for child in children:
            child_type = child.get('type')
            if child_type == 'paragraph':
                content = child.get('content', '')
                segments = child.get('children', [])
                inner = self._inline.render(segments, content)
                parts.append(f"<p>{inner}</p>")
            else:
                rendered = self._process_node(child)
                if rendered:
                    parts.append(rendered)
        if not parts:
            return ""
        return f'<blockquote class="blockquote">\n' + "\n".join(parts) + '\n</blockquote>'

    def _render_image(self, node: Dict[str, Any]) -> str:
        src = node.get('attributes', {}).get('src', '')
        alt = node.get('attributes', {}).get('alt', '')
        if not src:
            return ""
        return f'<figure class="image">\n  <img src="{self._escape_attr(src)}" alt="{self._escape_attr(alt)}">\n  <figcaption>{self._escape(alt)}</figcaption>\n</figure>'

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
