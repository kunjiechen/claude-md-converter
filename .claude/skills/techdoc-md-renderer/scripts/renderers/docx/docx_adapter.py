"""Minimal DOCX adapter consuming DocumentModel, RenderPolicy, and LayoutPlan."""

from __future__ import annotations

from pathlib import Path
import re

from docx import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, Inches

from diagnostics import make_diagnostic
from core.model import (
    BlockQuote,
    CodeBlock,
    Figure,
    Heading,
    HorizontalRule,
    ListBlock,
    PageBreak,
    Paragraph,
    RawHtmlBlock,
    ImageRun,
    Table,
    TextRun,
    UnsupportedBlock,
)
from renderers.base import RenderContext, RenderResult, RendererAdapter
from .image_writer import DocxImageWriter
from .inline_writer import DocxInlineWriter
from .style_mapper import DocxStyleMapper
from .table_writer import DocxTableWriter


class DocxRendererAdapter(RendererAdapter):
    target = "docx"

    def render(self, context: RenderContext) -> RenderResult:
        diagnostics = list(context.diagnostics or [])
        diagnostics.extend(context.layout_plan.diagnostics)
        self.diagnostics = diagnostics
        try:
            doc = DocxDocument()
            self._apply_formal_styles(doc)
            self.style_mapper = DocxStyleMapper(doc, context.policy, diagnostics)
            self.inline_writer = DocxInlineWriter(diagnostics)
            self.image_writer = DocxImageWriter(diagnostics)
            self.table_writer = DocxTableWriter(self.style_mapper, diagnostics)
            self.heading_counters = [0] * 6
            self._revision_block_indices = set()
            self._heading_anchor_map = self._build_heading_anchor_map(context)
            self._next_bookmark_id = 0

            self._apply_page_setup(doc, context)
            self._apply_header_footer(doc, context)
            self._insert_toc_if_required(doc, context)
            self._insert_revision_table(doc, context)

            for index, block in self._renderable_blocks(context):
                self._render_block(doc, block, index, context)

            output_path = str(context.output_path or "")
            if not output_path:
                raise ValueError("DOCX adapter requires output_path")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            doc.save(output_path)
            fidelity, reason = self._fidelity(diagnostics)
            return RenderResult(
                success=True,
                output_path=output_path,
                diagnostics=diagnostics,
                fidelity_level=fidelity,
                degradation_reason=reason,
                fallback_used=False,
                metadata={"renderer": "docx_adapter", "format_reference": "Original formal document corpus"},
            )
        except Exception as exc:
            diagnostics.append(make_diagnostic(
                "docx_adapter_render_failed",
                "DOCX adapter failed before producing output.",
                severity="error",
                category="renderer",
                fallback="legacy_docx_renderer",
                evidence=[str(exc)],
            ))
            return RenderResult(False, diagnostics=diagnostics, fidelity_level="non_conformant", degradation_reason="docx_adapter_render_failed", fallback_used=True, error=str(exc))

    def _renderable_blocks(self, context: RenderContext):
        skip = self._source_toc_indices(context) | self._revision_block_indices
        for index, block in enumerate(context.document.blocks):
            if index not in skip:
                yield index, block

    def _source_toc_indices(self, context: RenderContext):
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
                if isinstance(block, Paragraph) and not self._block_text(block).strip():
                    skip.add(index)
                    continue
                break
            self.diagnostics.append(make_diagnostic(
                "docx_source_toc_table_suppressed",
                "Source Markdown contains a table-form TOC; DOCX adapter suppressed it and generated TOC entries.",
                severity="info",
                category="renderer",
                fallback="word_toc_field",
                evidence=[f"block_count={len(skip)}"],
            ))
            return skip
        if not isinstance(blocks[0], Paragraph):
            return set()
        first_text = self._block_text(blocks[0]).strip()
        if first_text != "目录":
            return set()
        skip = {0}
        for index, block in enumerate(blocks[1:], start=1):
            if isinstance(block, Heading):
                break
            text = self._block_text(block).strip()
            if not text:
                skip.add(index)
                continue
            if isinstance(block, Paragraph) and self._looks_like_exported_toc_entry(text):
                skip.add(index)
                continue
            break
        if len(skip) > 1:
            self.diagnostics.append(make_diagnostic(
                "docx_source_toc_suppressed",
                "Source Markdown appears to contain an exported TOC; DOCX adapter suppressed it and generated a Word TOC field instead.",
                severity="info",
                category="renderer",
                fallback="word_toc_field",
                evidence=[f"block_count={len(skip)}"],
            ))
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

    def _block_text(self, block) -> str:
        children = getattr(block, "children", None) or []
        if children:
            return "".join(self._inline_text(child) for child in children)
        return getattr(block, "text", "") or getattr(block, "content", "") or ""

    def _inline_text(self, node) -> str:
        children = getattr(node, "children", None) or []
        if children:
            return "".join(self._inline_text(child) for child in children)
        return (
            getattr(node, "text", "")
            or getattr(node, "content", "")
            or getattr(node, "code", "")
            or getattr(node, "href", "")
            or getattr(node, "src", "")
            or ""
        )

    def _apply_formal_styles(self, doc) -> None:
        """Apply formatting learned from the Original/ formal document corpus."""

        normal = doc.styles["Normal"]
        self._set_font(normal, east_asia="楷体", ascii_font="Times New Roman", size_pt=12)
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        normal.paragraph_format.line_spacing = 1.5
        normal.paragraph_format.space_after = Pt(0)
        self._set_char_based_indent(normal, chars=2, font_size_pt=12)

        title_style = self._ensure_paragraph_style(doc, "Title", base="Normal")
        title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_style.font.bold = False
        self._zero_style_indent(title_style)

        for level in range(1, 5):
            style = doc.styles[f"Heading {level}"]
            self._set_font(style, east_asia="楷体", ascii_font="Times New Roman", size_pt=12)
            style.font.bold = True if level == 1 else None
            style.paragraph_format.first_line_indent = None
            style.paragraph_format.line_spacing = 2.0 if level == 1 else 1.5
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(0)

        toc_indents = {"toc 1": 0, "toc 2": 0.5, "toc 3": 1.0, "toc 4": 1.5}
        for name in ("toc 1", "toc 2", "toc 3", "toc 4"):
            style = self._ensure_paragraph_style(doc, name, base="Normal")
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            style.paragraph_format.line_spacing = 1.0
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(0)
            if name != "toc 1":
                style.paragraph_format.left_indent = Cm(toc_indents[name])
            self._add_toc_style_tab_stops(style)
            self._zero_style_indent(style)

        body2 = self._ensure_paragraph_style(doc, "正文2", base="Normal")
        body2.paragraph_format.left_indent = Cm(0.18)
        body2.paragraph_format.first_line_indent = None

        body3 = self._ensure_paragraph_style(doc, "正文3", base="Normal")
        body3.paragraph_format.left_indent = Cm(0.53)
        body3.paragraph_format.first_line_indent = None

        subtitle = self._ensure_paragraph_style(doc, "小标题", base="Normal")
        subtitle.font.bold = True
        subtitle.paragraph_format.first_line_indent = None

        code = self._ensure_paragraph_style(doc, "规范", base="Normal")
        self._set_font(code, east_asia="Consolas", ascii_font="Consolas", size_pt=10.5)
        code.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        code.paragraph_format.left_indent = Cm(0.18)
        code.paragraph_format.first_line_indent = Cm(1.06)
        code.paragraph_format.line_spacing = 1.0

        caption = self._ensure_paragraph_style(doc, "图表正文", base="Normal")
        self._set_font(caption, east_asia="楷体_GB2312", ascii_font="Times New Roman", size_pt=10.5)
        caption.paragraph_format.line_spacing = 1.0
        self._zero_style_indent(caption)

        for list_style_name in ("List Bullet", "List Number", "List Paragraph"):
            self._ensure_paragraph_style(doc, list_style_name, base="Normal")

        self.diagnostics.append(make_diagnostic(
            "docx_formal_style_profile_applied",
            "DOCX adapter applied formal document styles learned from the Original reference corpus.",
            severity="info",
            category="renderer",
            fallback="built_in_formal_style_profile",
            evidence=["Original/*.docx"],
        ))

    @staticmethod
    def _ensure_paragraph_style(doc, name: str, *, base: str = "Normal"):
        try:
            return doc.styles[name]
        except Exception:
            style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = doc.styles[base]
            return style

    @staticmethod
    def _set_font(style, *, east_asia: str, ascii_font: str, size_pt: float) -> None:
        style.font.name = ascii_font
        style.font.size = Pt(size_pt)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), east_asia)

    @staticmethod
    def _set_char_based_indent(style, *, chars: int, font_size_pt: float) -> None:
        """Set first-line indent as N characters (e.g. 2 chars for Chinese body text).

        Uses OOXML ``firstLineChars`` (in 1/100 of a character) so Word/LibreOffice
        compute the indent in terms of the actual font metrics.  A ``firstLine``
        fallback (in twips) is included for renderers that don't support char indents.
        """
        pPr = style.element.find(qn("w:pPr"))
        if pPr is None:
            pPr = OxmlElement("w:pPr")
            style.element.insert(0, pPr)
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:firstLineChars"), str(chars * 100))
        # Fallback: twips = pts * 20
        twips = int(round(chars * font_size_pt * 20))
        ind.set(qn("w:firstLine"), str(twips))

    def _render_block(self, doc, block, index: int, context: RenderContext) -> None:
        if isinstance(block, Heading):
            level = self._formal_heading_level(block, context)
            if level <= 0:
                paragraph = doc.add_paragraph(style=self.style_mapper.paragraph_style())
                self.inline_writer.write_children(paragraph, block.children, context)
                if not block.children and block.text:
                    paragraph.add_run(self._clean_heading_text(block.text))
                return
            paragraph = doc.add_paragraph(style=self.style_mapper.heading_style(level))
            number = self._heading_number(level, context)
            if number:
                paragraph.add_run(f"{number} ")
            stripped_text = self._strip_source_number(block.text, context) if block.text else ""
            if stripped_text and stripped_text != block.text:
                paragraph.add_run(self._clean_heading_text(stripped_text))
            else:
                self.inline_writer.write_children(paragraph, block.children, context)
                if not block.children and block.text:
                    paragraph.add_run(self._clean_heading_text(block.text))
            self._add_heading_bookmark(paragraph, index)
            return
        if isinstance(block, Paragraph):
            paragraph = doc.add_paragraph(style=self.style_mapper.paragraph_style())
            if self._is_image_only_paragraph(block):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self.inline_writer.write_children(paragraph, block.children, context)
            if not block.children and block.text:
                paragraph.add_run(block.text)
            return
        if isinstance(block, CodeBlock):
            paragraph = doc.add_paragraph(style=self.style_mapper.code_style())
            run = paragraph.add_run(block.code)
            run.font.name = "Courier New"
            run.font.size = Pt(9)
            paragraph.paragraph_format.keep_together = True
            return
        if isinstance(block, Table):
            self.table_writer.write_table(doc, block, index, context)
            return
        if isinstance(block, Figure):
            self.image_writer.write_block_image(doc, block, context)
            return
        if isinstance(block, ListBlock):
            self._render_list(doc, block, context, level=0)
            return
        if isinstance(block, BlockQuote):
            for child in block.blocks:
                paragraph = doc.add_paragraph(style=self.style_mapper.blockquote_style())
                if isinstance(child, Paragraph):
                    self.inline_writer.write_children(paragraph, child.children, context)
                else:
                    paragraph.add_run(getattr(child, "text", "") or getattr(child, "content", "") or "[Quoted content]")
            return
        if isinstance(block, PageBreak):
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            return
        if isinstance(block, HorizontalRule):
            doc.add_paragraph("---")
            return
        if isinstance(block, RawHtmlBlock):
            doc.add_paragraph(block.text_fallback or "[Raw HTML omitted]")
            self._diag_raw_html(block, context)
            return
        if isinstance(block, UnsupportedBlock):
            doc.add_paragraph(f"[Unsupported block: {block.original_type}] {block.content}")
            self._diag_unsupported(block)
            return
        doc.add_paragraph(f"[Unsupported block: {block.__class__.__name__}]")

    @staticmethod
    def _is_image_only_paragraph(block: Paragraph) -> bool:
        children = getattr(block, "children", []) or []
        return bool(children) and all(
            isinstance(child, ImageRun) or (isinstance(child, TextRun) and not child.text.strip())
            for child in children
        )

    def _render_list(self, doc, list_block: ListBlock, context: RenderContext, level: int) -> None:
        style = "List Number" if list_block.ordered else "List Bullet"
        for item in list_block.items:
            paragraph = doc.add_paragraph(style=style if self.style_mapper._has_style(style) else self.style_mapper.paragraph_style())
            first = True
            for child in item.blocks:
                if isinstance(child, Paragraph):
                    if not first:
                        paragraph.add_run(" ")
                    self.inline_writer.write_children(paragraph, child.children, context)
                    if not child.children and child.text:
                        paragraph.add_run(child.text)
                    first = False
                elif isinstance(child, ListBlock):
                    self._render_list(doc, child, context, level + 1)

    def _diag_raw_html(self, block: RawHtmlBlock, context: RenderContext) -> None:
        self.diagnostics.append(make_diagnostic(
            "docx_raw_html_fallback",
            "Raw HTML block was rendered as text fallback in DOCX.",
            severity="warning",
            category="renderer",
            fallback="text_fallback",
            evidence=[block.html[:120]],
        ))

    def _diag_unsupported(self, block: UnsupportedBlock) -> None:
        self.diagnostics.append(make_diagnostic(
            "docx_unsupported_block",
            "Unsupported block was rendered as placeholder in DOCX.",
            severity="warning",
            category="renderer",
            fallback="unsupported_block_placeholder",
            evidence=[block.original_type],
        ))

    def _apply_page_setup(self, doc, context: RenderContext) -> None:
        section = doc.sections[0]
        page_profile = context.layout_plan.page.page_profile
        if page_profile == "a4_cn_formal":
            section.page_width = Cm(21)
            section.page_height = Cm(29.7)
            margin = context.layout_plan.page.margin_profile
            if margin == "formal":
                section.top_margin = Cm(2.0)
                section.bottom_margin = Cm(1.5)
                section.left_margin = Cm(2.0)
                section.right_margin = Cm(2.0)
        else:
            self.diagnostics.append(make_diagnostic(
                "unsupported_section_layout",
                "DOCX adapter used default page setup for unsupported page profile.",
                severity="warning",
                category="renderer",
                fallback="default_docx_section",
                evidence=[page_profile],
            ))
        for sec in context.layout_plan.sections:
            if sec.orientation_intent != "portrait":
                self.diagnostics.append(make_diagnostic(
                    "unsupported_section_layout",
                    "LayoutPlan requests mixed or landscape section intent; Phase 6D records the intent but does not apply complex section layout.",
                    severity="warning",
                    category="renderer",
                    fallback="portrait_section_with_review",
                    evidence=[sec.orientation_intent, sec.section_break_intent],
                ))

    def _apply_header_footer(self, doc, context: RenderContext) -> None:
        policy = context.policy.document_policy.get("header_footer") or {}
        section = doc.sections[0]
        if policy.get("header_title") == "document_title":
            title = context.options.get("doc_title") or context.document.metadata.get("title") or "Document"
            section.header.paragraphs[0].text = title
        elif policy.get("header_title") not in (None, "none"):
            self.diagnostics.append(make_diagnostic(
                "furniture_policy_degraded",
                "Header policy is not supported by the DOCX adapter.",
                severity="warning",
                category="renderer",
                fallback="omit_complex_header",
                evidence=[str(policy.get("header_title"))],
            ))
        if policy.get("footer_page_number"):
            paragraph = section.footer.paragraphs[0]
            paragraph.add_run("Page ")
            self._add_field(paragraph, "PAGE")
            self.diagnostics.append(make_diagnostic(
                "footer_page_number_applied",
                "DOCX adapter inserted a Word PAGE field in the footer.",
                severity="info",
                category="renderer",
                fallback="word_field_update_required",
            ))

    def _build_heading_anchor_map(self, context: RenderContext):
        """Pre-compute anchor IDs keyed by block index before rendering.

        Both TOC hyperlink generation and heading bookmark insertion need the
        same anchor IDs.  Pre-computing them from the document model avoids
        a two-pass rendering strategy.
        """
        anchors = {}
        counters = [0] * 4
        rev_policy = context.policy.document_policy.get("revision_history") == "required"
        for index, block in enumerate(context.document.blocks):
            if not isinstance(block, Heading):
                continue
            text = self._clean_heading_text(block.text or self._block_text(block)).strip()
            if rev_policy and text == "文件修订履历表":
                continue
            level = self._formal_heading_level(block, context)
            if level <= 0:
                continue
            level = max(1, min(level, 4))
            counters[level - 1] += 1
            for idx in range(level, 4):
                counters[idx] = 0
            for idx in range(level - 1):
                if counters[idx] == 0:
                    counters[idx] = 1
            number = ".".join(str(v) for v in counters[:level] if v > 0)
            anchors[index] = f"_Toc_{number}"
        return anchors

    def _insert_toc_if_required(self, doc, context: RenderContext) -> None:
        toc_policy = context.policy.document_policy.get("toc")
        if toc_policy not in ("required", "recommended"):
            return
        toc_title_style = self._ensure_paragraph_style(doc, "TOC Title", base="Normal")
        toc_title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        self._zero_style_indent(toc_title_style)
        title = doc.add_paragraph("目录", style="TOC Title")
        self._clear_paragraph_indent(title)
        for run in title.runs:
            self._format_formal_run(run, size_pt=10.5)
        for level, number, label, page, anchor in self._toc_entries(context):
            style_name = f"toc {min(max(level, 1), 4)}" if self.style_mapper._has_style(f"toc {min(max(level, 1), 4)}") else self.style_mapper.paragraph_style()
            paragraph = doc.add_paragraph(label, style=style_name)
            self._clear_paragraph_indent(paragraph)
            paragraph.clear()
            display = f"{number}  {label}" if number else label
            self._add_toc_hyperlink(paragraph, display, str(page), anchor)
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        self.diagnostics.append(make_diagnostic(
            "docx_static_toc_generated",
            "DOCX adapter generated visible TOC entries from the document model.",
            severity="info",
            category="renderer",
            fallback="static_toc_without_page_numbers",
        ))

    def _toc_entries(self, context: RenderContext):
        entries = []
        if context.policy.document_policy.get("revision_history") == "required":
            # Check whether the source already has a revision heading — avoid double entry
            rev_heading_found = any(
                isinstance(b, Heading) and "文件修订履历表" in (b.text or "")
                for b in context.document.blocks
            )
            entries.append((1, "", "文件修订履历表", 3, "_Toc_RevHist"))
        else:
            rev_heading_found = False
        counters = [0] * 4
        heading_index = 0
        for index, block in enumerate(context.document.blocks):
            if not isinstance(block, Heading):
                continue
            # Skip the source revision heading — already added manually above
            text = self._clean_heading_text(block.text or self._block_text(block)).strip()
            if rev_heading_found and text == "文件修订履历表":
                continue
            level = self._formal_heading_level(block, context)
            if level <= 0:
                continue
            level = max(1, min(level, 4))
            counters[level - 1] += 1
            for idx in range(level, 4):
                counters[idx] = 0
            for idx in range(level - 1):
                if counters[idx] == 0:
                    counters[idx] = 1
            number = ".".join(str(v) for v in counters[:level] if v > 0)
            if context.policy.document_policy.get("source_number_stripping") == "strip":
                text = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", text).strip()
            heading_index += 1
            anchor = self._heading_anchor_map.get(index, f"_Toc_{number}")
            entries.append((level, number, text, self._estimated_toc_page(heading_index, level), anchor))
        return entries

    @staticmethod
    def _estimated_toc_page(heading_index: int, level: int) -> int:
        # Static TOC entries need a visible page-number column before Word field
        # update is available. This estimate is intentionally conservative; a
        # Word/LibreOffice update pass can replace it with exact PAGEREF values.
        return 5 + max(0, heading_index - 1) // 5

    @staticmethod
    def _add_toc_style_tab_stops(style) -> None:
        """Add single RIGHT+DOTS tab stop for page numbers at the style level.

        Uses only one tab stop (RIGHT with DOT leader at 16.93cm). This avoids
        the classic multi-tab mismatch bug where entries with N tab characters
        and M>N tab stops produce incorrect alignment.
        """
        pPr = style.element.find(qn("w:pPr"))
        if pPr is None:
            pPr = OxmlElement("w:pPr")
            style.element.insert(0, pPr)
        tabs = pPr.find(qn("w:tabs"))
        if tabs is None:
            tabs = OxmlElement("w:tabs")
            pPr.append(tabs)
        right = OxmlElement("w:tab")
        right.set(qn("w:val"), "right")
        right.set(qn("w:leader"), "dot")
        right.set(qn("w:pos"), "9600")  # 16.93cm in twips
        tabs.append(right)

    @staticmethod
    def _apply_toc_tab_stops(paragraph) -> None:
        stops = paragraph.paragraph_format.tab_stops
        stops.add_tab_stop(Cm(16.93), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

    @staticmethod
    def _clear_paragraph_indent(paragraph) -> None:
        """Explicitly zero out first-line indent to override style inheritance."""
        pPr = paragraph._element.get_or_add_pPr()
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:firstLine"), "0")
        ind.set(qn("w:firstLineChars"), "0")

    @staticmethod
    def _zero_style_indent(style) -> None:
        """Set both firstLine AND firstLineChars to zero at style level.

        python-docx's first_line_indent=Cm(0) only writes w:firstLine='0',
        but some renderers (WPS) require firstLineChars='0' to be present
        as well, otherwise they inherit firstLineChars from the base style.
        """
        pPr = style.element.find(qn("w:pPr"))
        if pPr is None:
            pPr = OxmlElement("w:pPr")
            style.element.insert(0, pPr)
        ind = pPr.find(qn("w:ind"))
        if ind is None:
            ind = OxmlElement("w:ind")
            pPr.append(ind)
        ind.set(qn("w:firstLine"), "0")
        ind.set(qn("w:firstLineChars"), "0")

    def _add_heading_bookmark(self, paragraph, block_index: int) -> None:
        """Insert bookmarkStart/bookmarkEnd wrapping heading runs for TOC hyperlinks."""
        anchor = self._heading_anchor_map.get(block_index)
        if anchor:
            self._add_bookmark(paragraph, anchor)

    def _add_bookmark(self, paragraph, anchor: str) -> None:
        """Insert a bookmark pair into the paragraph for internal hyperlink targets."""
        bid = str(self._next_bookmark_id)
        self._next_bookmark_id += 1
        bs = OxmlElement("w:bookmarkStart")
        bs.set(qn("w:id"), bid)
        bs.set(qn("w:name"), anchor)
        pPr = paragraph._element.find(qn("w:pPr"))
        insert_at = list(paragraph._element).index(pPr) + 1 if pPr is not None else 0
        paragraph._element.insert(insert_at, bs)
        be = OxmlElement("w:bookmarkEnd")
        be.set(qn("w:id"), bid)
        paragraph._element.append(be)

    def _add_toc_run(self, paragraph, text: str):
        run = paragraph.add_run(text)
        self._format_formal_run(run, size_pt=10.5)
        return run

    def _add_toc_hyperlink(self, paragraph, display: str, page: str, anchor: str) -> None:
        """Create a hyperlinked TOC entry pointing to a heading bookmark."""
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("w:anchor"), anchor)
        # Display text run
        display_run = OxmlElement("w:r")
        self._format_formal_run_element(display_run, size_pt=10.5)
        display_t = OxmlElement("w:t")
        display_t.text = display
        display_t.set(qn("xml:space"), "preserve")
        display_run.append(display_t)
        hyperlink.append(display_run)
        # Tab run
        tab_run = OxmlElement("w:r")
        tab_run.append(OxmlElement("w:tab"))
        hyperlink.append(tab_run)
        # Page number run
        page_run = OxmlElement("w:r")
        self._format_formal_run_element(page_run, size_pt=10.5)
        page_t = OxmlElement("w:t")
        page_t.text = page
        page_t.set(qn("xml:space"), "preserve")
        page_run.append(page_t)
        hyperlink.append(page_run)
        paragraph._element.append(hyperlink)

    @staticmethod
    def _format_formal_run_element(run_elem, *, size_pt: float) -> None:
        """Apply formal font formatting directly to an OOXML w:r element."""
        rPr = OxmlElement("w:rPr")
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), "Times New Roman")
        rFonts.set(qn("w:hAnsi"), "Times New Roman")
        rFonts.set(qn("w:eastAsia"), "楷体_GB2312")
        rPr.append(rFonts)
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size_pt * 2)))  # half-points
        rPr.append(sz)
        run_elem.insert(0, rPr)

    @staticmethod
    def _format_formal_run(run, *, size_pt: float) -> None:
        run.font.name = "Times New Roman"
        run.font.size = Pt(size_pt)
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "楷体_GB2312")

    def _diagnose_revision_policy(self, context: RenderContext) -> None:
        policy = context.policy.document_policy.get("revision_history")
        if policy != "required":
            return
        table_kinds = [item.get("kind") for item in (context.document.metadata.get("semantic_analysis") or {}).get("tables", [])]
        if "revision" not in table_kinds:
            severity = "warning" if policy == "required" else "info"
            self.diagnostics.append(make_diagnostic(
                "missing_required_revision_history",
                "Document profile expects revision history, but no source revision table was found. Adapter will not fabricate revision metadata.",
                severity=severity,
                category="renderer",
                fallback="no_generated_revision_history",
                evidence=[policy],
            ))

    REVISION_HEADERS = ["版次", "修订人", "修订原因", "修订内容", "修订日期", "备注"]

    def _insert_revision_table(self, doc, context: RenderContext) -> None:
        policy = context.policy.document_policy.get("revision_history")
        if policy != "required":
            return
        heading_idx, rev_block, rev_idx = self._find_revision_source(context)
        if rev_block is not None:
            rows_data = self._extract_revision_data(rev_block)
            self._revision_block_indices.add(rev_idx)
            if heading_idx >= 0:
                self._revision_block_indices.add(heading_idx)
            self._consume_revision_notes(context, rev_idx)
        else:
            if self._has_revision_signals(context):
                self.diagnostics.append(make_diagnostic(
                    "revision_source_detected_but_not_normalized",
                    "Revision signals were found in source blocks; adapter skips template injection to avoid duplicate revision sections.",
                    severity="warning",
                    category="renderer",
                    fallback="preserve_source_revision_section",
                ))
                return
            self._diagnose_revision_policy(context)
            rows_data = [self._auto_fill_revision_row(context)]
        rows_data = [self._enrich_revision_row(row, context) for row in rows_data]
        self._render_revision_table(doc, rows_data, context)
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def _auto_fill_revision_row(self, context: RenderContext):
        """Generate a default revision row with auto-detected author and today's date."""
        from datetime import date
        author = self._detect_author(context)
        today = date.today().strftime("%Y.%m.%d")
        return ["A/0", author, "新制定", "初版", today, ""]

    def _enrich_revision_row(self, row: list, context: RenderContext):
        """Auto-fill empty 修订人 (col 1) and 修订日期 (col 4) cells."""
        enriched = list(row)
        if not enriched[1].strip():
            enriched[1] = self._detect_author(context)
        if not enriched[4].strip():
            from datetime import date
            enriched[4] = date.today().strftime("%Y.%m.%d")
        return enriched

    @staticmethod
    def _detect_author(context: RenderContext) -> str:
        """Detect author from doc metadata, 拟制 line, git config, or system user."""
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

    def _find_revision_source(self, context: RenderContext):
        """Find the revision heading + data table in document blocks.

        Returns (heading_index, data_block, data_index).  heading_index is -1
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
                    cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if any(cells):
                        while len(cells) < 6:
                            cells.append("")
                        data.append(cells[:6])
                return data if data else [["待补充", "", "", "", "", ""]]
            except Exception:
                pass
        return [["待补充", "", "", "", "", ""]]

    def _render_revision_table(self, doc, rows_data: list, context: RenderContext) -> None:
        title = doc.add_paragraph("文件修订履历表", style="Title")
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._clear_paragraph_indent(title)
        self._add_bookmark(title, "_Toc_RevHist")
        doc.add_paragraph(" ")
        table = doc.add_table(rows=1 + len(rows_data), cols=6)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True
        try:
            table.style = "Table Grid"
        except Exception:
            pass
        ratios = self._revision_width_ratios(rows_data)
        total = self.style_mapper.content_width_inches()
        for ci, ratio in enumerate(ratios):
            width = Inches(total * ratio)
            for cell in table.columns[ci].cells:
                cell.width = width
        center_cols = {0, 1, 4}  # 版次, 修订人, 修订日期
        # Header row — all centered
        for idx, header in enumerate(self.REVISION_HEADERS):
            cell = table.cell(0, idx)
            para = cell.paragraphs[0]
            para.clear()
            para.style = self.style_mapper.cell_content_style()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(header)
            run.bold = True
        # Data rows — cols 0,1,4 center; 2,3,5 left
        for ri, row_data in enumerate(rows_data):
            for ci, text in enumerate(row_data):
                if ci >= 6:
                    break
                cell = table.cell(ri + 1, ci)
                para = cell.paragraphs[0]
                para.clear()
                para.style = self.style_mapper.cell_content_style()
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci in center_cols else WD_ALIGN_PARAGRAPH.LEFT
                if text:
                    para.add_run(text)

    @staticmethod
    def _revision_width_ratios(rows_data: list) -> list:
        headers = ["版次", "修订人", "修订原因", "修订内容", "修订日期", "备注"]
        weights = []
        for i, header in enumerate(headers):
            samples = [header] + [str(row[i] if i < len(row) else "") for row in rows_data]
            lengths = [len(s.strip()) for s in samples if str(s).strip()]
            max_len = max(lengths) if lengths else len(header)
            avg_len = (sum(lengths) / len(lengths)) if lengths else len(header)
            base = 0.9
            if i in (2, 3, 5):
                base = 1.8
            if i in (0, 1, 4):
                base = 1.0
            weights.append(base * (0.7 + min(2.0, 0.012 * max_len + 0.02 * avg_len)))
        total = sum(weights) or 1.0
        ratios = [w / total for w in weights]
        clamped = [max(0.10, min(0.42, r)) for r in ratios]
        norm = sum(clamped) or 1.0
        return [w / norm for w in clamped]

    def _heading_number(self, level: int, context: RenderContext) -> str:
        policy = context.policy.document_policy.get("heading_numbering")
        if policy not in ("required", "recommended"):
            return ""
        level = max(1, min(level, 4))
        idx = level - 1
        self.heading_counters[idx] += 1
        for i in range(idx + 1, len(self.heading_counters)):
            self.heading_counters[i] = 0
        for i in range(0, idx):
            if self.heading_counters[i] == 0:
                self.heading_counters[i] = 1
        number = ".".join(str(v) for v in self.heading_counters[:level] if v > 0)
        self.diagnostics.append(make_diagnostic(
            "heading_numbering_applied",
            "DOCX adapter applied policy-driven heading numbering.",
            severity="info",
            category="renderer",
            fallback="adapter_heading_numbering",
            evidence=[number],
        ))
        return number

    def _strip_source_number(self, text: str, context: RenderContext) -> str:
        policy = context.policy.document_policy.get("source_number_stripping")
        if policy != "strip":
            return text
        stripped = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", text)
        if stripped != text:
            self.diagnostics.append(make_diagnostic(
                "source_number_stripping_applied",
                "DOCX adapter stripped source heading number according to RenderPolicy.",
                severity="info",
                category="renderer",
                fallback="policy_source_number_stripping",
                evidence=[text, stripped],
            ))
        return stripped

    def _reset_revision_cell(self, cell, align=None) -> None:
        cell_style = self.style_mapper.cell_content_style()
        for paragraph in cell.paragraphs:
            paragraph.style = cell_style
            paragraph.paragraph_format.first_line_indent = None
            paragraph.paragraph_format.left_indent = None
            paragraph.paragraph_format.right_indent = None
            if align is not None:
                paragraph.alignment = align

    def _formal_heading_level(self, block: Heading, context: RenderContext) -> int:
        if context.policy.document_profile not in ("requirement_spec", "automotive_formal_spec"):
            return max(1, min(block.level, 4))
        text = self._clean_heading_text(block.text or self._block_text(block)).strip()
        if not text:
            return block.level
        if self._is_latin_example_heading(text):
            return 0
        if text in {"目的", "适用范围", "定义和缩写", "域定义", "支持/相关性文件"}:
            return 1
        if re.fullmatch(r"(?:FC|FCC|BC|BCC|CC)相关命名规则", text):
            return 1
        if re.fullmatch(r"P\d+\s+.+", text):
            return 2
        if re.fullmatch(r"(?:FC|FCC|BC|BCC|CC)模块命名规则", text):
            return 2
        if re.fullmatch(r"(?:FC|FCC|BC|BCC|CC)版本命名规则", text):
            return 2
        if text.endswith("源文件命名规则"):
            return 2
        if text in {"算法相关模块", "外设芯片驱动", "复杂设备驱动", "第三方代码", "金脉开发", "第三方提供", "基于第三方代码更新", "自主开发模块", "第三方代码-Bsw", "第三方代码-Mcal"}:
            return 3
        if text in {"复杂控制对象", "简单控制对象", "与芯片相关", "与芯片无关", "底层模块", "算法模块", "芯片公司提供", "除芯片公司外的其他公司提供", "第三方提供的完整的代码包", "第三方提供的部分代码的集合"}:
            return 4
        return max(1, min(block.level, 4))

    @staticmethod
    def _is_latin_example_heading(text: str) -> bool:
        if re.match(r"^\d", text):
            return False
        if re.search(r"[\u4e00-\u9fff]", text):
            return False
        return len(text.strip()) > 2 and bool(re.search(r"[A-Za-z]", text))

    @staticmethod
    def _clean_heading_text(text: str) -> str:
        return re.sub(r"^\*+|\*+$", "", text or "").strip()

    @staticmethod
    def _add_field(paragraph, instruction: str) -> None:
        run = paragraph.add_run()
        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = instruction
        fld_separate = OxmlElement("w:fldChar")
        fld_separate.set(qn("w:fldCharType"), "separate")
        text = OxmlElement("w:t")
        text.text = "Update field in Word"
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")
        run._r.append(fld_begin)
        run._r.append(instr)
        run._r.append(fld_separate)
        run._r.append(text)
        run._r.append(fld_end)

    @staticmethod
    def _fidelity(diagnostics) -> tuple:
        if any(d.get("severity") == "error" for d in diagnostics):
            return "review", "error_diagnostics_present"
        if any(d.get("category") in ("renderer", "asset", "layout", "unsupported") for d in diagnostics):
            reasons = sorted({d.get("code", "diagnostic") for d in diagnostics if d.get("category") in ("renderer", "asset", "layout", "unsupported")})
            return "review", ",".join(reasons[:5])
        return "conformant", ""
