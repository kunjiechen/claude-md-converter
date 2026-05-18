"""DOCX inline node writer."""

from __future__ import annotations

from docx.shared import Pt

from diagnostics import make_diagnostic
from core.model import (
    BreakRun,
    EmphasisRun,
    ImageRun,
    InlineCode,
    LinkRun,
    MathRun,
    RawInlineHtml,
    StrongRun,
    TextRun,
    UnsupportedInline,
)
from .image_writer import DocxImageWriter


class DocxInlineWriter:
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        self.image_writer = DocxImageWriter(diagnostics)

    def write_children(
        self,
        paragraph,
        children,
        context,
        *,
        image_max_width_inches: float | None = None,
        image_target_width_inches: float | None = None,
        ignore_declared_image_width: bool = False,
    ) -> None:
        for child in children:
            self.write_node(
                paragraph,
                child,
                context,
                image_max_width_inches=image_max_width_inches,
                image_target_width_inches=image_target_width_inches,
                ignore_declared_image_width=ignore_declared_image_width,
            )

    def write_node(
        self,
        paragraph,
        node,
        context,
        *,
        bold: bool = False,
        italic: bool = False,
        image_max_width_inches: float | None = None,
        image_target_width_inches: float | None = None,
        ignore_declared_image_width: bool = False,
    ) -> None:
        if isinstance(node, TextRun):
            run = paragraph.add_run(node.text)
            run.bold = bold or None
            run.italic = italic or None
            return
        if isinstance(node, StrongRun):
            for child in node.children:
                self.write_node(
                    paragraph,
                    child,
                    context,
                    bold=True,
                    italic=italic,
                    image_max_width_inches=image_max_width_inches,
                    image_target_width_inches=image_target_width_inches,
                    ignore_declared_image_width=ignore_declared_image_width,
                )
            return
        if isinstance(node, EmphasisRun):
            for child in node.children:
                self.write_node(
                    paragraph,
                    child,
                    context,
                    bold=bold,
                    italic=True,
                    image_max_width_inches=image_max_width_inches,
                    image_target_width_inches=image_target_width_inches,
                    ignore_declared_image_width=ignore_declared_image_width,
                )
            return
        if isinstance(node, InlineCode):
            run = paragraph.add_run(node.code)
            run.font.name = "Courier New"
            run.font.size = Pt(10)
            return
        if isinstance(node, LinkRun):
            text = "".join(getattr(c, "text", "") for c in node.children) or node.href
            paragraph.add_run(f"{text} ({node.href})" if node.href else text)
            return
        if isinstance(node, ImageRun):
            self.image_writer.write_inline_image(
                paragraph,
                node,
                context,
                max_width_inches=image_max_width_inches,
                target_width_inches=image_target_width_inches,
                ignore_declared_width=ignore_declared_image_width,
            )
            return
        if isinstance(node, MathRun):
            paragraph.add_run(node.content)
            return
        if isinstance(node, BreakRun):
            paragraph.add_run().add_break()
            return
        if isinstance(node, RawInlineHtml):
            paragraph.add_run(node.text_fallback or "[Raw inline HTML]")
            self.diagnostics.append(make_diagnostic(
                "docx_raw_inline_html_fallback",
                "Raw inline HTML was rendered as text fallback in DOCX.",
                severity="warning",
                category="renderer",
                fallback="text_fallback",
                evidence=[(node.html or node.text_fallback)[:120]],
            ))
            return
        if isinstance(node, UnsupportedInline):
            paragraph.add_run(f"[Unsupported inline: {node.original_type}]")
            self.diagnostics.append(make_diagnostic(
                "docx_unsupported_inline",
                "Unsupported inline node was rendered as placeholder in DOCX.",
                severity="warning",
                category="renderer",
                fallback="unsupported_inline_placeholder",
                evidence=[node.original_type],
            ))
