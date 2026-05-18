"""Legacy dict AST -> typed DocumentModel adapter."""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from typing import Any, Dict, List

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - existing project depends on bs4
    BeautifulSoup = None  # type: ignore

from diagnostics import make_diagnostic
from core.model import (
    BlockNode,
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
    ListItem,
    MathRun,
    PageBreak,
    Paragraph,
    RawHtmlBlock,
    RawInlineHtml,
    SourcePosition,
    StrongRun,
    Table,
    TableCell,
    TableRow,
    TextRun,
    UnsupportedBlock,
    UnsupportedInline,
)
from .raw_html_normalizer import normalize_raw_html_block, raw_html_images_as_inline

IMAGE_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:[\\/]|/|\./|\.\./|[\w.-]+/)[^\s\"'“”‘’<>|]+?\.(?:png|jpe?g|gif|bmp|webp|tiff?))",
    re.IGNORECASE,
)
TRAILING_IMAGE_PATH_PUNCTUATION = ".,;:，。；：、!！?？)]）】}"


def ast_to_document(ast: List[Dict[str, Any]], *, source_hint: str = "") -> Document:
    """Convert legacy dict AST to a typed DocumentModel."""

    blocks: List[BlockNode] = []
    active_prose_policy = ""
    for i, node in enumerate(ast):
        if node.get("type") == "prose_marker":
            active_prose_policy = "" if (node.get("attributes") or {}).get("end") else (node.get("content") or "")
            if active_prose_policy not in ("compact", "preserve"):
                active_prose_policy = ""
            continue
        block_or_blocks = _block_from_ast(
            node,
            f"{source_hint}#{i}",
            prose_policy=active_prose_policy,
            source_base=_source_base_path(source_hint),
        )
        if isinstance(block_or_blocks, list):
            blocks.extend(block_or_blocks)
        else:
            blocks.append(block_or_blocks)
        if node.get("type") != "paragraph" and active_prose_policy not in ("compact", "preserve"):
            active_prose_policy = ""
    return Document(blocks=blocks, source_position=SourcePosition(source_hint=source_hint))


