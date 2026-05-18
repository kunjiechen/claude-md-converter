"""DOCX image writing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from docx.shared import Inches
from docx.image.image import Image as DocxImage

from diagnostics import make_diagnostic
from core.model import EmphasisRun, StrongRun, TextRun


class DocxAssetResolver:
    """Resolve assets only from AssetAnalysis metadata."""

    @staticmethod
    def resolve(context, src: str) -> Dict[str, Any]:
        semantic = context.document.metadata.get("semantic_analysis") or {}
        for asset in semantic.get("assets") or []:
            attrs: Dict[str, Any] = asset.get("attributes") or {}
            if attrs.get("src") == src:
                return {
                    "status": asset.get("kind", ""),
                    "resolved_path": attrs.get("resolved_path"),
                    "diagnostics": asset.get("diagnostics") or [],
                }
        return {"status": "unknown_asset", "resolved_path": None, "diagnostics": []}


class DocxImageWriter:
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        self.asset_resolver = DocxAssetResolver()

    def write_inline_image(
        self,
        paragraph,
        image,
        context,
        *,
        max_width_inches: float | None = None,
        target_width_inches: float | None = None,
        ignore_declared_width: bool = False,
    ) -> None:
        asset = self.asset_resolver.resolve(context, image.src)
        status = asset["status"]
        resolved = asset["resolved_path"]
        if status == "svg":
            self._write_svg_placeholder(paragraph, image.src)
            return
        if status == "local_image" and resolved and Path(resolved).exists():
            try:
                width = Inches(self._target_width_inches(
                    context,
                    image,
                    resolved,
                    max_width_inches=max_width_inches,
                    target_width_inches=target_width_inches,
                    ignore_declared_width=ignore_declared_width,
                ))
                paragraph.add_run().add_picture(str(resolved), width=width)
                self.diagnostics.append(make_diagnostic(
                    "docx_image_scaling_applied",
                    "DOCX image inserted with max-width policy while preserving aspect ratio.",
                    severity="info",
                    category="renderer",
                    fallback="max_width_policy",
                    evidence=[image.src, f"max_width_inches={max_width_inches or self._max_width_inches(context)}"],
                ))
                return
            except Exception as exc:
                self.diagnostics.append(make_diagnostic(
                    "docx_image_insert_failed",
                    "Local image could not be inserted into DOCX.",
                    severity="warning",
                    category="renderer",
                    fallback="image_placeholder",
                    evidence=[image.src, str(exc)],
                ))
        self._write_placeholder(paragraph, image.src, status or "unknown_asset")

    def write_block_image(self, document, figure, context) -> None:
        paragraph = document.add_paragraph()
        try:
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception:
            pass
        self.write_inline_image(paragraph, figure.image, context)
        caption = self._caption_text(figure.caption)
        if caption:
            document.add_paragraph(caption)

    def _write_placeholder(self, paragraph, src: str, status: str) -> None:
        paragraph.add_run(f"[Image unavailable: {src}]")
        self.diagnostics.append(make_diagnostic(
            "docx_image_placeholder",
            "Image was rendered as a DOCX placeholder.",
            severity="warning",
            category="renderer",
            fallback="image_placeholder",
            evidence=[src, status],
        ))

    def _write_svg_placeholder(self, paragraph, src: str) -> None:
        paragraph.add_run(f"[SVG image unsupported in DOCX adapter: {src}]")
        self.diagnostics.append(make_diagnostic(
            "docx_svg_unsupported",
            "SVG image is not inserted by the DOCX adapter in Phase 6C.",
            severity="warning",
            category="renderer",
            fallback="svg_placeholder",
            evidence=[src],
        ))

    @staticmethod
    def _caption_text(caption_nodes) -> str:
        parts = []
        for node in caption_nodes or []:
            if isinstance(node, TextRun):
                parts.append(node.text)
            elif isinstance(node, (StrongRun, EmphasisRun)):
                parts.append(DocxImageWriter._caption_text(node.children))
            else:
                parts.append(getattr(node, "text", "") or getattr(node, "content", ""))
        return "".join(parts).strip()

    @staticmethod
    def _max_width_inches(context) -> float:
        adapter_policy = ((context.policy.renderer_policy.get("docx") or {}).get("adapter_policy") or {})
        return float(adapter_policy.get("max_image_width_inches", 5.8))

    def _target_width_inches(
        self,
        context,
        image,
        resolved: str,
        *,
        max_width_inches: float | None = None,
        target_width_inches: float | None = None,
        ignore_declared_width: bool = False,
    ) -> float:
        max_width = float(max_width_inches or self._max_width_inches(context))
        if target_width_inches and target_width_inches > 0:
            return max(0.1, min(float(target_width_inches), max_width))
        declared = None if ignore_declared_width else self._declared_width_inches(getattr(image, "width", "") or "")
        natural = self._natural_width_inches(resolved)
        candidates = [value for value in (declared, natural, max_width) if value and value > 0]
        if not candidates:
            return max_width
        return max(0.1, min(candidates))

    @staticmethod
    def _natural_width_inches(resolved: str) -> float | None:
        try:
            image = DocxImage.from_file(resolved)
            return float(image.width) / 914400.0
        except Exception:
            return None

    @staticmethod
    def _declared_width_inches(value: str) -> float | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        try:
            if text.endswith("in"):
                return float(text[:-2])
            if text.endswith("cm"):
                return float(text[:-2]) / 2.54
            if text.endswith("mm"):
                return float(text[:-2]) / 25.4
            if text.endswith("pt"):
                return float(text[:-2]) / 72.0
            if text.endswith("px"):
                return float(text[:-2]) / 96.0
        except ValueError:
            return None
        return None
