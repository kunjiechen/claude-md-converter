"""Typed DocumentModel -> legacy dict AST bridge.

This bridge is intentionally conservative. It exists for compatibility tests
and future feature-flagged migration; legacy renderers are not switched to it
in Phase 2.
"""

from __future__ import annotations

from typing import Dict, List

from core.model import (
    BlockQuote,
    BreakRun,
    CodeBlock,
    Diagram,
    Document,
    EmphasisRun,
    Figure,
    Heading,
    HorizontalRule,
    ImageRun,
    InlineCode,
    InlineNode,
    LinkRun,
    ListBlock,
    MathRun,
    PageBreak,
    Paragraph,
    RawHtmlBlock,
    RawInlineHtml,
    StrongRun,
    Table,
    TextRun,
    UnsupportedInline,
)


def document_to_ast(document: Document) -> List[Dict]:
    return [_block_to_ast(block) for block in document.blocks]


def _block_to_ast(block) -> Dict:
    if isinstance(block, Heading):
        return {
            "type": "heading",
            "content": block.text or _plain_text(block.children),
            "level": block.level,
            "children": _inline_segments(block.children),
            "attributes": _attrs(block),
        }
    if isinstance(block, Paragraph):
        return {
            "type": "paragraph",
            "content": block.text or _plain_text(block.children),
            "children": _inline_segments(block.children),
            "attributes": _attrs(block),
        }
    if isinstance(block, Table):
        return {
            "type": "table",
            "content": "",
            "children": [
                {
                    "type": "table_row",
                    "content": "",
                    "children": [
                        {
                            "type": "table_cell",
                            "content": cell.text or _plain_text(cell.children),
                            "children": _inline_segments(cell.children),
                            "attributes": {
                                "align": cell.align,
                                "raw_html": cell.raw_html,
                                "colspan": cell.colspan,
                                "rowspan": cell.rowspan,
                                "diagnostics": cell.diagnostics,
                            },
                        }
                        for cell in row.cells
                    ],
                    "attributes": {"diagnostics": row.diagnostics},
                    **({"is_header": True} if row.header else {}),
                }
                for row in block.rows
            ],
            "attributes": {**_attrs(block), **({"table_kind": block.explicit_kind} if block.explicit_kind else {}), "source": block.source},
        }
    if isinstance(block, Figure):
        return {
            "type": "image",
            "content": block.image.alt,
            "children": [],
            "attributes": {
                **_attrs(block),
                "src": block.image.src,
                "alt": block.image.alt,
                "title": block.image.title,
            },
        }
    if isinstance(block, Diagram):
        return {
            "type": "code_block",
            "content": block.source,
            "children": [],
            "attributes": {**_attrs(block), "language": block.language or block.diagram_type},
        }
    if isinstance(block, CodeBlock):
        return {
            "type": "code_block",
            "content": block.code,
            "children": [],
            "attributes": {**_attrs(block), "language": block.language},
        }
    if isinstance(block, ListBlock):
        return {
            "type": "list",
            "content": "",
            "children": [
                {
                    "type": "list_item",
                    "content": "",
                    "children": [_block_to_ast(child) for child in item.blocks],
                    "attributes": {"diagnostics": item.diagnostics},
                }
                for item in block.items
            ],
            "attributes": {**_attrs(block), "ordered": block.ordered},
        }
    if isinstance(block, BlockQuote):
        return {
            "type": "blockquote",
            "content": "",
            "children": [_block_to_ast(child) for child in block.blocks],
            "attributes": _attrs(block),
        }
    if isinstance(block, RawHtmlBlock):
        return {"type": "raw_html", "content": block.html, "children": [], "attributes": _attrs(block)}
    if isinstance(block, PageBreak):
        return {"type": "pagebreak", "content": "", "children": [], "attributes": _attrs(block)}
    if isinstance(block, HorizontalRule):
        return {"type": "hr", "content": "", "children": [], "attributes": _attrs(block)}
    return {
        "type": "unsupported",
        "content": getattr(block, "content", ""),
        "children": [],
        "attributes": _attrs(block),
    }


def _inline_segments(children: List[InlineNode]) -> List[Dict]:
    segments: List[Dict] = []
    for child in children:
        if isinstance(child, TextRun):
            segments.append({"type": "text", "content": child.text})
        elif isinstance(child, StrongRun):
            for seg in _inline_segments(child.children):
                if seg.get("type") == "text":
                    seg["bold"] = True
                segments.append(seg)
        elif isinstance(child, EmphasisRun):
            for seg in _inline_segments(child.children):
                if seg.get("type") == "text":
                    seg["italic"] = True
                segments.append(seg)
        elif isinstance(child, InlineCode):
            segments.append({"type": "code_inline", "content": child.code})
        elif isinstance(child, LinkRun):
            segments.append({"type": "link", "content": _plain_text(child.children), "href": child.href, "title": child.title})
        elif isinstance(child, ImageRun):
            segments.append({
                "type": "image",
                "content": child.alt,
                "src": child.src,
                "alt": child.alt,
                "title": child.title,
                "children": [],
                "attributes": {"src": child.src, "alt": child.alt, "title": child.title, "diagnostics": child.diagnostics},
            })
        elif isinstance(child, MathRun):
            segments.append({"type": "math_inline", "content": child.content})
        elif isinstance(child, BreakRun):
            segments.append({"type": "hardbreak" if child.hard else "softbreak", "content": ""})
        elif isinstance(child, RawInlineHtml):
            segments.append({"type": "html_inline", "content": child.html, "attributes": {"diagnostics": child.diagnostics}})
        elif isinstance(child, UnsupportedInline):
            segments.append({
                "type": child.original_type or "unsupported_inline",
                "content": child.content,
                "attributes": {**child.attributes, "diagnostics": child.diagnostics},
            })
        else:
            text = getattr(child, "text_fallback", "") or getattr(child, "content", "")
            if text:
                segments.append({"type": "text", "content": text})
    return segments


def _plain_text(children: List[InlineNode]) -> str:
    parts: List[str] = []
    for child in children:
        if isinstance(child, TextRun):
            parts.append(child.text)
        elif isinstance(child, (StrongRun, EmphasisRun)):
            parts.append(_plain_text(child.children))
        elif isinstance(child, InlineCode):
            parts.append(child.code)
        elif isinstance(child, LinkRun):
            parts.append(_plain_text(child.children))
        elif isinstance(child, ImageRun):
            parts.append(child.alt)
        elif isinstance(child, MathRun):
            parts.append(child.content)
        else:
            parts.append(getattr(child, "text_fallback", "") or getattr(child, "content", ""))
    return "".join(parts)


def _attrs(block) -> Dict:
    return {"diagnostics": list(getattr(block, "diagnostics", []) or [])}
