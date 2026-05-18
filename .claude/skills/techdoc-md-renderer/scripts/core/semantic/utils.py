"""Small helpers shared by semantic analyzers."""

from __future__ import annotations

import re
from typing import Iterable, List

from core.model import (
    BlockNode,
    BlockQuote,
    Document,
    Figure,
    ImageRun,
    InlineNode,
    LinkRun,
    ListBlock,
    Paragraph,
    Table,
    TextRun,
)


def plain_inline_text(children: Iterable[InlineNode]) -> str:
    parts: List[str] = []
    for child in children:
        if isinstance(child, TextRun):
            parts.append(child.text)
        elif isinstance(child, ImageRun):
            parts.append(child.alt)
        elif isinstance(child, LinkRun):
            parts.append(plain_inline_text(child.children))
        else:
            text = getattr(child, "text", "") or getattr(child, "code", "") or getattr(child, "content", "") or getattr(child, "text_fallback", "")
            if text:
                parts.append(text)
            nested = getattr(child, "children", None)
            if nested:
                parts.append(plain_inline_text(nested))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def table_rows_text(table: Table) -> List[List[str]]:
    return [
        [cell.text or plain_inline_text(cell.children) for cell in row.cells]
        for row in table.rows
    ]


def walk_blocks(document_or_blocks) -> Iterable[BlockNode]:
    blocks = document_or_blocks.blocks if isinstance(document_or_blocks, Document) else document_or_blocks
    for block in blocks:
        yield block
        if isinstance(block, BlockQuote):
            yield from walk_blocks(block.blocks)
        elif isinstance(block, ListBlock):
            for item in block.items:
                yield from walk_blocks(item.blocks)


def walk_inline_images(block: BlockNode) -> Iterable[ImageRun]:
    if isinstance(block, Figure):
        yield block.image
    if isinstance(block, Paragraph):
        for child in block.children:
            yield from _walk_inline_image_children(child)
    if isinstance(block, Table):
        for row in block.rows:
            for cell in row.cells:
                for child in cell.children:
                    yield from _walk_inline_image_children(child)
                for nested in cell.blocks:
                    yield from walk_inline_images(nested)


def _walk_inline_image_children(node: InlineNode) -> Iterable[ImageRun]:
    if isinstance(node, ImageRun):
        yield node
    for child in getattr(node, "children", []) or []:
        yield from _walk_inline_image_children(child)
