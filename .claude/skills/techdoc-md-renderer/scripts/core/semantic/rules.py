"""Centralized semantic analysis rule thresholds.

These values intentionally live outside analyzers so heuristics stay visible
and can later move to render-rules.yaml without hunting through code.
"""

CONFIDENCE_STRONG = 0.85
CONFIDENCE_REVIEW = 0.70
TABLE_LOW_CONFIDENCE = 0.70
HEADER_RELIABLE = 0.75
PROFILE_MIN_CONFIDENCE = 0.60

PARAGRAPH_SHORT_CJK_LIMIT = 42
PARAGRAPH_SHORT_LATIN_LIMIT = 90

SUPPORTED_IMAGE_FORMATS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
}

RASTER_IMAGE_FORMATS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
}
