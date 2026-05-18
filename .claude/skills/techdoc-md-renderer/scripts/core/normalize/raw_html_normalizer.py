"""Normalize images embedded in raw HTML into standard image semantics."""

from __future__ import annotations

from typing import List

from diagnostics import make_diagnostic
from core.model import Figure, ImageRun, RawHtmlBlock, SourcePosition, TextRun

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


def extract_raw_html_images(html: str) -> List[ImageRun]:
    """Extract <img> tags from raw HTML as ImageRun nodes."""

    if not html or BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    images: List[ImageRun] = []
    for img in soup.find_all("img"):
        src = img.get("src", "") or ""
        alt = img.get("alt", "") or ""
        title = img.get("title", "") or ""
        width = img.get("width", "") or _style_value(img.get("style", ""), "width")
        height = img.get("height", "") or _style_value(img.get("style", ""), "height")
        diagnostics = [
            make_diagnostic(
                "raw_html_image_normalized",
                "Raw HTML <img> was normalized into an ImageRun for semantic analysis and renderer adapters.",
                severity="info",
                category="normalization",
                fallback="preserve_raw_html_source",
                evidence=[src],
            )
        ]
        images.append(ImageRun(
            src=src,
            alt=alt,
            title=title,
            width=width,
            height=height,
            raw_html=str(img),
            source_kind="raw_html_img",
            diagnostics=diagnostics,
        ))
    return images


def normalize_raw_html_block(html: str, diagnostics, source_position: SourcePosition):
    """Return blocks preserving raw HTML while exposing image references.

    Pure image-only raw HTML becomes Figure nodes that carry raw_html on the
    ImageRun. Complex HTML is preserved as RawHtmlBlock and image references are
    additionally exposed as Figure nodes.
    """

    images = extract_raw_html_images(html)
    if not images:
        return [RawHtmlBlock(
            html=html,
            text_fallback=_html_text_fallback(html),
            diagnostics=diagnostics,
            source_position=source_position,
        )]

    blocks = []
    if not _is_image_only_html(html):
        raw_diagnostics = list(diagnostics)
        raw_diagnostics.append(make_diagnostic(
            "complex_raw_html_preserved_with_images_extracted",
            "Complex raw HTML was preserved while image references were normalized separately.",
            severity="warning",
            category="normalization",
            fallback="preserve_raw_html_and_expose_images",
            evidence=[html[:120]],
        ))
        blocks.append(RawHtmlBlock(
            html=html,
            text_fallback=_html_text_fallback(html),
            diagnostics=raw_diagnostics,
            source_position=source_position,
        ))

    for idx, image in enumerate(images):
        blocks.append(Figure(
            image=image,
            caption=[TextRun(text=image.alt)] if image.alt else [],
            diagnostics=list(image.diagnostics),
            source_position=SourcePosition(source_hint=f"{source_position.source_hint}/raw-img{idx}"),
        ))
    return blocks


def raw_html_images_as_inline(html: str):
    return extract_raw_html_images(html)


def _style_value(style: str, key: str) -> str:
    for part in (style or "").split(";"):
        if ":" not in part:
            continue
        name, value = part.split(":", 1)
        if name.strip().lower() == key:
            return value.strip()
    return ""


def _is_image_only_html(html: str) -> bool:
    if BeautifulSoup is None:
        return False
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("", strip=True)
    if text:
        return False
    for img in soup.find_all("img"):
        img.extract()
    leftovers = str(soup).strip()
    return not leftovers or leftovers in ("<html><body></body></html>", "<body></body>")


def _html_text_fallback(html: str) -> str:
    if BeautifulSoup is not None:
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return ""
