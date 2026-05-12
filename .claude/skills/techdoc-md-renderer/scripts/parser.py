"""
Markdown解析器
将Markdown文本解析为结构化的AST
"""

from typing import Any, Dict, List, Optional
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.texmath import texmath_plugin
from mdit_py_plugins.deflist import deflist_plugin


class MarkdownParser:
    """Markdown解析器"""

    def __init__(self):
        """
        初始化解析器
        """
        self.md = MarkdownIt()
        # 启用表格支持
        self.md.enable('table')
        # 启用删除线支持
        self.md.enable('strikethrough')
        # 启用脚注支持
        self.md.use(footnote_plugin)
        # 启用数学公式支持
        self.md.use(texmath_plugin)
        # 启用定义列表支持
        self.md.use(deflist_plugin)

    def parse(self, text: str) -> List[Dict[str, Any]]:
        """
        解析Markdown文本

        Args:
            text: Markdown文本内容

        Returns:
            解析后的AST节点列表
        """
        text = self._preprocess_highlight(text)
        text = self._preprocess_pagebreak(text)
        tokens = self.md.parse(text)
        converter = TokenConverter()
        ast = converter.convert(tokens)
        return self._postprocess_pagebreaks(ast)

    @staticmethod
    def _preprocess_highlight(text: str) -> str:
        """将 ==text== 转换为 <mark>text</mark>（仅非代码块区域）"""
        import re
        # 按代码块分割，只处理非代码部分
        parts = re.split(r'(```[\s\S]*?```)', text)
        for i in range(0, len(parts), 2):
            parts[i] = re.sub(r'==([^=\s].*?[^=\s])==', r'<mark>\1</mark>', parts[i])
        return ''.join(parts)

    @staticmethod
    def _preprocess_pagebreak(text: str) -> str:
        """将 <!-- pagebreak --> 转换为 [PAGEBREAK] 标记"""
        import re
        return re.sub(r'<!--\s*pagebreak\s*-->', '[PAGEBREAK]', text)

    @staticmethod
    def _postprocess_pagebreaks(ast: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将内容为 [PAGEBREAK] 的段落节点替换为 pagebreak 节点"""
        result = []
        for node in ast:
            if node.get('type') == 'paragraph' and node.get('content', '').strip() == '[PAGEBREAK]':
                result.append({'type': 'pagebreak', 'content': '', 'children': [], 'attributes': {}})
            elif node.get('type') == 'blockquote':
                node['children'] = MarkdownParser._postprocess_pagebreaks(node['children'])
                result.append(node)
            elif node.get('type') == 'list':
                node['children'] = MarkdownParser._postprocess_pagebreaks(node['children'])
                result.append(node)
            elif node.get('type') == 'list_item':
                node['children'] = MarkdownParser._postprocess_pagebreaks(node['children'])
                result.append(node)
            else:
                result.append(node)
        return result

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析Markdown文件

        Args:
            file_path: Markdown文件路径

        Returns:
            解析后的AST节点列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return self.parse(text)


class TokenConverter:
    """将markdown-it tokens转换为自定义AST"""

    def __init__(self):
        self.tokens = []
        self.pos = 0

    def convert(self, tokens) -> List[Dict[str, Any]]:
        """
        转换token列表为AST节点列表

        Args:
            tokens: markdown-it token列表

        Returns:
            AST节点列表
        """
        self.tokens = tokens
        self.pos = 0
        result = []

        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            node = self._process_token(token)
            if node:
                result.append(node)
            self.pos += 1

        return result

    def _process_token(self, token) -> Optional[Dict[str, Any]]:
        """处理单个token"""
        handler = getattr(self, f'_handle_{token.type}', None)
        if handler:
            return handler(token)
        # 跳过不独立处理的token类型
        if token.type in ('footnote_block_open', 'footnote_block_close',
                          'footnote_open', 'footnote_close', 'footnote_anchor',
                          'math_block_eqno',
                          'dl_close', 'dt_open', 'dt_close', 'dd_open', 'dd_close'):
            return None
        return None

    def _handle_footnote_block_open(self, token) -> Dict[str, Any]:
        """处理脚注块"""
        footnotes = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "footnote_block_close":
                break
            elif token.type == "footnote_open":
                footnote = self._process_footnote()
                if footnote:
                    footnotes.append(footnote)
            self.pos += 1
        return {
            "type": "footnote_block",
            "content": "",
            "children": footnotes,
            "attributes": {}
        }

    def _process_footnote(self) -> Optional[Dict[str, Any]]:
        """处理单个脚注"""
        label = ""
        children = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "footnote_close":
                break
            elif token.type == "footnote_anchor":
                label = token.meta.get("label", "") if token.meta else ""
            elif token.type in ("paragraph_open", "paragraph_close"):
                pass
            elif token.type == "inline":
                children.append({
                    "type": NODE_PARAGRAPH,
                    "content": token.content,
                    "children": self._parse_inline_segments(token),
                    "attributes": {}
                })
            self.pos += 1
        return {
            "type": "footnote",
            "content": label,
            "children": children,
            "attributes": {"label": label}
        }

    def _handle_heading_open(self, token) -> Dict[str, Any]:
        """处理标题开始"""
        level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
        # 获取标题内容（下一个inline token）
        content = ""
        children = []
        if self.pos + 1 < len(self.tokens):
            next_token = self.tokens[self.pos + 1]
            if next_token.type == "inline":
                content = next_token.content
                segments = self._parse_inline_segments(next_token)
                # 如果有格式化的内联内容，存入children
                has_formatting = any(
                    s.get("type") != "text" or s.get("bold") or s.get("italic") or s.get("strikethrough")
                    for s in segments
                )
                if has_formatting:
                    children = segments
                self.pos += 1  # 跳过inline token
        # 跳过heading_close
        self.pos += 1
        return {
            "type": NODE_HEADING,
            "content": content,
            "level": level,
            "children": children,
            "attributes": {}
        }

    def _handle_paragraph_open(self, token) -> Dict[str, Any]:
        """处理段落开始"""
        content = ""
        children = []
        if self.pos + 1 < len(self.tokens):
            next_token = self.tokens[self.pos + 1]
            if next_token.type == "inline":
                # 检查inline token中是否有图片
                if next_token.children:
                    has_image = any(child.type == "image" for child in next_token.children)
                    if has_image:
                        # 如果有图片，返回图片节点而不是段落
                        self.pos += 1  # 跳过inline token
                        self.pos += 1  # 跳过paragraph_close
                        return self._handle_inline(next_token)[0]
                # 解析内联格式段
                segments = self._parse_inline_segments(next_token)
                # 如果只有纯文本，保持content兼容
                if len(segments) == 1 and segments[0].get("type") == "text" and not segments[0].get("bold") and not segments[0].get("italic") and not segments[0].get("strikethrough"):
                    content = segments[0].get("content", "")
                else:
                    children = segments
                    content = next_token.content
                self.pos += 1
        # 跳过paragraph_close
        self.pos += 1
        return {
            "type": NODE_PARAGRAPH,
            "content": content,
            "children": children,
            "attributes": {}
        }

    def _handle_bullet_list_open(self, token) -> Dict[str, Any]:
        """处理无序列表开始"""
        items = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "bullet_list_close":
                break
            elif token.type == "list_item_open":
                item = self._process_list_item()
                if item:
                    items.append(item)
            self.pos += 1
        return {
            "type": NODE_LIST,
            "content": "",
            "children": items,
            "attributes": {"ordered": False}
        }

    def _handle_ordered_list_open(self, token) -> Dict[str, Any]:
        """处理有序列表开始"""
        items = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "ordered_list_close":
                break
            elif token.type == "list_item_open":
                item = self._process_list_item()
                if item:
                    items.append(item)
            self.pos += 1
        return {
            "type": NODE_LIST,
            "content": "",
            "children": items,
            "attributes": {"ordered": True}
        }

    def _process_list_item(self) -> Optional[Dict[str, Any]]:
        """处理列表项"""
        children = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "list_item_close":
                break
            elif token.type == "inline":
                segments = self._parse_inline_segments(token)
                has_formatting = any(
                    s.get("type") not in ("text",) or s.get("bold") or s.get("italic") or s.get("strikethrough")
                    for s in segments
                )
                # 检测任务列表
                task_checked = None
                content = token.content
                stripped = content.lstrip()
                if stripped.startswith('[x] ') or stripped.startswith('[X] '):
                    task_checked = True
                    content = stripped[4:]
                    # 同步更新segments中第一个text段
                    if segments and segments[0].get("type") == "text":
                        seg_text = segments[0].get("content", "").lstrip()
                        if seg_text.startswith('[x] ') or seg_text.startswith('[X] '):
                            segments[0]["content"] = seg_text[4:]
                elif stripped.startswith('[ ] '):
                    task_checked = False
                    content = stripped[4:]
                    if segments and segments[0].get("type") == "text":
                        seg_text = segments[0].get("content", "").lstrip()
                        if seg_text.startswith('[ ] '):
                            segments[0]["content"] = seg_text[4:]

                para_attrs = {}
                if task_checked is not None:
                    para_attrs["task_checked"] = task_checked

                children.append({
                    "type": NODE_PARAGRAPH,
                    "content": content,
                    "children": segments if has_formatting else [],
                    "attributes": para_attrs
                })
            elif token.type in ("bullet_list_open", "ordered_list_open"):
                # 嵌套列表
                node = self._process_token(token)
                if node:
                    children.append(node)
            self.pos += 1
        return {
            "type": NODE_LIST_ITEM,
            "content": "",
            "children": children,
            "attributes": {}
        }

    def _handle_table_open(self, token) -> Dict[str, Any]:
        """处理表格开始"""
        rows = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "table_close":
                break
            elif token.type == "thead_open":
                header = self._process_table_section()
                if header:
                    for row in header:
                        row["is_header"] = True
                    rows.extend(header)
            elif token.type == "tbody_open":
                body = self._process_table_section()
                if body:
                    rows.extend(body)
            self.pos += 1
        return {
            "type": NODE_TABLE,
            "content": "",
            "children": rows,
            "attributes": {}
        }

    def _process_table_section(self) -> List[Dict[str, Any]]:
        """处理表格部分（表头或表体）"""
        rows = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type in ("thead_close", "tbody_close"):
                break
            elif token.type == "tr_open":
                row = self._process_table_row()
                if row:
                    rows.append(row)
            self.pos += 1
        return rows

    def _process_table_row(self) -> Optional[Dict[str, Any]]:
        """处理表格行"""
        cells = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "tr_close":
                break
            elif token.type in ("th_open", "td_open"):
                cell = self._process_table_cell(open_token=token)
                if cell:
                    cells.append(cell)
            self.pos += 1
        return {
            "type": NODE_TABLE_ROW,
            "content": "",
            "children": cells,
            "attributes": {}
        }

    def _process_table_cell(self, open_token=None) -> Optional[Dict[str, Any]]:
        """处理表格单元格"""
        content = ""
        align = ""
        children = []
        if open_token and open_token.attrs:
            style = open_token.attrs.get("style", "")
            if "text-align:" in style:
                align = style.split("text-align:")[1].strip().rstrip(";")
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type in ("th_close", "td_close"):
                break
            elif token.type == "inline":
                content = token.content
                segments = self._parse_inline_segments(token)
                has_formatting = any(
                    s.get("type") != "text" or s.get("bold") or s.get("italic") or s.get("strikethrough")
                    for s in segments
                )
                if has_formatting or len(segments) > 1:
                    children = segments
            self.pos += 1
        return {
            "type": NODE_TABLE_CELL,
            "content": content,
            "children": children,
            "attributes": {"align": align}
        }

    def _handle_fence(self, token) -> Dict[str, Any]:
        """处理代码块"""
        return {
            "type": NODE_CODE_BLOCK,
            "content": token.content,
            "children": [],
            "attributes": {"language": token.info}
        }

    def _handle_code_block(self, token) -> Dict[str, Any]:
        """处理代码块（缩进式）"""
        return {
            "type": NODE_CODE_BLOCK,
            "content": token.content,
            "children": [],
            "attributes": {"language": ""}
        }

    def _handle_blockquote_open(self, token) -> Dict[str, Any]:
        """处理引用开始"""
        children = []
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "blockquote_close":
                break
            node = self._process_token(token)
            if node:
                children.append(node)
            self.pos += 1
        return {
            "type": NODE_BLOCKQUOTE,
            "content": "",
            "children": children,
            "attributes": {}
        }

    def _handle_image(self, token) -> Dict[str, Any]:
        """处理图片"""
        return {
            "type": NODE_IMAGE,
            "content": token.content,
            "children": [],
            "attributes": {
                "src": token.attrGet("src") or "",
                "alt": token.content,
                "title": token.attrGet("title") or ""
            }
        }

    def _handle_hr(self, token) -> Dict[str, Any]:
        """处理分割线"""
        return {
            "type": NODE_HR,
            "content": "",
            "children": [],
            "attributes": {}
        }

    def _handle_math_block(self, token) -> Dict[str, Any]:
        """处理块级数学公式"""
        return {
            "type": NODE_MATH_BLOCK,
            "content": token.content,
            "children": [],
            "attributes": {}
        }

    def _handle_math_inline(self, token) -> Dict[str, Any]:
        """处理内联数学公式（块级回退）"""
        return {
            "type": NODE_MATH_INLINE,
            "content": token.content,
            "children": [],
            "attributes": {}
        }

    def _handle_dl_open(self, token) -> Dict[str, Any]:
        """处理定义列表"""
        items = []
        self.pos += 1
        current_terms = []
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "dl_close":
                break
            elif token.type == "dt_open":
                term = self._process_dt()
                if term:
                    current_terms.append(term)
            elif token.type == "dd_open":
                desc = self._process_dd()
                if desc:
                    items.append({
                        "terms": list(current_terms),
                        "description": desc
                    })
                    current_terms = []
            self.pos += 1
        return {
            "type": NODE_DEF_LIST,
            "content": "",
            "children": items,
            "attributes": {}
        }

    def _process_dt(self) -> Optional[Dict[str, Any]]:
        """处理定义术语"""
        content = ""
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "dt_close":
                break
            elif token.type == "inline":
                content = token.content
            self.pos += 1
        return {"content": content}

    def _process_dd(self) -> Optional[Dict[str, Any]]:
        """处理定义描述"""
        content = ""
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type == "dd_close":
                break
            elif token.type == "inline":
                content = token.content
            self.pos += 1
        return {"content": content}

    def _parse_inline_segments(self, token) -> List[Dict[str, Any]]:
        """
        解析inline token的children为结构化段落内容

        Returns:
            段落节点，children中包含文本段和内联元素
        """
        segments = []
        if not token.children:
            if token.content:
                segments.append({"type": "text", "content": token.content})
            return segments

        bold = False
        italic = False
        strikethrough = False

        children = list(token.children)
        i = 0
        while i < len(children):
            child = children[i]

            if child.type == "html_inline" and not child.content.startswith("</"):
                # 合并碎片化的 HTML 标签（如 <kbd> + text + </kbd>）
                merged = child.content
                i += 1
                while i < len(children):
                    nc = children[i]
                    if nc.type in ("html_inline", "text"):
                        merged += nc.content
                        i += 1
                        if nc.type == "html_inline" and (nc.content.startswith("</") or nc.content.endswith("/>")):
                            break
                    else:
                        break
                parsed = self._parse_html_inline(merged)
                for seg in parsed:
                    if seg.get("type") == "text":
                        if bold: seg["bold"] = True
                        if italic: seg["italic"] = True
                        if strikethrough: seg["strikethrough"] = True
                segments.extend(parsed)
                continue

            if child.type == "strong_open":
                bold = True
            elif child.type == "strong_close":
                bold = False
            elif child.type == "em_open":
                italic = True
            elif child.type == "em_close":
                italic = False
            elif child.type == "s_open":
                strikethrough = True
            elif child.type == "s_close":
                strikethrough = False
            elif child.type == "text":
                segments.append({
                    "type": "text",
                    "content": child.content,
                    "bold": bold,
                    "italic": italic,
                    "strikethrough": strikethrough,
                })
            elif child.type == "code_inline":
                segments.append({
                    "type": "code_inline",
                    "content": child.content,
                })
            elif child.type == "link_open":
                href = child.attrGet("href") or ""
                title = child.attrGet("title") or ""
                segments.append({
                    "type": "link_start",
                    "href": href,
                    "title": title,
                })
            elif child.type == "link_close":
                segments.append({"type": "link_end"})
            elif child.type == "image":
                segments.append({
                    "type": NODE_IMAGE,
                    "content": child.content,
                    "children": [],
                    "attributes": {
                        "src": child.attrGet("src") or "",
                        "alt": child.content,
                        "title": child.attrGet("title") or ""
                    }
                })
            elif child.type == "footnote_ref":
                label = child.meta.get("label", "") if child.meta else ""
                segments.append({"type": "footnote_ref", "label": label})
            elif child.type == "softbreak":
                segments.append({"type": "softbreak"})
            elif child.type == "hardbreak":
                segments.append({"type": "hardbreak"})
            elif child.type == "math_inline":
                segments.append({"type": "math_inline", "content": child.content})
            elif child.type == "html_inline":
                segments.extend(self._parse_html_inline(child.content))

            i += 1

        return self._merge_link_segments(segments)

    def _parse_html_inline(self, raw_html: str) -> List[Dict[str, Any]]:
        """解析HTML内联标签为结构化段"""
        import re
        segments = []
        remaining = raw_html
        patterns = [
            (r'<kbd>(.*?)</kbd>', 'kbd'),
            (r'<sub>(.*?)</sub>', 'sub'),
            (r'<sup>(.*?)</sup>', 'sup'),
            (r'<mark>(.*?)</mark>', 'highlight'),
            (r'<del>(.*?)</del>', 'strikethrough_text'),
            (r'<ins>(.*?)</ins>', 'underline_text'),
            (r'<u>(.*?)</u>', 'underline_text'),
            (r'<em>(.*?)</em>', 'italic_text'),
            (r'<strong>(.*?)</strong>', 'bold_text'),
            (r'<code>(.*?)</code>', 'code_inline'),
            (r'<br\s*/?>', 'hardbreak'),
        ]
        for pattern, seg_type in patterns:
            parts = re.split(pattern, remaining, flags=re.DOTALL)
            new_remaining = []
            for idx, part in enumerate(parts):
                if idx % 2 == 0:
                    # 非匹配部分
                    if part.strip():
                        new_remaining.append(part)
                else:
                    # 匹配的标签内容
                    if seg_type == 'hardbreak':
                        segments.append({"type": "hardbreak"})
                    elif seg_type == 'strikethrough_text':
                        segments.append({"type": "text", "content": part, "bold": False, "italic": False, "strikethrough": True})
                    elif seg_type == 'underline_text':
                        segments.append({"type": "text", "content": part, "bold": False, "italic": False, "strikethrough": False, "underline": True})
                    elif seg_type == 'italic_text':
                        segments.append({"type": "text", "content": part, "bold": False, "italic": True, "strikethrough": False})
                    elif seg_type == 'bold_text':
                        segments.append({"type": "text", "content": part, "bold": True, "italic": False, "strikethrough": False})
                    else:
                        segments.append({"type": seg_type, "content": part})
            remaining = ''.join(new_remaining)
        # 剩余纯文本
        if remaining.strip():
            segments.insert(0, {"type": "text", "content": remaining.strip()})
        return segments

    def _merge_link_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将link_start/link_end之间的段合并为单个link节点"""
        merged = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg.get("type") == "link_start":
                # 收集链接内的文本
                link_text_parts = []
                href = seg.get("href", "")
                title = seg.get("title", "")
                i += 1
                while i < len(segments) and segments[i].get("type") != "link_end":
                    s = segments[i]
                    if s.get("type") in ("text", "code_inline"):
                        link_text_parts.append(s.get("content", ""))
                    i += 1
                merged.append({
                    "type": "link",
                    "content": "".join(link_text_parts),
                    "href": href,
                    "title": title,
                })
            elif seg.get("type") == "link_end":
                pass  # 已在link_start中处理
            else:
                merged.append(seg)
            i += 1
        return merged

    def _handle_inline(self, token) -> List[Dict[str, Any]]:
        """处理内联内容"""
        # 处理inline token中的子元素
        result = []
        if token.children:
            for child in token.children:
                if child.type == "image":
                    result.append({
                        "type": NODE_IMAGE,
                        "content": child.content,
                        "children": [],
                        "attributes": {
                            "src": child.attrGet("src") or "",
                            "alt": child.content,
                            "title": child.attrGet("title") or ""
                        }
                    })
        return result


# 节点类型常量
NODE_HEADING = "heading"
NODE_PARAGRAPH = "paragraph"
NODE_LIST = "list"
NODE_LIST_ITEM = "list_item"
NODE_TABLE = "table"
NODE_TABLE_ROW = "table_row"
NODE_TABLE_CELL = "table_cell"
NODE_CODE_BLOCK = "code_block"
NODE_BLOCKQUOTE = "blockquote"
NODE_IMAGE = "image"
NODE_LINK = "link"
NODE_STRONG = "strong"
NODE_EM = "em"
NODE_HR = "hr"
NODE_MATH_BLOCK = "math_block"
NODE_MATH_INLINE = "math_inline"
NODE_DEF_LIST = "definition_list"


class MarkdownNode:
    """Markdown AST节点基类"""

    def __init__(self, node_type: str, content: str = "", **kwargs):
        """
        初始化节点

        Args:
            node_type: 节点类型（heading, paragraph, list, table等）
            content: 节点内容
            **kwargs: 其他属性
        """
        self.type = node_type
        self.content = content
        self.children: List['MarkdownNode'] = []
        self.attributes: Dict[str, Any] = kwargs

    def add_child(self, child: 'MarkdownNode'):
        """添加子节点"""
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'content': self.content,
            'children': [child.to_dict() for child in self.children],
            'attributes': self.attributes
        }