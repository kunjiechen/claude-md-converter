"""
PDF文档转换器
将Markdown AST转换为PDF文档
"""

from typing import Any, Dict, List
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .converter import BaseConverter
from .parser import MarkdownParser


class PDFConverter(BaseConverter):
    """PDF文档转换器"""

    def __init__(self, **options):
        """
        初始化PDF转换器

        Args:
            **options: 转换选项
                - output_dir: 输出目录
                - page_size: 页面大小（A4, Letter等）
                - margin: 页边距
                - font: 默认字体
                - font_size: 默认字号
                - css_template: 自定义CSS模板路径（预留）
        """
        super().__init__(**options)
        self.page_size = options.get('page_size', 'A4')
        self.margin = options.get('margin', '2.5cm')
        self.font = options.get('font', '宋体')
        self.font_size = options.get('font_size', 12)
        self.css_template = options.get('css_template')  # 预留模板接口

    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """
        将AST转换为PDF文档

        Args:
            ast: Markdown AST节点列表
            output_path: 输出PDF文件路径

        Returns:
            转换是否成功
        """
        try:
            # 转换AST为HTML
            html_content = self._convert_ast_to_html(ast)

            # 生成完整HTML
            full_html = self._generate_full_html(html_content)

            # 获取CSS样式
            css_content = self._get_css_style()

            # 配置字体
            font_config = FontConfiguration()

            # 生成PDF
            HTML(string=full_html).write_pdf(
                output_path,
                stylesheets=[CSS(string=css_content)],
                font_config=font_config
            )

            self.log(f"PDF文档已生成: {output_path}")
            return True

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def convert_file(self, input_path: str, output_path: str) -> bool:
        """
        转换Markdown文件为PDF文档

        Args:
            input_path: 输入Markdown文件路径
            output_path: 输出PDF文件路径

        Returns:
            转换是否成功
        """
        try:
            # 验证输入文件
            self.validate_input(input_path)

            # 解析Markdown
            parser = MarkdownParser()
            ast = parser.parse_file(input_path)

            # 转换为PDF
            return self.convert(ast, output_path)

        except Exception as e:
            self.log(f"转换失败: {e}", "error")
            return False

    def _convert_ast_to_html(self, ast: List[Dict[str, Any]]) -> str:
        """
        将AST转换为HTML

        Args:
            ast: AST节点列表

        Returns:
            HTML字符串
        """
        html_parts = []
        for node in ast:
            html_parts.append(self._process_node(node))
        return '\n'.join(html_parts)

    def _process_node(self, node: Dict[str, Any]) -> str:
        """
        处理AST节点

        Args:
            node: AST节点

        Returns:
            HTML字符串
        """
        node_type = node.get('type')

        if node_type == 'heading':
            return self._process_heading(node)
        elif node_type == 'paragraph':
            return self._process_paragraph(node)
        elif node_type == 'list':
            return self._process_list(node)
        elif node_type == 'table':
            return self._process_table(node)
        elif node_type == 'code_block':
            return self._process_code_block(node)
        elif node_type == 'blockquote':
            return self._process_blockquote(node)
        elif node_type == 'image':
            return self._process_image(node)
        elif node_type == 'hr':
            return self._process_hr(node)
        elif node_type == 'math_block':
            return self._process_math_block(node)
        elif node_type == 'definition_list':
            return self._process_definition_list(node)
        elif node_type == 'footnote_block':
            return self._process_footnote_block(node)
        else:
            return ''

    def _render_inline_segments(self, segments: List[Dict[str, Any]], plain_text: str) -> str:
        """将内联格式段渲染为HTML"""
        if not segments:
            return self._escape_html(plain_text)

        html_parts = []
        for seg in segments:
            seg_type = seg.get('type', 'text')

            if seg_type == 'text':
                text = self._escape_html(seg.get('content', ''))
                if seg.get('bold'):
                    text = f'<strong>{text}</strong>'
                if seg.get('italic'):
                    text = f'<em>{text}</em>'
                if seg.get('strikethrough'):
                    text = f'<del>{text}</del>'
                if seg.get('underline'):
                    text = f'<u>{text}</u>'
                html_parts.append(text)

            elif seg_type == 'code_inline':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<code>{text}</code>')

            elif seg_type == 'link':
                text = self._escape_html(seg.get('content', ''))
                href = seg.get('href', '')
                title = seg.get('title', '')
                title_attr = f' title="{title}"' if title else ''
                html_parts.append(f'<a href="{href}"{title_attr}>{text}</a>')

            elif seg_type == 'footnote_ref':
                label = seg.get('label', '')
                html_parts.append(f'<sup><a href="#fn-{label}">[{label}]</a></sup>')

            elif seg_type == 'math_inline':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<span class="math-inline">${text}$</span>')

            elif seg_type == 'kbd':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<kbd>{text}</kbd>')

            elif seg_type == 'sub':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<sub>{text}</sub>')

            elif seg_type == 'sup':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<sup>{text}</sup>')

            elif seg_type == 'highlight':
                text = self._escape_html(seg.get('content', ''))
                html_parts.append(f'<mark>{text}</mark>')

            elif seg_type == 'softbreak':
                html_parts.append('<br>')
            elif seg_type == 'hardbreak':
                html_parts.append('<br>')

        return ''.join(html_parts)

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义HTML特殊字符"""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def _process_heading(self, node: Dict[str, Any]) -> str:
        """处理标题"""
        level = node.get('level', 1)
        segments = node.get('children', [])
        content = node.get('content', '')
        inner = self._render_inline_segments(segments, content)
        return f'<h{level}>{inner}</h{level}>'

    def _process_paragraph(self, node: Dict[str, Any]) -> str:
        """处理段落"""
        segments = node.get('children', [])
        content = node.get('content', '')
        inner = self._render_inline_segments(segments, content)
        return f'<p>{inner}</p>'

    def _process_list(self, node: Dict[str, Any]) -> str:
        """处理列表"""
        children = node.get('children', [])
        ordered = node.get('attributes', {}).get('ordered', False)

        tag = 'ol' if ordered else 'ul'
        items_html = []

        for item in children:
            if item.get('type') == 'list_item':
                item_content = self._get_list_item_content(item)
                items_html.append(f'<li>{item_content}</li>')

                # 处理嵌套列表
                for child in item.get('children', []):
                    if child.get('type') == 'list':
                        items_html.append(self._process_list(child))

        return f'<{tag}>{"".join(items_html)}</{tag}>'

    def _get_list_item_content(self, node: Dict[str, Any]) -> str:
        """获取列表项内容"""
        content_parts = []
        for child in node.get('children', []):
            if child.get('type') == 'paragraph':
                segments = child.get('children', [])
                content = child.get('content', '')
                content_parts.append(self._render_inline_segments(segments, content))
        return ' '.join(content_parts)

    def _process_table(self, node: Dict[str, Any]) -> str:
        """处理表格"""
        children = node.get('children', [])

        if not children:
            return ''

        rows_html = []
        for i, row_node in enumerate(children):
            cells_html = []
            for cell_node in row_node.get('children', []):
                segments = cell_node.get('children', [])
                content = cell_node.get('content', '')
                cell_inner = self._render_inline_segments(segments, content)
                align = cell_node.get('attributes', {}).get('align', '')
                align_attr = f' style="text-align:{align}"' if align else ''
                if i == 0:  # 表头
                    cells_html.append(f'<th{align_attr}>{cell_inner}</th>')
                else:
                    cells_html.append(f'<td{align_attr}>{cell_inner}</td>')
            rows_html.append(f'<tr>{"".join(cells_html)}</tr>')

        return f'<table>{"".join(rows_html)}</table>'

    def _process_code_block(self, node: Dict[str, Any]) -> str:
        """处理代码块"""
        content = node.get('content', '')
        language = node.get('attributes', {}).get('language', '')

        # 转义HTML特殊字符
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        if language:
            return f'<pre><code class="language-{language}">{content}</code></pre>'
        else:
            return f'<pre><code>{content}</code></pre>'

    def _process_blockquote(self, node: Dict[str, Any]) -> str:
        """处理引用"""
        children = node.get('children', [])
        content_html = []

        for child in children:
            child_type = child.get('type')
            if child_type == 'paragraph':
                segments = child.get('children', [])
                content = child.get('content', '')
                inner = self._render_inline_segments(segments, content)
                content_html.append(f'<p>{inner}</p>')
            elif child_type in ('heading', 'code_block', 'table', 'list'):
                content_html.append(self._process_node(child))

        return f'<blockquote>{"".join(content_html)}</blockquote>'

    def _process_image(self, node: Dict[str, Any]) -> str:
        """处理图片"""
        src = node.get('attributes', {}).get('src', '')
        alt = node.get('attributes', {}).get('alt', '')

        if src:
            return f'<img src="{src}" alt="{alt}" />'
        return ''

    def _process_hr(self, node: Dict[str, Any]) -> str:
        """处理分割线"""
        return '<hr />'

    def _process_math_block(self, node: Dict[str, Any]) -> str:
        """处理块级数学公式"""
        content = self._escape_html(node.get('content', ''))
        return f'<div class="math-block">$${content}$$</div>'

    def _process_definition_list(self, node: Dict[str, Any]) -> str:
        """处理定义列表"""
        items = node.get('children', [])
        parts = ['<dl>']
        for item in items:
            for term in item.get('terms', []):
                parts.append(f'<dt>{self._escape_html(term.get("content", ""))}</dt>')
            desc = item.get('description', {})
            if desc.get('content'):
                parts.append(f'<dd>{self._escape_html(desc.get("content", ""))}</dd>')
        parts.append('</dl>')
        return ''.join(parts)

    def _process_footnote_block(self, node: Dict[str, Any]) -> str:
        """处理脚注块"""
        children = node.get('children', [])
        if not children:
            return ''
        parts = ['<hr><section class="footnotes"><ol>']
        for i, fn in enumerate(children):
            if fn.get('type') != 'footnote':
                continue
            label = fn.get('attributes', {}).get('label', str(i + 1))
            content_parts = []
            for child in fn.get('children', []):
                if child.get('type') == 'paragraph':
                    segments = child.get('children', [])
                    text = child.get('content', '')
                    content_parts.append(self._render_inline_segments(segments, text))
            parts.append(f'<li id="fn-{label}">{" ".join(content_parts)}</li>')
        parts.append('</ol></section>')
        return ''.join(parts)

    def _generate_full_html(self, content: str) -> str:
        """
        生成完整HTML文档

        Args:
            content: HTML内容

        Returns:
            完整HTML文档
        """
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Markdown转换文档</title>
</head>
<body>
{content}
</body>
</html>'''

    def _get_css_style(self) -> str:
        """
        获取CSS样式

        Returns:
            CSS样式字符串
        """
        # 如果有自定义CSS模板，使用自定义模板
        if self.css_template:
            try:
                with open(self.css_template, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                self.log(f"读取CSS模板失败: {e}，使用默认样式", "warning")

        # 默认CSS样式
        return self._generate_default_css()

    def _generate_default_css(self) -> str:
        """
        生成默认CSS样式

        Returns:
            CSS样式字符串
        """
        return f'''
@page {{
    size: {self.page_size};
    margin: {self.margin};

    @top-center {{
        content: "";
    }}

    @bottom-center {{
        content: "第 " counter(page) " 页";
    }}
}}

body {{
    font-family: "{self.font}", "SimSun", "宋体", sans-serif;
    font-size: {self.font_size}pt;
    line-height: 1.6;
    color: #333;
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: "黑体", "SimHei", sans-serif;
    color: #2c3e50;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
}}

h1 {{
    font-size: 24pt;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.3em;
}}

h2 {{
    font-size: 18pt;
    border-bottom: 1px solid #bdc3c7;
    padding-bottom: 0.2em;
}}

h3 {{
    font-size: 14pt;
}}

h4 {{
    font-size: 12pt;
}}

h5 {{
    font-size: 11pt;
}}

h6 {{
    font-size: 10pt;
    color: #7f8c8d;
}}

p {{
    margin-bottom: 1em;
    text-align: justify;
}}

ul, ol {{
    margin-bottom: 1em;
    padding-left: 2em;
}}

li {{
    margin-bottom: 0.3em;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 1em;
    page-break-inside: avoid;
}}

th, td {{
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}}

th {{
    background-color: #f2f2f2;
    font-weight: bold;
}}

tr:nth-child(even) {{
    background-color: #f9f9f9;
}}

code {{
    font-family: "Courier New", "Consolas", monospace;
    background-color: #f4f4f4;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 0.9em;
}}

pre {{
    background-color: #f8f8f8;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 1em;
    margin-bottom: 1em;
    overflow-x: auto;
    page-break-inside: avoid;
}}

pre code {{
    background-color: transparent;
    padding: 0;
    border-radius: 0;
}}

blockquote {{
    border-left: 4px solid #3498db;
    padding-left: 1em;
    margin-left: 0;
    margin-bottom: 1em;
    color: #555;
    font-style: italic;
}}

img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}}

hr {{
    border: none;
    border-top: 1px solid #ddd;
    margin: 2em 0;
}}

a {{
    color: #3498db;
    text-decoration: none;
}}

a:hover {{
    text-decoration: underline;
}}

kbd {{
    font-family: "Courier New", monospace;
    background-color: #EBEBEB;
    border: 1px solid #A0A0A0;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: 0.9em;
}}

mark {{
    background-color: #FFFF00;
    padding: 1px 2px;
}}

.math-inline, .math-block {{
    font-family: "Cambria Math", "Times New Roman", serif;
    font-style: italic;
    background-color: #F0F4FF;
    padding: 2px 4px;
}}

.math-block {{
    display: block;
    text-align: center;
    padding: 1em;
    margin: 1em 0;
    border-left: 3px solid #4472C4;
}}

dl {{
    margin: 1em 0;
}}

dt {{
    font-weight: bold;
    margin-top: 0.5em;
}}

dd {{
    margin-left: 2em;
    margin-bottom: 0.5em;
}}

.footnotes {{
    font-size: 0.9em;
    color: #666;
    border-top: 1px solid #ddd;
    margin-top: 2em;
    padding-top: 0.5em;
}}
'''