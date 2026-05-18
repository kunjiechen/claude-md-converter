"""HTML adapter consuming DocumentModel, RenderPolicy, and LayoutPlan."""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List

from diagnostics import make_diagnostic
from core.layout import DiagramLayout, FigureLayout, LayoutPlan, TableLayout
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
    UnsupportedBlock,
    UnsupportedInline,
)
from renderers.base import RenderContext, RenderResult, RendererAdapter


REVISION_HEADERS = ["版次", "修订人", "修订原因", "修订内容", "修订日期", "备注"]


class HtmlRendererAdapter(RendererAdapter):
    target = "html"

    def render(self, context: RenderContext) -> RenderResult:
        diagnostics = list(context.diagnostics or [])
        diagnostics.extend(context.layout_plan.diagnostics)
        self._diagnostics = diagnostics
        self._heading_counters = [0] * 6
        self._revision_block_indices = set()
        self._revision_html = ""
        rev_policy = context.policy.document_policy.get("revision_history")
        if rev_policy == "required":
            heading_idx, rev_block, rev_idx = self._find_revision_source(context)
            if rev_block is not None:
                rows_data = self._extract_revision_data(rev_block)
                self._revision_block_indices.add(rev_idx)
                if heading_idx >= 0:
                    self._revision_block_indices.add(heading_idx)
                self._consume_revision_notes(context, rev_idx)
            else:
                if self._has_revision_signals(context):
                    self._diagnostics.append(make_diagnostic(
                        "revision_source_detected_but_not_normalized",
                        "Revision signals were found in source blocks; adapter skips template injection to avoid duplicate revision sections.",
                        severity="warning",
                        category="renderer",
                        fallback="preserve_source_revision_section",
                    ))
                    rows_data = []
                else:
                    rows_data = [self._auto_fill_revision_row(context)]
            if rows_data:
                rows_data = [self._enrich_revision_row(row, context) for row in rows_data]
                self._revision_html = self._revision_table_html(rows_data)
        self._heading_meta = self._build_heading_meta(context.document.blocks, context)
        self._heading_meta_index = 0
        self._raw_html_image_sources = set()
        try:
            body = self._render_blocks(context.document.blocks, context)
            html = self._document_shell(body, context)
            output_path = ""
            if context.output_path:
                path = Path(context.output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
                output_path = str(path)
            fidelity = self._fidelity(context, diagnostics)
            return RenderResult(
                success=True,
                output_path=output_path,
                content=html,
                diagnostics=diagnostics,
                fidelity_level=fidelity,
                fallback_used=False,
                metadata={"renderer": "html_adapter"},
            )
        except Exception as exc:
            diagnostics.append(make_diagnostic(
                "html_adapter_render_failed",
                "HTML adapter failed before producing output.",
                severity="error",
                category="renderer",
                fallback="legacy_html_renderer",
                evidence=[str(exc)],
            ))
            return RenderResult(False, diagnostics=diagnostics, fidelity_level="non_conformant", fallback_used=True, error=str(exc))

    def _document_shell(self, body: str, context: RenderContext) -> str:
        title = escape(context.options.get("doc_title") or "Document")
        toc = self._toc_html(context)
        mermaid = ""
        if context.layout_plan.diagrams:
            mermaid = (
                '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>\n'
                "<script>mermaid.initialize({startOnLoad:true});</script>"
            )
        return (
            "<!doctype html>\n"
            '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            f"<title>{title}</title>\n"
            "<style>\n"
            "body{font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.65;margin:2rem auto;max-width:960px;padding:0 1rem;}\n"
            ".toc{margin:0 0 2rem 0;padding:1rem 0;border-bottom:1px solid #bbb;}.toc-title{font-weight:700;margin-bottom:.5rem;}"
            ".toc-item{line-height:1.6;}.toc-item a{display:flex;align-items:baseline;text-decoration:none;color:inherit;}"
            ".toc-num{flex:0 0 auto;margin-right:.5em;white-space:nowrap;}"
            ".toc-title-text{flex:1 1 auto;min-width:0;} .toc-item a{background:repeating-linear-gradient(to right,transparent 0,transparent .4em,#aaa .4em,#aaa .55em) 0 1.1em/100% 1px no-repeat;}"
            ".toc-page{flex:0 0 auto;min-width:2.5em;text-align:right;white-space:nowrap;margin-left:.3em;}"
            ".toc-level-1{font-weight:700;}.toc-level-2{padding-left:1em;}.toc-level-3{padding-left:2em;}.toc-level-4{padding-left:3em;}\n"
            ".table-wrapper{overflow-x:auto;margin:1rem 0;}\n"
            "table{border-collapse:collapse;width:100%;table-layout:fixed;}th,td{border:1px solid #999;padding:.35rem .5rem;vertical-align:top;}"
            "th{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.35;max-height:2.7em;}\n"
            "img{max-width:100%;height:auto;}figure{text-align:center;margin:1rem 0;}p.image-paragraph{text-align:center;}"
            "td img{display:inline-block;max-width:100%;height:auto;vertical-align:middle;}\n"
            ".layout-overflow-high{border-left:4px solid #b45309;padding-left:.5rem;}\n"
            ".missing-image{border:1px dashed #b91c1c;padding:.75rem;color:#7f1d1d;background:#fef2f2;}\n"
            ".unsupported{border:1px dashed #777;padding:.5rem;background:#f8f8f8;}\n"
            "pre{overflow-x:auto;background:#f5f5f5;padding:.75rem;}\n"
            ".revision-history{margin:1rem 0 2rem 0;}.revision-title{font-weight:700;text-align:center;margin-bottom:.5rem;}"
            ".revision-table{border-collapse:collapse;width:100%;}.revision-table th,.revision-table td{border:1px solid #999;padding:.35rem .5rem;vertical-align:top;}"
            ".revision-table th{text-align:center;font-weight:700;}"
            "@media print{body{margin:0;max-width:none;padding:0;}.toc{break-after:page;}.revision-history{break-after:page;}.table-wrapper{overflow:visible;break-inside:avoid;}figure{break-inside:avoid;}}\n"
            "</style>\n"
            f"{mermaid}\n</head>\n<body>\n{body}\n</body>\n</html>\n"
        ).replace("<body>\n", f"<body>\n{toc}{self._revision_html}")

    def _render_blocks(self, blocks: Iterable[Any], context: RenderContext) -> str:
        skip_indices = self._revision_block_indices | self._source_toc_indices(context)
        parts = []
        for i, block in enumerate(blocks):
            if i in skip_indices:
                continue
            part = self._render_block(block, i, context)
            if part:
                parts.append(part)
        return "\n".join(parts)

    def _render_block(self, block: Any, block_index: int, context: RenderContext) -> str:
        if isinstance(block, Heading):
            level = max(1, min(block.level, 6))
            meta = self._next_heading_meta(level, block, context)
            number = meta.get("number", "")
            heading_id = meta.get("id", "")
            label = f"{number} " if number else ""
            return (
                f'<a id="{escape(heading_id, quote=True)}"></a>'
                f'<h{level} class="heading heading--{level}">{escape(label)}{self._inline(block.children, context)}</h{level}>'
            )
        if isinstance(block, Paragraph):
            klass = "paragraph image-paragraph" if self._is_image_only_paragraph(block) else "paragraph"
            return f'<p class="{klass}">{self._inline(block.children, context) or escape(block.text)}</p>'
        if isinstance(block, Table):
            return self._render_table(block, block_index, context.layout_plan, context)
        if isinstance(block, Figure):
            if self._is_duplicate_raw_html_figure(block):
                self._diagnostics.append(make_diagnostic(
                    "html_adapter_raw_html_image_duplicate_suppressed",
                    "Raw HTML image was already preserved in its source HTML block; duplicate extracted figure was suppressed for HTML/PDF layout fidelity.",
                    severity="info",
                    category="renderer",
                    fallback="preserve_source_raw_html_position",
                    evidence=[block.image.src],
                ))
                return ""
            return self._render_figure(block, block_index, context.layout_plan)
        if isinstance(block, CodeBlock):
            return self._render_code(block, block_index)
        if isinstance(block, Diagram):
            return self._render_diagram(block, block_index, context.layout_plan)
        if isinstance(block, ListBlock):
            tag = "ol" if block.ordered else "ul"
            items = []
            for item in block.items:
                items.append(f"<li>{self._render_blocks(item.blocks, context)}</li>")
            return f"<{tag}>" + "".join(items) + f"</{tag}>"
        if isinstance(block, BlockQuote):
            return f"<blockquote>{self._render_blocks(block.blocks, context)}</blockquote>"
        if isinstance(block, RawHtmlBlock):
            return self._render_raw_html(block, context)
        if isinstance(block, PageBreak):
            return '<hr class="pagebreak">'
        if isinstance(block, HorizontalRule):
            return '<hr>'
        if isinstance(block, UnsupportedBlock):
            self._diagnostics.append(make_diagnostic(
                "html_adapter_unsupported_block",
                "Unsupported block was rendered as an explicit placeholder.",
                severity="warning",
                category="renderer",
                fallback="unsupported_placeholder",
                evidence=[block.original_type],
            ))
            msg = escape(block.content or block.original_type)
            return f'<div class="unsupported" data-unsupported-type="{escape(block.original_type)}">{msg}</div>'
        return ""

    def _render_table(self, table: Table, block_index: int, plan: LayoutPlan, context: RenderContext) -> str:
        table_layout = self._table_layout_for_block(plan, block_index)
        kind = table_layout.kind if table_layout else "generic"
        overflow = table_layout.overflow_risk if table_layout else "unknown"
        landscape = table_layout.landscape_recommendation if table_layout else "not_required"
        header_rows = []
        body_rows = []
        for row_idx, row in enumerate(table.rows):
            tag = "th" if row.header else "td"
            cells = "".join(f"<{tag}>{self._inline(cell.children, context) or escape(cell.text)}</{tag}>" for cell in row.cells)
            if row.header:
                header_rows.append(f"<tr>{cells}</tr>")
            else:
                body_rows.append(f"<tr>{cells}</tr>")
        if not header_rows and body_rows:
            all_rows = "\n".join(body_rows)
        else:
            all_rows = ""
            if header_rows:
                all_rows += "<thead>\n" + "\n".join(header_rows) + "\n</thead>\n"
            all_rows += "<tbody>\n" + "\n".join(body_rows) + "\n</tbody>"
        colgroup = self._table_colgroup(table_layout)
        return (
            f'<div class="table-wrapper layout-overflow-{escape(overflow)}" '
            f'data-table-kind="{escape(kind)}" data-landscape-recommendation="{escape(landscape)}">\n'
            f'<table class="table table--{escape(kind)}">\n'
            + colgroup
            + all_rows
            + "\n</table>\n</div>"
        )

    def _render_figure(self, figure: Figure, block_index: int, plan: LayoutPlan) -> str:
        layout = self._figure_layout_for_block(plan, block_index)
        if layout and layout.asset_status == "missing_asset":
            self._diagnostics.append(make_diagnostic(
                "html_adapter_missing_image_placeholder",
                "Missing block image was rendered as an explicit placeholder.",
                severity="warning",
                category="renderer",
                fallback="missing_image_placeholder",
                evidence=[figure.image.src],
            ))
            return (
                f'<div class="missing-image" data-placeholder-intent="{escape(layout.missing_image_placeholder_intent)}">'
                f'Missing image: {escape(figure.image.src)}</div>'
            )
        img = figure.image
        size = self._image_size_attrs(img)
        return f'<figure><img src="{escape(img.src, quote=True)}" alt="{escape(img.alt, quote=True)}"{size}></figure>'

    @staticmethod
    def _render_code(block: CodeBlock, block_index: int) -> str:
        return f'<pre class="code-block" data-language="{escape(block.language)}"><code>{escape(block.code)}</code></pre>'

    def _render_diagram(self, diagram: Diagram, block_index: int, plan: LayoutPlan) -> str:
        layout = self._diagram_layout_for_block(plan, block_index)
        risk = layout.fallback_fidelity_risk if layout else "review"
        if diagram.diagram_type == "mermaid":
            return f'<pre class="mermaid" data-fidelity-risk="{escape(risk)}">{escape(diagram.source)}</pre>'
        return (
            f'<pre class="diagram-placeholder" data-diagram-kind="{escape(diagram.diagram_type)}" '
            f'data-fidelity-risk="{escape(risk)}">{escape(diagram.source)}</pre>'
        )

    def _render_raw_html(self, block: RawHtmlBlock, context: RenderContext) -> str:
        policy = context.policy.document_policy.get("unsupported_content_policy", "diagnostic_required")
        if policy == "diagnostic_required":
            self._record_raw_html_images(block.html)
            self._diagnostics.append(make_diagnostic(
                "html_adapter_raw_html_review",
                "Raw HTML block was preserved for HTML output and marked for fidelity review.",
                severity="warning",
                category="renderer",
                fallback="preserve_raw_html",
                evidence=[block.html[:120]],
            ))
            return f'<div class="raw-html" data-fidelity="review">{block.html}</div>'
        return f'<div class="unsupported">{escape(block.text_fallback or block.html)}</div>'

    def _inline(self, children: Iterable[InlineNode], context: RenderContext = None) -> str:
        return "".join(self._inline_node(child, context) for child in children)

    def _inline_node(self, node: InlineNode, context: RenderContext = None) -> str:
        if isinstance(node, TextRun):
            return escape(node.text)
        if isinstance(node, StrongRun):
            return f"<strong>{self._inline(node.children, context)}</strong>"
        if isinstance(node, EmphasisRun):
            return f"<em>{self._inline(node.children, context)}</em>"
        if isinstance(node, InlineCode):
            return f'<code class="code-inline">{escape(node.code)}</code>'
        if isinstance(node, LinkRun):
            return f'<a href="{escape(node.href, quote=True)}">{self._inline(node.children, context) or escape(node.href)}</a>'
        if isinstance(node, ImageRun):
            if context and self._asset_status_for_src(context, node.src) == "missing_asset":
                self._diagnostics.append(make_diagnostic(
                    "html_adapter_missing_inline_image_placeholder",
                    "Missing inline image was rendered as an explicit placeholder.",
                    severity="warning",
                    category="renderer",
                    fallback="missing_inline_image_placeholder",
                    evidence=[node.src],
                ))
                return (
                    f'<span class="missing-image" data-placeholder-intent="render_declared_missing_asset_placeholder">'
                    f'Missing image: {escape(node.src)}</span>'
                )
            return f'<img class="inline-image" src="{escape(node.src, quote=True)}" alt="{escape(node.alt, quote=True)}"{self._image_size_attrs(node)}>'
        if isinstance(node, MathRun):
            return f'<span class="math math--inline">\\({escape(node.content)}\\)</span>'
        if isinstance(node, RawInlineHtml):
            self._diagnostics.append(make_diagnostic(
                "html_adapter_raw_inline_html_review",
                "Raw inline HTML was preserved for HTML output and marked for fidelity review.",
                severity="warning",
                category="renderer",
                fallback="preserve_raw_inline_html",
                evidence=[(node.html or node.text_fallback)[:120]],
            ))
            return node.html or escape(node.text_fallback)
        if isinstance(node, BreakRun):
            return "<br>"
        if isinstance(node, UnsupportedInline):
            self._diagnostics.append(make_diagnostic(
                "html_adapter_unsupported_inline",
                "Unsupported inline node was rendered as an explicit placeholder.",
                severity="warning",
                category="renderer",
                fallback="unsupported_inline_placeholder",
                evidence=[node.original_type],
            ))
            return f'<span class="unsupported">{escape(node.content or node.original_type)}</span>'
        return ""

    def _heading_number(self, level: int, context: RenderContext) -> str:
        policy = context.policy.document_policy.get("heading_numbering")
        if policy not in ("required", "recommended"):
            return ""
        idx = level - 1
        self._heading_counters[idx] += 1
        for i in range(idx + 1, len(self._heading_counters)):
            self._heading_counters[i] = 0
        for i in range(0, idx):
            if self._heading_counters[i] == 0:
                self._heading_counters[i] = 1
        return ".".join(str(v) for v in self._heading_counters[:level] if v > 0)

    def _build_heading_meta(self, blocks: Iterable[Any], context: RenderContext) -> List[Dict[str, str]]:
        self._heading_counters = [0] * 6
        metas = []
        seen = {}
        rev_policy = context.policy.document_policy.get("revision_history") == "required"
        for index, block in enumerate(blocks):
            if not isinstance(block, Heading):
                continue
            text = self._plain_inline_text(block.children) or block.text or f"heading-{index + 1}"
            if rev_policy and "文件修订履历表" in text:
                continue
            level = max(1, min(block.level, 6))
            number = self._heading_number(level, context)
            slug = self._slug(text, index + 1)
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            if count:
                slug = f"{slug}-{count + 1}"
            metas.append({"id": slug, "level": str(level), "number": number, "text": text})
        self._heading_counters = [0] * 6
        return metas

    def _next_heading_meta(self, level: int, block: Heading, context: RenderContext) -> Dict[str, str]:
        if self._heading_meta_index < len(self._heading_meta):
            meta = self._heading_meta[self._heading_meta_index]
            self._heading_meta_index += 1
            return meta
        return {
            "id": f"heading-{self._heading_meta_index + 1}",
            "level": str(level),
            "number": self._heading_number(level, context),
            "text": self._plain_inline_text(block.children) or block.text or "",
        }

    @staticmethod
    def _estimated_toc_page(heading_index: int) -> int:
        return 5 + max(0, heading_index - 1) // 5

    def _toc_html(self, context: RenderContext) -> str:
        toc_policy = context.policy.document_policy.get("toc")
        if toc_policy not in ("required", "recommended") and not context.options.get("include_toc"):
            return ""
        if not self._heading_meta:
            return ""
        items = []
        rev_policy = context.policy.document_policy.get("revision_history") == "required"
        rev_heading_found = any(
            isinstance(block, Heading) and "文件修订履历表" in (block.text or "")
            for block in context.document.blocks
        )
        heading_index = 0
        if rev_policy:
            items.append(
                '<div class="toc-item toc-level-1">'
                '<a href="#文件修订履历表">'
                '<span class="toc-num"></span>'
                '<span class="toc-title-text">文件修订履历表</span>'
                '<span class="toc-page">3</span>'
                '</a></div>'
            )
        for meta in self._heading_meta:
            if rev_heading_found and (meta.get("text", "") or "").strip() == "文件修订履历表":
                continue
            num = meta.get("number", "")
            title = meta.get("text", "")
            anchor = escape(meta["id"], quote=True)
            display_num = escape(num) if num else ""
            display_title = escape(title)
            heading_index += 1
            level = int(meta.get("level", 1))
            page = self._estimated_toc_page(heading_index)
            items.append(
                f'<div class="toc-item toc-level-{level}">'
                f'<a href="#{anchor}">'
                f'<span class="toc-num">{display_num}</span>'
                f'<span class="toc-title-text">{display_title}</span>'
                f'<span class="toc-page">{page}</span>'
                f'</a></div>'
            )
        return '<nav class="toc" aria-label="目录"><div class="toc-title">目录</div>' + "\n".join(items) + "</nav>\n"

    def _record_raw_html_images(self, html: str) -> None:
        for src in re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", html or "", flags=re.I):
            self._raw_html_image_sources.add(src)

    def _is_duplicate_raw_html_figure(self, figure: Figure) -> bool:
        image = getattr(figure, "image", None)
        return bool(
            image
            and getattr(image, "source_kind", "") == "raw_html_img"
            and image.src in self._raw_html_image_sources
        )

    def _plain_inline_text(self, children: Iterable[InlineNode]) -> str:
        parts = []
        for node in children or []:
            if isinstance(node, TextRun):
                parts.append(node.text)
            elif isinstance(node, (StrongRun, EmphasisRun, LinkRun)):
                parts.append(self._plain_inline_text(node.children))
            elif isinstance(node, InlineCode):
                parts.append(node.code)
            elif isinstance(node, ImageRun):
                parts.append(node.alt)
            else:
                parts.append(getattr(node, "text", "") or getattr(node, "content", ""))
        return "".join(parts).strip()

    @staticmethod
    def _is_image_only_paragraph(block: Paragraph) -> bool:
        children = getattr(block, "children", []) or []
        return bool(children) and all(
            isinstance(child, ImageRun) or (isinstance(child, TextRun) and not child.text.strip())
            for child in children
        )

    @staticmethod
    def _slug(text: str, fallback_index: int) -> str:
        slug = re.sub(r"\s+", "-", (text or "").strip().lower())
        slug = re.sub(r"[^\w\u4e00-\u9fff.-]+", "", slug).strip("-")
        return slug or f"heading-{fallback_index}"

    @staticmethod
    def _asset_status_for_src(context: RenderContext, src: str) -> str:
        semantic = context.document.metadata.get("semantic_analysis") or {}
        for asset in semantic.get("assets") or []:
            attrs = asset.get("attributes") or {}
            if attrs.get("src") == src:
                return asset.get("kind", "")
        return ""

    @staticmethod
    def _image_size_attrs(image: ImageRun) -> str:
        attrs = []
        styles = ["max-width:100%", "height:auto"]
        if getattr(image, "width", ""):
            attrs.append(f' data-source-width="{escape(str(image.width), quote=True)}"')
            styles.append(f'width:{escape(str(image.width), quote=True)}')
        if getattr(image, "height", ""):
            attrs.append(f' data-source-height="{escape(str(image.height), quote=True)}"')
        attrs.append(f' style="{";".join(styles)}"')
        return "".join(attrs)

    @staticmethod
    def _table_layout_for_block(plan: LayoutPlan, block_index: int) -> TableLayout:
        return next((item for item in plan.tables if item.block_index == block_index), None)

    @staticmethod
    def _table_colgroup(table_layout: TableLayout) -> str:
        if not table_layout or not table_layout.columns:
            return ""
        cols = "".join(
            f'<col style="width:{max(0.0, min(100.0, c.width_ratio * 100.0)):.2f}%">'
            for c in table_layout.columns
        )
        return f"<colgroup>{cols}</colgroup>\n"

    @staticmethod
    def _figure_layout_for_block(plan: LayoutPlan, block_index: int) -> FigureLayout:
        return next((item for item in plan.figures if item.block_index == block_index), None)

    @staticmethod
    def _diagram_layout_for_block(plan: LayoutPlan, block_index: int) -> DiagramLayout:
        return next((item for item in plan.diagrams if item.block_index == block_index), None)

    def _source_toc_indices(self, context: RenderContext) -> set:
        toc_policy = context.policy.document_policy.get("toc")
        if toc_policy not in ("required", "recommended"):
            return set()
        blocks = list(context.document.blocks)
        if not blocks:
            return set()
        if isinstance(blocks[0], Table) and self._looks_like_exported_toc_table(blocks[0]):
            skip = {0}
            for index, block in enumerate(blocks[1:], start=1):
                if isinstance(block, Heading):
                    break
                text = (getattr(block, "text", "") or "").strip()
                if isinstance(block, Paragraph) and not text:
                    skip.add(index)
                    continue
                break
            return skip
        if not isinstance(blocks[0], Paragraph):
            return set()
        first_text = (blocks[0].text or "").strip()
        if first_text != "目录":
            return set()
        skip = {0}
        for index, block in enumerate(blocks[1:], start=1):
            if isinstance(block, Heading):
                break
            text = (getattr(block, "text", "") or "").strip()
            if not text:
                skip.add(index)
                continue
            if isinstance(block, Paragraph) and self._looks_like_exported_toc_entry(text):
                skip.add(index)
                continue
            break
        return skip

    @staticmethod
    def _looks_like_exported_toc_entry(text: str) -> bool:
        return (
            text.startswith("[")
            and "](" in text
            and "#" in text
        ) or bool(re.match(r"^\d+(?:\.\d+)*\s+.+\s+\d+$", text))

    @staticmethod
    def _looks_like_exported_toc_table(block: Table) -> bool:
        rows = getattr(block, "rows", []) or []
        if len(rows) < 2:
            return False
        first_cell = ((rows[0].cells[0].text if rows[0].cells else "") or "").strip()
        if first_cell != "目录":
            return False
        samples = []
        for row in rows[1: min(10, len(rows))]:
            text = ((row.cells[0].text if row.cells else "") or "").strip()
            if text:
                samples.append(text)
        if not samples:
            return False
        toc_like = sum(1 for s in samples if ("目的" in s or "适用范围" in s or re.search(r"\d+$", s)))
        return toc_like >= max(1, len(samples) // 2)

    def _find_revision_source(self, context: RenderContext):
        """Find the revision heading + data table in document blocks.

        Returns (heading_index, data_block, data_index). heading_index is -1
        when no explicit heading block precedes the table.
        """
        blocks = list(context.document.blocks)

        # Pass 1: Heading "文件修订履历表" followed by a Table or RawHtmlBlock
        for i, block in enumerate(blocks):
            if isinstance(block, Heading) and "文件修订履历表" in (block.text or ""):
                for j in range(i + 1, min(i + 5, len(blocks))):
                    if isinstance(blocks[j], (Table, RawHtmlBlock)):
                        return i, blocks[j], j
                return i, None, -1

        # Pass 2: Semantic analysis — find the first Table block tagged "revision"
        sem_tables = (context.document.metadata.get("semantic_analysis") or {}).get("tables", [])
        if "revision" in [item.get("kind") for item in sem_tables]:
            rev_sem_index = next((i for i, item in enumerate(sem_tables) if item.get("kind") == "revision"), -1)
            if rev_sem_index >= 0:
                table_count = 0
                for i, block in enumerate(blocks):
                    if isinstance(block, Table):
                        if table_count == rev_sem_index:
                            return -1, block, i
                        table_count += 1

        # Pass 3: RawHtmlBlock containing revision markers
        for i, block in enumerate(blocks):
            if isinstance(block, RawHtmlBlock) and any(
                kw in (block.html or "").lower() for kw in ("版次", "修订人")
            ):
                return -1, block, i

        return -1, None, -1

    def _has_revision_signals(self, context: RenderContext) -> bool:
        blocks = list(context.document.blocks)
        for block in blocks:
            text = (getattr(block, "text", "") or getattr(block, "content", "") or "").strip()
            if text and ("文件修订履历表" in text or ("版次" in text and "修订" in text)):
                return True
            if isinstance(block, RawHtmlBlock):
                html = (block.html or "").lower()
                if "版次" in html and "修订" in html:
                    return True
        sem_tables = (context.document.metadata.get("semantic_analysis") or {}).get("tables", [])
        return any((item.get("kind") == "revision") for item in sem_tables)

    def _extract_revision_data(self, rev_block) -> list:
        if isinstance(rev_block, Table):
            data = []
            for row in rev_block.rows:
                if row.header:
                    continue
                cells = []
                for cell in row.cells[:6]:
                    text = cell.text.strip() or "".join(getattr(c, "text", "") for c in (cell.children or []))
                    cells.append(text.strip())
                while len(cells) < 6:
                    cells.append("")
                data.append(cells[:6])
            filled = [r for r in data if any(r)]
            return filled if filled else [["待补充", "", "", "", "", ""]]
        if isinstance(rev_block, RawHtmlBlock):
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(rev_block.html, "html.parser")
                data = []
                for tr in soup.find_all("tr"):
                    if tr.find("th") or tr.parent.name == "thead":
                        continue
                    c = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if any(c):
                        while len(c) < 6:
                            c.append("")
                        data.append(c[:6])
                return data if data else [["待补充", "", "", "", "", ""]]
            except Exception:
                pass
        return [["待补充", "", "", "", "", ""]]

    def _auto_fill_revision_row(self, context: RenderContext):
        author = self._detect_author(context)
        today = date.today().strftime("%Y.%m.%d")
        return ["A/0", author, "新制定", "初版", today, ""]

    def _enrich_revision_row(self, row: list, context: RenderContext):
        """Auto-fill empty 修订人 (col 1) and 修订日期 (col 4) cells."""
        enriched = list(row)
        if not enriched[1].strip():
            enriched[1] = self._detect_author(context)
        if not enriched[4].strip():
            enriched[4] = date.today().strftime("%Y.%m.%d")
        return enriched

    @staticmethod
    def _detect_author(context: RenderContext) -> str:
        author = (context.document.metadata.get("author") or "").strip()
        if author:
            return author
        blocks = list(context.document.blocks)
        for block in reversed(blocks[-5:]):
            text = getattr(block, "text", "") or getattr(block, "content", "") or ""
            if "拟制" in text:
                m = re.search(r"拟制[：:]\s*(\S+)", text)
                if m:
                    return m.group(1).strip("。，, ")
                return text.strip()
        import os, subprocess
        try:
            git_name = subprocess.check_output(
                ["git", "config", "user.name"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            if git_name:
                return git_name
        except Exception:
            pass
        return os.environ.get("USER") or os.environ.get("USERNAME") or ""

    def _consume_revision_notes(self, context: RenderContext, rev_idx: int) -> None:
        """Consume trailing revision-note paragraphs so they don't leak into body."""
        blocks = list(context.document.blocks)
        for offset in (1, 2):
            idx = rev_idx + offset
            if idx >= len(blocks):
                break
            block = blocks[idx]
            if isinstance(block, Heading):
                break
            if isinstance(block, Paragraph):
                text = (block.text or "").strip()
                if text and "修订" in text:
                    self._revision_block_indices.add(idx)
                    continue
            break

    def _revision_table_html(self, rows_data: list) -> str:
        center_cols = {0, 1, 4}
        ratios = self._revision_width_ratios(rows_data)
        colgroup = "<colgroup>" + "".join(
            f'<col style="width:{max(0.0, min(100.0, r * 100.0)):.2f}%">' for r in ratios
        ) + "</colgroup>\n"
        header_cells = "".join(
            f"<th>{escape(h)}</th>" for h in REVISION_HEADERS
        )
        data_rows = []
        for row_data in rows_data:
            cells = []
            for ci, text in enumerate(row_data):
                if ci >= 6:
                    break
                align = ' style="text-align:center"' if ci in center_cols else ""
                cells.append(f"<td{align}>{escape(text) if text else ''}</td>")
            data_rows.append("<tr>" + "".join(cells) + "</tr>")
        return (
            '<div class="revision-history">\n'
            '<a id="文件修订履历表"></a>'
            '<div class="revision-title">文件修订履历表</div>\n'
            '<div class="table-wrapper">\n'
            '<table class="revision-table">\n'
            f"{colgroup}"
            f"<thead><tr>{header_cells}</tr></thead>\n"
            f"<tbody>\n" + "\n".join(data_rows) + "\n</tbody>\n"
            "</table>\n</div>\n</div>\n"
        )

    @staticmethod
    def _revision_width_ratios(rows_data: list) -> list:
        headers = ["版次", "修订人", "修订原因", "修订内容", "修订日期", "备注"]
        weights = []
        for i, header in enumerate(headers):
            samples = [header] + [str(row[i] if i < len(row) else "") for row in rows_data]
            lengths = [len(s.strip()) for s in samples if str(s).strip()]
            max_len = max(lengths) if lengths else len(header)
            avg_len = (sum(lengths) / len(lengths)) if lengths else len(header)
            base = 1.0 if i in (0, 1, 4) else 1.8
            weights.append(base * (0.7 + min(2.0, 0.012 * max_len + 0.02 * avg_len)))
        total = sum(weights) or 1.0
        ratios = [w / total for w in weights]
        clamped = [max(0.10, min(0.42, r)) for r in ratios]
        norm = sum(clamped) or 1.0
        return [w / norm for w in clamped]

    @staticmethod
    def _fidelity(context: RenderContext, diagnostics: List[Dict[str, Any]]) -> str:
        html_policy = (context.policy.renderer_policy.get("html") or {})
        if any(d.get("severity") == "error" for d in diagnostics):
            return "review"
        review_categories = {"unsupported", "asset", "diagram", "layout", "renderer"}
        review_codes = ("raw_html", "source_only", "missing_image", "unsupported")
        if any(d.get("category") in review_categories or any(code in str(d.get("code", "")) for code in review_codes) for d in diagnostics):
            return "review"
        return html_policy.get("target_fidelity", "conformant")