def _block_from_ast(node: Dict[str, Any], source_hint: str, prose_policy: str = "", source_base: Path | None = None) -> BlockNode:
    node_type = node.get("type", "")
    diagnostics = _diagnostics(node)
    pos = SourcePosition(source_hint=source_hint)

    if node_type == "heading":
        return Heading(
            level=int(node.get("level", 1) or 1),
            text=node.get("content", "") or "",
            children=_inline_children(node, source_base),
            diagnostics=diagnostics,
            source_position=pos,
        )
    if node_type == "paragraph":
        return Paragraph(
            text=node.get("content", "") or "",
            children=_inline_children(node, source_base),
            prose_policy=prose_policy or (node.get("attributes") or {}).get("prose_kind"),
            diagnostics=diagnostics,
            source_position=pos,
        )
    if node_type == "table":
        attrs = node.get("attributes") or {}
        rows = [
            _table_row_from_ast(row, f"{source_hint}/row{ri}")
            for ri, row in enumerate(node.get("children", []) or [])
            if isinstance(row, dict)
        ]
        return Table(
            rows=rows,
            explicit_kind=attrs.get("table_kind"),
            source=attrs.get("source", "markdown"),
            diagnostics=diagnostics,
            source_position=pos,
        )
    if node_type == "image":
        img = _image_from_attrs(node.get("attributes") or {}, node.get("content", ""))
        return Figure(
            image=img,
            caption=[TextRun(text=img.alt)] if img.alt else [],
            diagnostics=diagnostics,
            source_position=pos,
        )
    if node_type == "code_block":
        language = (node.get("attributes") or {}).get("language", "") or ""
        code = node.get("content", "") or ""
        diagram = _diagram_from_code(code, language, diagnostics, pos)
        if diagram:
            return diagram
        return CodeBlock(code=code, language=language, diagnostics=diagnostics, source_position=pos)
    if node_type == "list":
        ordered = bool((node.get("attributes") or {}).get("ordered"))
        items = [
            _list_item_from_ast(item, f"{source_hint}/item{ii}")
            for ii, item in enumerate(node.get("children", []) or [])
            if isinstance(item, dict)
        ]
        return ListBlock(ordered=ordered, items=items, diagnostics=diagnostics, source_position=pos)
    if node_type == "blockquote":
        return BlockQuote(
            blocks=[
                _block_from_ast(child, f"{source_hint}/quote{ci}", source_base=source_base)
                for ci, child in enumerate(node.get("children", []) or [])
                if isinstance(child, dict)
            ],
            diagnostics=diagnostics,
            source_position=pos,
        )
    if node_type == "raw_html":
        html = node.get("content", "") or ""
        return normalize_raw_html_block(html, diagnostics, pos)
    if node_type == "pagebreak":
        return PageBreak(diagnostics=diagnostics, source_position=pos)
    if node_type == "hr":
        return HorizontalRule(diagnostics=diagnostics, source_position=pos)
    if node_type == "math_block":
        return Paragraph(
            text=node.get("content", "") or "",
            children=[MathRun(content=node.get("content", "") or "", display=True)],
            diagnostics=diagnostics,
            source_position=pos,
        )

    diag = make_diagnostic(
        "unsupported_ast_block",
        f"Unsupported legacy AST node preserved in DocumentModel: {node_type}",
        severity="warning",
        category="unsupported",
        fallback="preserve_as_unsupported_block",
        evidence=[str(node.get("content", ""))[:120]],
    )
    return UnsupportedBlock(
        original_type=node_type,
        content=node.get("content", "") or "",
        attributes=node.get("attributes") or {},
        children=node.get("children") or [],
        diagnostics=diagnostics + [diag],
        source_position=pos,
    )


def _inline_children(node: Dict[str, Any], source_base: Path | None = None) -> List[InlineNode]:
    children = node.get("children") or []
    if children:
        result: List[InlineNode] = []
        for child in children:
            if isinstance(child, dict):
                result.extend(_inline_from_segment(child, source_base))
        return result
    content = node.get("content", "") or ""
    return _text_or_existing_image_runs(content, source_base) if content else []


def _inline_from_segment(seg: Dict[str, Any], source_base: Path | None = None) -> List[InlineNode]:
    seg_type = seg.get("type", "text")
    diagnostics = _diagnostics(seg)

    if seg_type == "text":
        raw_images = raw_html_images_as_inline(seg.get("content", "") or "")
        if raw_images:
            text = _html_text_fallback(seg.get("content", "") or "")
            nodes: List[InlineNode] = []
            if text:
                nodes.append(TextRun(text=text, diagnostics=diagnostics))
            nodes.extend(raw_images)
            return nodes
        text_runs = _text_or_existing_image_runs(seg.get("content", "") or "", source_base, diagnostics=diagnostics)
        if len(text_runs) != 1 or not isinstance(text_runs[0], TextRun):
            return text_runs
        run: InlineNode = text_runs[0]
        if seg.get("bold"):
            run = StrongRun(children=[run])
        if seg.get("italic"):
            run = EmphasisRun(children=[run])
        return [run]
    if seg_type == "code_inline":
        return [InlineCode(code=seg.get("content", "") or "", diagnostics=diagnostics)]
    if seg_type == "link":
        link_children = seg.get("children") or []
        if link_children:
            inline_kids: List[InlineNode] = []
            for lc in link_children:
                inline_kids.extend(_inline_from_segment(lc, source_base))
            link_kids = inline_kids if inline_kids else [TextRun(text=seg.get("content", "") or "")]
        else:
            link_kids = [TextRun(text=seg.get("content", "") or "")]
        return [LinkRun(
            href=seg.get("href", "") or "",
            title=seg.get("title", "") or "",
            children=link_kids,
            diagnostics=diagnostics,
        )]
    if seg_type == "image":
        attrs = seg.get("attributes") or {}
        return [_image_from_attrs({**attrs, **{k: v for k, v in seg.items() if k in ("src", "alt", "title")}}, seg.get("content", ""))]
    if seg_type == "math_inline":
        return [MathRun(content=seg.get("content", "") or "", display=False, diagnostics=diagnostics)]
    if seg_type == "softbreak":
        return [BreakRun(hard=False, diagnostics=diagnostics)]
    if seg_type == "hardbreak":
        return [BreakRun(hard=True, diagnostics=diagnostics)]
    if seg_type in ("kbd", "sub", "sup", "highlight"):
        return [RawInlineHtml(
            html=seg.get("content", "") or "",
            text_fallback=seg.get("content", "") or "",
            diagnostics=diagnostics,
        )]

    diag = make_diagnostic(
        "unsupported_inline_segment",
        f"Unsupported inline segment preserved in DocumentModel: {seg_type}",
        severity="warning",
        category="unsupported",
        fallback="preserve_as_unsupported_inline",
        evidence=[str(seg.get("content", ""))[:120]],
    )
    return [UnsupportedInline(
        original_type=seg_type,
        content=seg.get("content", "") or "",
        attributes=seg.get("attributes") or {},
        diagnostics=diagnostics + [diag],
    )]


