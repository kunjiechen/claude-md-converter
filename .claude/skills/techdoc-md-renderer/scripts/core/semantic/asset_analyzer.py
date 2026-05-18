"""Asset semantic analysis for images and resource references."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse

from diagnostics import make_diagnostic
from core.model import Document, ImageRun
from .results import AnalysisResult, Evidence
from .rules import RASTER_IMAGE_FORMATS, SUPPORTED_IMAGE_FORMATS
from .utils import walk_blocks, walk_inline_images


class AssetAnalyzer:
    @classmethod
    def analyze(cls, document: Document, *, base_path: Optional[Path] = None) -> List[AnalysisResult]:
        results: List[AnalysisResult] = []
        for index, image in enumerate(cls._images(document)):
            results.append(cls._analyze_image(image, index, base_path=base_path))
        return results

    @staticmethod
    def _images(document: Document) -> Iterable[ImageRun]:
        for block in walk_blocks(document):
            yield from walk_inline_images(block)

    @classmethod
    def _analyze_image(cls, image: ImageRun, index: int, *, base_path: Optional[Path]) -> AnalysisResult:
        src = image.src or ""
        diagnostics = list(image.diagnostics)
        evidence = [
            Evidence("src", "image source reference", src),
            Evidence("alt", "image alternate text", image.alt),
        ]
        attributes = {
            "asset_index": index,
            "src": src,
            "width": getattr(image, "width", ""),
            "height": getattr(image, "height", ""),
            "source_kind": getattr(image, "source_kind", ""),
            "raw_html": getattr(image, "raw_html", ""),
        }
        fallback = "use_asset_reference"
        confidence = 0.90
        kind = "local_image"

        if not src:
            kind, confidence, fallback = "missing_asset", 0.0, "declare_missing_asset"
        elif src.startswith("data:"):
            kind, confidence, fallback = "data_uri", 0.95, "preserve_data_uri"
        elif urlparse(src).scheme in ("http", "https"):
            kind, confidence, fallback = "remote_image", 0.85, "preserve_remote_reference"
        else:
            suffix = Path(src).suffix.lower()
            if suffix == ".svg":
                kind, confidence, fallback = "svg", 0.90, "preserve_svg_or_prerender_when_required"
            elif suffix and suffix not in SUPPORTED_IMAGE_FORMATS:
                kind, confidence, fallback = "unsupported_format", 0.40, "asset_review_required"
            else:
                resolved = (base_path / src).resolve() if base_path and not Path(src).is_absolute() else Path(src)
                attributes["resolved_path"] = str(resolved)
                if base_path and not resolved.exists():
                    kind, confidence, fallback = "missing_asset", 0.20, "declare_missing_asset"
                elif suffix in RASTER_IMAGE_FORMATS or not suffix:
                    kind, confidence, fallback = "local_image", 0.90, "use_asset_reference"

        if kind in ("missing_asset", "unsupported_format"):
            diagnostics.append(make_diagnostic(
                "asset_requires_review",
                f"Image asset analysis requires review: {kind}",
                severity="warning",
                category="asset",
                fallback=fallback,
                evidence=[f"asset_index={index}", src],
            ))

        return AnalysisResult(
            kind=kind,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes=attributes,
        )
