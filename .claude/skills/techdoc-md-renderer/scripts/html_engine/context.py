"""渲染上下文数据结构"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class RenderContext:
    """HTML渲染上下文，承载模板所需的所有数据"""

    title: str = ""
    number: str = ""
    version: str = ""
    department: str = ""
    company: str = ""
    date: str = ""
    theme_css: str = ""
    toc_html: str = ""
    body_html: str = ""
    revision_html: str = ""
    cover_html: str = ""
    flowcharts: list = field(default_factory=list)
    page_header_html: str = ""
    page_footer_html: str = ""
    mermaid_js_cdn: str = ""
    inline_images: bool = False
