"""
Markdown解析器
将Markdown文本解析为结构化的AST
"""

from typing import Any, Dict, List, Optional
from markdown_it import MarkdownIt


class MarkdownParser:
    """Markdown解析器"""

    def __init__(self):
        """
        初始化解析器
        """
        self.md = MarkdownIt()
        # 启用表格支持
        self.md.enable('table')

    def parse(self, text: str) -> List[Dict[str, Any]]:
        """
        解析Markdown文本

        Args:
            text: Markdown文本内容

        Returns:
            解析后的AST节点列表
        """
        tokens = self.md.parse(text)
        converter = TokenConverter()
        return converter.convert(tokens)

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
        return None

    def _handle_heading_open(self, token) -> Dict[str, Any]:
        """处理标题开始"""
        level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
        # 获取标题内容（下一个inline token）
        content = ""
        if self.pos + 1 < len(self.tokens):
            next_token = self.tokens[self.pos + 1]
            if next_token.type == "inline":
                content = next_token.content
                self.pos += 1  # 跳过inline token
        # 跳过heading_close
        self.pos += 1
        return {
            "type": NODE_HEADING,
            "content": content,
            "level": level,
            "children": [],
            "attributes": {}
        }

    def _handle_paragraph_open(self, token) -> Dict[str, Any]:
        """处理段落开始"""
        # token参数用于接口一致性，内容在inline token中
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
                children.append({
                    "type": NODE_PARAGRAPH,
                    "content": token.content,
                    "children": [],
                    "attributes": {}
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
                cell = self._process_table_cell()
                if cell:
                    cells.append(cell)
            self.pos += 1
        return {
            "type": NODE_TABLE_ROW,
            "content": "",
            "children": cells,
            "attributes": {}
        }

    def _process_table_cell(self) -> Optional[Dict[str, Any]]:
        """处理表格单元格"""
        content = ""
        self.pos += 1
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.type in ("th_close", "td_close"):
                break
            elif token.type == "inline":
                content = token.content
            self.pos += 1
        return {
            "type": NODE_TABLE_CELL,
            "content": content,
            "children": [],
            "attributes": {}
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
        # token参数用于接口一致性
        return {
            "type": NODE_HR,
            "content": "",
            "children": [],
            "attributes": {}
        }

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