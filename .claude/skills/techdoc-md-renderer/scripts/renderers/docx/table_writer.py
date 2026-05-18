"""DOCX table writer consuming LayoutPlan table intent."""

from __future__ import annotations

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

from diagnostics import make_diagnostic
from core.model import BreakRun, EmphasisRun, ImageRun, LinkRun, StrongRun, TextRun
from .inline_writer import DocxInlineWriter


class DocxTableWriter:
    def __init__(self, style_mapper, diagnostics):
        self.style_mapper = style_mapper
        self.diagnostics = diagnostics
        self.inline_writer = DocxInlineWriter(diagnostics)

    def write_table(self, document, table_node, block_index: int, context) -> None:
        rows = table_node.rows
        if not rows:
            return
        col_count = max(len(row.cells) for row in rows)
        table_layout = next((item for item in context.layout_plan.tables if item.block_index == block_index), None)
        docx_table = document.add_table(rows=len(rows), cols=col_count)
        try:
            docx_table.style = self.style_mapper.table_style()
        except Exception:
            pass
        docx_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        docx_table.autofit = True
        self._apply_column_widths(docx_table, table_layout, col_count)
        tokens = self.style_mapper.table_kind_style_tokens(table_layout.kind if table_layout else "generic")

        for r_idx, row in enumerate(rows):
            header_texts = self._normalized_header_texts(row, col_count) if row.header else None
            for c_idx in range(col_count):
                cell_node = row.cells[c_idx] if c_idx < len(row.cells) else None
                if cell_node is None:
                    # When colspan was used, later columns may be None but have header text
                    if header_texts and c_idx < len(header_texts) and header_texts[c_idx]:
                        cell = docx_table.cell(r_idx, c_idx)
                        paragraph = cell.paragraphs[0]
                        paragraph.style = self.style_mapper.cell_content_style()
                        self._reset_cell_paragraph(paragraph, "center")
                        if row.header:
                            self._shade_cell(cell, tokens["header_fill"])
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        paragraph.add_run(header_texts[c_idx])
                        if row.header:
                            for run in paragraph.runs:
                                run.bold = True
                        self._apply_cell_run_font(paragraph)
                    continue
                if cell_node.colspan > 1 or cell_node.rowspan > 1:
                    self.diagnostics.append(make_diagnostic(
                        "docx_complex_table_span_unsupported",
                        "DOCX adapter does not handle complex colspan/rowspan yet.",
                        severity="warning",
                        category="renderer",
                        fallback="span_ignored",
                        evidence=[f"row={r_idx}", f"col={c_idx}", f"colspan={cell_node.colspan}", f"rowspan={cell_node.rowspan}"],
                    ))
                cell = docx_table.cell(r_idx, c_idx)
                if table_layout and c_idx < len(table_layout.columns):
                    cell.width = Inches(self.style_mapper.content_width_inches() * table_layout.columns[c_idx].width_ratio)
                paragraph = cell.paragraphs[0]
                paragraph.style = self.style_mapper.cell_content_style()
                self._reset_cell_paragraph(paragraph, cell_node.align)
                contains_image = self._cell_contains_image(cell_node)
                image_only = self._cell_is_image_only(cell_node)
                image_width = self._cell_image_max_width_inches(table_layout, c_idx, col_count)
                if row.header:
                    self._shade_cell(cell, tokens["header_fill"])
                    if c_idx == 0:
                        self._set_repeat_header(row=docx_table.rows[r_idx], row_index=r_idx)
                elif table_layout and c_idx < len(table_layout.columns) and table_layout.columns[c_idx].role == "code" and tokens.get("code_fill"):
                    self._shade_cell(cell, tokens["code_fill"])
                if row.header or contains_image:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                self.inline_writer.write_children(
                    paragraph,
                    cell_node.children,
                    context,
                    image_max_width_inches=image_width,
                    image_target_width_inches=image_width if image_only else None,
                    ignore_declared_image_width=image_only,
                )
                cell_text = (cell_node.text or "").strip()
                if not cell_node.children and cell_text:
                    paragraph.add_run(cell_text)
                elif not cell_node.children and not cell_text and header_texts and c_idx < len(header_texts) and header_texts[c_idx]:
                    paragraph.add_run(header_texts[c_idx])
                if row.header:
                    self._clamp_header_to_two_lines(paragraph, table_layout, c_idx, col_count)
                    for run in paragraph.runs:
                        run.bold = True
                self._apply_cell_run_font(paragraph)

        if table_layout and table_layout.overflow_risk != "low":
            self.diagnostics.append(make_diagnostic(
                "docx_table_layout_review",
                "DOCX table was written with layout risk from LayoutPlan.",
                severity="warning",
                category="renderer",
                fallback=table_layout.fallback_strategy,
                evidence=[f"kind={table_layout.kind}", f"overflow={table_layout.overflow_risk}", f"landscape={table_layout.landscape_recommendation}"],
            ))
        if table_layout and table_layout.landscape_recommendation == "recommended":
            self.diagnostics.append(make_diagnostic(
                "docx_landscape_recommendation_not_applied",
                "LayoutPlan recommends landscape for this table; DOCX adapter records the intent but does not change sections in Phase 6C.",
                severity="warning",
                category="renderer",
                fallback="portrait_table_with_review",
                evidence=[f"kind={table_layout.kind}", f"table_index={table_layout.table_index}"],
            ))
        if table_layout and table_layout.wrap_policy:
            self.diagnostics.append(make_diagnostic(
                "docx_table_wrap_policy_recorded",
                "DOCX adapter preserved table wrap policy as rendering intent; exact OOXML wrapping remains adapter-specific.",
                severity="info",
                category="renderer",
                fallback="default_word_cell_wrapping",
                evidence=[table_layout.wrap_policy],
            ))

    @staticmethod
    def _normalized_header_texts(row, col_count: int):
        """Auto-fill empty header cells, expanding colspan cells and duplicating adjacent text."""
        texts = []
        c_idx = 0
        for cell_node in row.cells:
            text = (cell_node.text or "").strip() if cell_node else ""
            span = max(getattr(cell_node, "colspan", 1) or 1, 1)
            for _ in range(span):
                texts.append(text)
                c_idx += 1
        while len(texts) < col_count:
            texts.append("")
        for i in range(col_count):
            if not texts[i]:
                for left in range(i - 1, -1, -1):
                    if texts[left]:
                        texts[i] = texts[left]
                        break
                if not texts[i]:
                    for right in range(i + 1, col_count):
                        if texts[right]:
                            texts[i] = texts[right]
                            break
        return texts[:col_count]

    @staticmethod
    def _reset_cell_paragraph(paragraph, align: str = "") -> None:
        paragraph.paragraph_format.first_line_indent = None
        paragraph.paragraph_format.left_indent = None
        paragraph.paragraph_format.right_indent = None
        paragraph.paragraph_format.space_before = None
        paragraph.paragraph_format.space_after = None
        normalized = (align or "").strip().lower()
        if normalized == "center":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif normalized == "right":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif normalized == "left":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    def _apply_column_widths(self, table, table_layout, col_count: int) -> None:
        if not table_layout or not table_layout.columns:
            self.diagnostics.append(make_diagnostic(
                "docx_table_width_intent_missing",
                "Table has no LayoutPlan column width intent; Word defaults are used.",
                severity="warning",
                category="renderer",
                fallback="word_auto_width",
            ))
            return
        total = self.style_mapper.content_width_inches()
        for idx in range(min(col_count, len(table_layout.columns))):
            width = Inches(total * table_layout.columns[idx].width_ratio)
            for cell in table.columns[idx].cells:
                cell.width = width
        if len(table_layout.columns) != col_count:
            self.diagnostics.append(make_diagnostic(
                "docx_table_width_intent_partial",
                "LayoutPlan column count does not match rendered table columns.",
                severity="warning",
                category="renderer",
                fallback="partial_width_application",
                evidence=[f"layout_columns={len(table_layout.columns)}", f"rendered_columns={col_count}"],
            ))

    def _cell_image_max_width_inches(self, table_layout, column_index: int, col_count: int) -> float:
        total = self.style_mapper.content_width_inches()
        if table_layout and column_index < len(table_layout.columns):
            column_width = total * table_layout.columns[column_index].width_ratio
        else:
            column_width = total / max(col_count, 1)
        return max(0.35, min(column_width * 0.88, 2.4))

    def _clamp_header_to_two_lines(self, paragraph, table_layout, column_index: int, col_count: int) -> None:
        text = (paragraph.text or "").strip()
        if not text:
            return
        width_inches = self._column_width_inches(table_layout, column_index, col_count)
        max_chars_per_line = max(6, int(width_inches * 8.5))
        max_chars_total = max_chars_per_line * 2
        compact = " ".join(text.split())
        if len(compact) <= max_chars_total:
            return
        clipped = compact[: max(1, max_chars_total - 1)] + "…"
        first = clipped[:max_chars_per_line]
        second = clipped[max_chars_per_line:]
        display = first + ("\n" + second if second else "")
        paragraph.clear()
        paragraph.add_run(display)

    def _column_width_inches(self, table_layout, column_index: int, col_count: int) -> float:
        total = self.style_mapper.content_width_inches()
        if table_layout and column_index < len(table_layout.columns):
            return total * table_layout.columns[column_index].width_ratio
        return total / max(col_count, 1)

    def _cell_contains_image(self, cell_node) -> bool:
        return any(self._inline_contains_image(child) for child in getattr(cell_node, "children", []) or [])

    def _cell_is_image_only(self, cell_node) -> bool:
        children = getattr(cell_node, "children", []) or []
        return bool(children) and any(self._inline_contains_image(child) for child in children) and all(
            self._inline_is_image_or_blank(child) for child in children
        )

    def _inline_contains_image(self, node) -> bool:
        if isinstance(node, ImageRun):
            return True
        return any(self._inline_contains_image(child) for child in getattr(node, "children", []) or [])

    def _inline_is_image_or_blank(self, node) -> bool:
        if isinstance(node, ImageRun):
            return True
        if isinstance(node, TextRun):
            return not node.text.strip()
        if isinstance(node, BreakRun):
            return True
        if isinstance(node, (StrongRun, EmphasisRun, LinkRun)):
            return all(self._inline_is_image_or_blank(child) for child in getattr(node, "children", []) or [])
        return False

    def _set_repeat_header(self, row, row_index: int) -> None:
        if row_index != 0 or not self.style_mapper.repeat_table_header_enabled():
            return
        try:
            tr_pr = row._tr.get_or_add_trPr()
            tbl_header = OxmlElement("w:tblHeader")
            tbl_header.set(qn("w:val"), "true")
            tr_pr.append(tbl_header)
        except Exception as exc:
            self.diagnostics.append(make_diagnostic(
                "docx_repeat_header_not_applied",
                "DOCX repeat header row could not be applied.",
                severity="warning",
                category="renderer",
                fallback="single_header_row",
                evidence=[str(exc)],
            ))

    @staticmethod
    def _shade_cell(cell, fill: str) -> None:
        if not fill:
            return
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = tc_pr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tc_pr.append(shd)
        shd.set(qn("w:fill"), fill)

    @staticmethod
    def _apply_cell_run_font(paragraph) -> None:
        """Apply explicit 图表正文 font (楷体_GB2312 10.5pt) on every run.

        Style inheritance alone is not reliable across all Word renderers;
        explicit run-level font ensures consistent cell content formatting.
        """
        from docx.shared import Pt
        for run in paragraph.runs:
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.insert(0, rFonts)
            rFonts.set(qn("w:eastAsia"), "楷体_GB2312")
            rFonts.set(qn("w:ascii"), "Times New Roman")
            rFonts.set(qn("w:hAnsi"), "Times New Roman")
            sz = rPr.find(qn("w:sz"))
            if sz is None:
                sz = OxmlElement("w:sz")
                rPr.append(sz)
            sz.set(qn("w:val"), "21")  # 10.5pt in half-points
            szCs = rPr.find(qn("w:szCs"))
            if szCs is None:
                szCs = OxmlElement("w:szCs")
                rPr.append(szCs)
            szCs.set(qn("w:val"), "21")