def _table_row_from_ast(row: Dict[str, Any], source_hint: str) -> TableRow:
    header = bool(row.get("is_header"))
    return TableRow(
        header=header,
        source_position=SourcePosition(source_hint=source_hint),
        diagnostics=_diagnostics(row),
        cells=[
            _table_cell_from_ast(cell, header, f"{source_hint}/cell{ci}")
            for ci, cell in enumerate(row.get("children", []) or [])
            if isinstance(cell, dict)
        ],
    )


def _table_cell_from_ast(cell: Dict[str, Any], header: bool, source_hint: str) -> TableCell:
    attrs = cell.get("attributes") or {}
    raw_html = attrs.get("raw_html", "") or ""
    children = _inline_children(cell, _source_base_path(source_hint))
    raw_images = raw_html_images_as_inline(raw_html)
    if raw_images:
        children.extend(raw_images)
        diagnostics = _diagnostics(cell) + [
            make_diagnostic(
                "raw_html_table_cell_images_normalized",
                "Raw HTML table cell <img> references were normalized into ImageRun nodes.",
                severity="info",
                category="normalization",
                fallback="preserve_cell_raw_html",
                evidence=[f"image_count={len(raw_images)}"],
            )
        ]
    else:
        diagnostics = _diagnostics(cell)
    return TableCell(
        text=cell.get("content", "") or "",
        children=children,
        colspan=int(attrs.get("colspan", 1) or 1),
        rowspan=int(attrs.get("rowspan", 1) or 1),
        header=header,
        align=attrs.get("align", "") or "",
        raw_html=raw_html,
        diagnostics=diagnostics,
        source_position=SourcePosition(source_hint=source_hint),
    )


def _list_item_from_ast(item: Dict[str, Any], source_hint: str) -> ListItem:
    checked = None
    blocks: List[BlockNode] = []
    for idx, child in enumerate(item.get("children", []) or []):
        if not isinstance(child, dict):
            continue
        if child.get("type") == "paragraph":
            attrs = child.get("attributes") or {}
            if "task_checked" in attrs:
                checked = bool(attrs.get("task_checked"))
        blocks.append(_block_from_ast(child, f"{source_hint}/block{idx}", source_base=_source_base_path(source_hint)))
    return ListItem(blocks=blocks, checked=checked, source_position=SourcePosition(source_hint=source_hint), diagnostics=_diagnostics(item))


