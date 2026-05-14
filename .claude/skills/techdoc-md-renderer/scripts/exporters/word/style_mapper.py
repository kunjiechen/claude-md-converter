"""CSS class → Word 样式映射

将 HTML 元素的 CSS class 映射为 Word 样式名和格式覆盖。
正文段落（p/blockquote/pre/dl）默认映射到「正文2」样式，
更精确的样式由 classify_paragraph() 根据内容决定。
"""

from typing import Dict, Optional, Tuple
from bs4 import Tag


# 块级元素 → Word 样式名（默认值，更精确的分类见 classify_paragraph）
ELEMENT_STYLE_MAP: Dict[Tuple[str, ...], str] = {
    ('h1',): 'Heading 1',
    ('h2',): 'Heading 2',
    ('h3',): 'Heading 3',
    ('h4',): 'Heading 4',
    ('h5',): 'Heading 5',
    ('h6',): 'Heading 6',
    ('p',): '正文2',
    ('blockquote',): '正文2',
    ('pre',): '正文2',
    ('dl',): '正文2',
}

# 表格 class → Word 表格样式名
TABLE_CLASS_MAP: Dict[str, str] = {
    'table--data': 'Table Grid',
    'table--revision': 'Table Grid',
    'table--params': 'Table Grid',
    'table--defs': 'Table Grid',
}

# 表格对齐 class → Word 对齐常量
ALIGN_MAP: Dict[str, int] = {
    'align-left': 0,    # WD_ALIGN_PARAGRAPH.LEFT
    'align-center': 1,  # WD_ALIGN_PARAGRAPH.CENTER
    'align-right': 2,   # WD_ALIGN_PARAGRAPH.RIGHT
}


class StyleMapper:
    """将 HTML 元素及其 CSS class 映射为 Word 样式和格式选项"""

    @classmethod
    def get_paragraph_style(cls, tag: Tag) -> Optional[str]:
        """根据 HTML 标签获取 Word 段落样式名"""
        tag_name = tag.name.lower() if hasattr(tag, 'name') else tag
        for tags, style in ELEMENT_STYLE_MAP.items():
            if tag_name in tags:
                return style
        return 'Normal'

    @classmethod
    def get_table_style(cls, tag: Tag) -> Optional[str]:
        """根据 table 的 CSS class 获取 Word 表格样式名"""
        if tag.name != 'table':
            return None
        classes = tag.get('class', [])
        for cls_name in classes:
            if cls_name in TABLE_CLASS_MAP:
                return TABLE_CLASS_MAP[cls_name]
        return 'Table Grid'

    @classmethod
    def get_alignment(cls, tag: Tag) -> Optional[int]:
        """从标签的 CSS class 中提取对齐方式"""
        classes = tag.get('class', [])
        for cls_name in classes:
            if cls_name in ALIGN_MAP:
                return ALIGN_MAP[cls_name]
        return None

    @classmethod
    def is_bold(cls, tag: Tag) -> bool:
        """检查是否为 <strong> 或 <th>"""
        return tag.name == 'strong' or tag.name == 'th'

    @classmethod
    def is_italic(cls, tag: Tag) -> bool:
        """检查是否为 <em>"""
        return tag.name == 'em'

    @classmethod
    def is_strikethrough(cls, tag: Tag) -> bool:
        """检查是否为 <del>"""
        return tag.name == 'del'

    @classmethod
    def is_underline(cls, tag: Tag) -> bool:
        """检查是否为 <ins>"""
        return tag.name == 'ins'

    @classmethod
    def is_code_inline(cls, tag: Tag) -> bool:
        """检查是否为内联代码"""
        return tag.name == 'code' and 'code-inline' in tag.get('class', [])

    @classmethod
    def is_code_block(cls, tag: Tag) -> bool:
        """检查是否为代码块"""
        if tag.name == 'div' and 'code-block' in tag.get('class', []):
            return True
        if tag.name == 'pre':
            return True
        return False

    @classmethod
    def is_flowchart(cls, tag: Tag) -> bool:
        """检查是否为流程图 figure"""
        return tag.name == 'figure' and 'flowchart' in tag.get('class', [])

    @classmethod
    def get_table_classes(cls, tag: Tag) -> list:
        """获取表格的 CSS class 列表"""
        return tag.get('class', [])

    @classmethod
    def classify_paragraph(cls, tag: Tag) -> str:
        """根据 HTML 段落内容和结构返回精确的 Word 样式名。
        委托给 style_config.classify_paragraph() 执行内容分析。
        """
        from .style_config import classify_paragraph as _classify
        return _classify(tag)

    @classmethod
    def classify_code_block(cls, code_text: str) -> Optional[str]:
        """判断代码块内容是否为规范语法条目。
        委托给 style_config.classify_code_block() 执行模式匹配。
        """
        from .style_config import classify_code_block as _classify
        return _classify(code_text)

    @classmethod
    def classify_code_line(cls, text: str) -> str:
        """对代码块中的单行分类，返回样式名。
        委托给 style_config.classify_code_line() 执行判断。
        """
        from .style_config import classify_code_line as _classify
        return _classify(text)

    @classmethod
    def is_thead_row(cls, tag: Tag) -> bool:
        """检查 tr 是否在 thead 中"""
        return tag.parent and tag.parent.name == 'thead'

    @classmethod
    def cell_collector(cls, row_tag: Tag, is_header: bool):
        """遍历行中的 cell（th 或 td），yield 各 cell 信息"""
        tag_name = 'th' if is_header else 'td'
        cells = row_tag.find_all(tag_name, recursive=False)
        if not cells:
            cells = row_tag.find_all(['th', 'td'], recursive=False)
        for cell in cells:
            align_cls = None
            for cls_name in cell.get('class', []):
                if cls_name in ALIGN_MAP:
                    align_cls = cls_name
            text = cell.get_text(strip=False)
            yield {
                'text': text,
                'tag': cell.name,
                'element': cell,
                'align': align_cls,
                'colspan': int(cell.get('colspan', 1)),
                'rowspan': int(cell.get('rowspan', 1)),
            }
