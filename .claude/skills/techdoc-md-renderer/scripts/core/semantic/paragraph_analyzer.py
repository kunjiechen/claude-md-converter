"""Paragraph semantic analysis for prose policy hints."""

from __future__ import annotations

import re

from diagnostics import make_diagnostic
from core.model import Paragraph
from .results import AnalysisResult, Evidence
from .rules import PARAGRAPH_SHORT_CJK_LIMIT, PARAGRAPH_SHORT_LATIN_LIMIT
from .utils import plain_inline_text


class ParagraphAnalyzer:
    NOTE_PREFIX = re.compile(r"^(注意|注|例如|示例|参考|说明|备注)[：:]")
    WARNING_PREFIX = re.compile(r"^(警告|危险|禁止|小心|Warning|Caution|Danger)[：:]", re.I)
    CAPTION_PREFIX = re.compile(r"^(图|表|Figure|Table)\s*[0-9一二三四五六七八九十.-]+", re.I)
    CJK_RE = re.compile(r"[\u4e00-\u9fff]")

    @classmethod
    def analyze(cls, paragraph: Paragraph, index: int = 0) -> AnalysisResult:
        text = paragraph.text or plain_inline_text(paragraph.children)
        policy = (paragraph.prose_policy or "").strip().lower()
        length = cls._visual_length(text)
        evidence = [
            Evidence("text_length", "visual text length", length),
            Evidence("explicit_prose_policy", "source prose policy marker", policy),
        ]
        diagnostics = list(paragraph.diagnostics)
        fallback = "normal_spacing"
        kind = "normal"
        confidence = 0.72
        reason = "body_text"

        if policy == "preserve":
            kind, confidence, fallback, reason = "preserve", 1.0, "preserve_source_paragraph_spacing", "explicit_prose_preserve"
        elif policy == "compact":
            kind, confidence, fallback, reason = "compact", 1.0, "compact_prose_candidate", "explicit_prose_compact"
        elif cls.WARNING_PREFIX.match(text.strip()):
            kind, confidence, fallback, reason = "warning", 0.92, "warning_block_candidate", "warning_prefix"
        elif cls.NOTE_PREFIX.match(text.strip()):
            kind, confidence, fallback, reason = "note", 0.88, "note_block_candidate", "note_prefix"
        elif cls.CAPTION_PREFIX.match(text.strip()):
            kind, confidence, fallback, reason = "caption_candidate", 0.78, "caption_review", "caption_prefix"
        elif cls._is_short(text):
            kind, confidence, fallback, reason = "compact", 0.68, "compact_review", "short_paragraph"

        evidence.append(Evidence("reason_code", "paragraph classification reason", reason))
        # Only emit diagnostic for genuinely ambiguous classifications.
        # compact/short is a deliberate heuristic, not a problem.
        if confidence < 0.70 and reason not in ("short_paragraph",):
            diagnostics.append(make_diagnostic(
                "low_confidence_paragraph_analysis",
                "Paragraph semantic classification requires review.",
                severity="warning",
                category="semantic",
                fallback=fallback,
                evidence=[f"paragraph_index={index}", reason, text[:80]],
            ))

        return AnalysisResult(
            kind=kind,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes={"paragraph_index": index, "reason_code": reason},
        )

    @classmethod
    def _is_short(cls, text: str) -> bool:
        length = cls._visual_length(text)
        if cls.CJK_RE.search(text):
            return length <= PARAGRAPH_SHORT_CJK_LIMIT
        return length <= PARAGRAPH_SHORT_LATIN_LIMIT

    @staticmethod
    def _visual_length(text: str) -> int:
        return len(re.sub(r"\s+", "", text or ""))
