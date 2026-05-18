"""Typed DocumentModel for Phase 2.

The model is renderer-independent: it carries document semantics, source hints,
and diagnostics, but no DOCX/PDF/HTML-specific fields such as DXA, EMU, CSS
classes, or Word style names.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, field, is_dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SourcePosition:
    """Best-effort source location hint for future diagnostics."""

    line_start: Optional[int] = None
    line_end: Optional[int] = None
    source_hint: str = ""


@dataclass
class InlineNode:
    source_position: Optional[SourcePosition] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TextRun(InlineNode):
    text: str = ""


@dataclass
class EmphasisRun(InlineNode):
    children: List[InlineNode] = field(default_factory=list)


@dataclass
class StrongRun(InlineNode):
    children: List[InlineNode] = field(default_factory=list)


@dataclass
class InlineCode(InlineNode):
    code: str = ""


@dataclass
class LinkRun(InlineNode):
    href: str = ""
    title: str = ""
    children: List[InlineNode] = field(default_factory=list)


@dataclass
class ImageRun(InlineNode):
    src: str = ""
    alt: str = ""
    title: str = ""
    width: str = ""
    height: str = ""
    raw_html: str = ""
    source_kind: str = ""


@dataclass
class MathRun(InlineNode):
    content: str = ""
    display: bool = False


@dataclass
class BreakRun(InlineNode):
    hard: bool = False


@dataclass
class RawInlineHtml(InlineNode):
    html: str = ""
    text_fallback: str = ""


@dataclass
class UnsupportedInline(InlineNode):
    original_type: str = ""
    content: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BlockNode:
    id: Optional[str] = None
    source_position: Optional[SourcePosition] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Document(BlockNode):
    blocks: List[BlockNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Heading(BlockNode):
    level: int = 1
    children: List[InlineNode] = field(default_factory=list)
    text: str = ""


@dataclass
class Paragraph(BlockNode):
    children: List[InlineNode] = field(default_factory=list)
    text: str = ""
    prose_policy: Optional[str] = None


@dataclass
class TableCell:
    children: List[InlineNode] = field(default_factory=list)
    blocks: List[BlockNode] = field(default_factory=list)
    text: str = ""
    colspan: int = 1
    rowspan: int = 1
    header: bool = False
    align: str = ""
    raw_html: str = ""
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    source_position: Optional[SourcePosition] = None


@dataclass
class TableRow:
    cells: List[TableCell] = field(default_factory=list)
    header: bool = False
    source_position: Optional[SourcePosition] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Table(BlockNode):
    rows: List[TableRow] = field(default_factory=list)
    explicit_kind: Optional[str] = None
    source: str = "markdown"


@dataclass
class Figure(BlockNode):
    image: ImageRun = field(default_factory=ImageRun)
    caption: List[InlineNode] = field(default_factory=list)


@dataclass
class CodeBlock(BlockNode):
    code: str = ""
    language: str = ""


@dataclass
class Diagram(BlockNode):
    source: str = ""
    diagram_type: str = "unknown"
    subtype: str = ""
    language: str = ""


@dataclass
class ListItem:
    blocks: List[BlockNode] = field(default_factory=list)
    checked: Optional[bool] = None
    source_position: Optional[SourcePosition] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ListBlock(BlockNode):
    ordered: bool = False
    items: List[ListItem] = field(default_factory=list)


@dataclass
class BlockQuote(BlockNode):
    blocks: List[BlockNode] = field(default_factory=list)


@dataclass
class RawHtmlBlock(BlockNode):
    html: str = ""
    text_fallback: str = ""


@dataclass
class PageBreak(BlockNode):
    pass


@dataclass
class HorizontalRule(BlockNode):
    pass


@dataclass
class UnsupportedBlock(BlockNode):
    original_type: str = ""
    content: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List[Any] = field(default_factory=list)


def node_to_dict(value: Any) -> Any:
    """Convert model nodes to JSON-serializable dictionaries."""

    if is_dataclass(value):
        data = {
            f.name: node_to_dict(getattr(value, f.name))
            for f in fields(value)
        }
        data["node_type"] = value.__class__.__name__
        return data
    if isinstance(value, list):
        return [node_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: node_to_dict(v) for k, v in value.items()}
    return value