def _image_from_attrs(attrs: Dict[str, Any], fallback_alt: str = "") -> ImageRun:
    return ImageRun(
        src=attrs.get("src", "") or "",
        alt=attrs.get("alt", "") or fallback_alt or "",
        title=attrs.get("title", "") or "",
        width=attrs.get("width", "") or "",
        height=attrs.get("height", "") or "",
        raw_html=attrs.get("raw_html", "") or "",
        source_kind=attrs.get("source_kind", "") or "",
        diagnostics=attrs.get("diagnostics", []) or [],
    )


def _text_or_existing_image_runs(text: str, source_base: Path | None, diagnostics: List[Dict[str, Any]] | None = None) -> List[InlineNode]:
    """Convert bare text image paths into ImageRun only when the file exists."""

    if not text:
        return []
    base = source_base
    nodes: List[InlineNode] = []
    cursor = 0
    for match in IMAGE_PATH_RE.finditer(text):
        raw_path = match.group("path")
        stripped_path = raw_path.rstrip(TRAILING_IMAGE_PATH_PUNCTUATION)
        trailing = raw_path[len(stripped_path):]
        if not stripped_path or not _image_path_exists(stripped_path, base):
            continue
        if match.start() > cursor:
            nodes.append(TextRun(text=text[cursor:match.start()], diagnostics=list(diagnostics or [])))
        nodes.append(ImageRun(
            src=stripped_path,
            alt=Path(stripped_path).name,
            source_kind="bare_text_image_path",
            diagnostics=list(diagnostics or []),
        ))
        if trailing:
            nodes.append(TextRun(text=trailing, diagnostics=list(diagnostics or [])))
        cursor = match.end()
    if not nodes:
        return [TextRun(text=text, diagnostics=list(diagnostics or []))]
    if cursor < len(text):
        nodes.append(TextRun(text=text[cursor:], diagnostics=list(diagnostics or [])))
    return nodes


def _image_path_exists(src: str, source_base: Path | None) -> bool:
    path = Path(src)
    if path.is_absolute():
        return path.exists()
    return bool(source_base and (source_base / src).resolve().exists())


def _source_base_path(source_hint: str) -> Path | None:
    if not source_hint or source_hint == "<memory>":
        return None
    raw = source_hint.split("#", 1)[0]
    raw = raw.split("/row", 1)[0].split("/item", 1)[0].split("/quote", 1)[0].split("/block", 1)[0]
    path = Path(raw)
    if path.suffix:
        return path.parent
    return path if path.exists() and path.is_dir() else None


def _diagram_from_code(code: str, language: str, diagnostics: List[Dict[str, Any]], pos: SourcePosition) -> Diagram | None:
    lang = (language or "").strip().lower()
    stripped = code.strip()
    if lang == "mermaid" or any(k in stripped for k in ("graph ", "flowchart ", "sequenceDiagram", "classDiagram", "stateDiagram", "gantt", "pie", "journey")):
        return Diagram(
            source=code,
            diagram_type="mermaid",
            subtype=_mermaid_subtype(stripped),
            language=language,
            diagnostics=diagnostics,
            source_position=pos,
        )
    if lang in ("plantuml", "puml") or stripped.startswith("@startuml") or stripped.startswith("@startgantt"):
        return Diagram(source=code, diagram_type="plantuml", language=language, diagnostics=diagnostics, source_position=pos)
    return None


def _mermaid_subtype(code: str) -> str:
    for subtype in ("sequenceDiagram", "gantt", "pie", "classDiagram", "stateDiagram", "journey"):
        if subtype in code:
            return subtype
    if "graph " in code or "flowchart " in code:
        return "flowchart"
    return ""


def _html_text_fallback(html: str) -> str:
    if BeautifulSoup is not None:
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return unescape(re.sub(r"<[^>]+>", " ", html)).strip()


def _diagnostics(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list((node.get("attributes") or {}).get("diagnostics") or [])
