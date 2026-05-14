"""Low-confidence suggestion generator for table classifications.

When the deterministic classifier can't confidently determine a table kind
(confidence < 0.80), this module generates advisory suggestions. They are
written into the quality report only — the conversion pipeline is never altered.

Architecture: heuristic scoring first; an AI model can be plugged in later via
the same SuggestionProvider interface without touching the exporter/renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set

from .table_classifier import TableAnalysis, TableClassifier

SUGGESTION_CONFIDENCE_THRESHOLD = 0.80


@dataclass
class Suggestion:
    kind_hint: str
    confidence: float
    reasoning: str
    action: str = ""


@dataclass
class TableSuggestionReport:
    table_index: int
    current_kind: str
    current_confidence: float
    suggestions: List[Suggestion] = field(default_factory=list)

    @property
    def has_suggestions(self) -> bool:
        return len(self.suggestions) > 0


# ----------------------------------------------------------------
# Heuristic re-scoring for low-confidence tables
# ----------------------------------------------------------------

_KIND_PATTERNS: Dict[str, List[str]] = {
    "register": [
        r"\b0x[0-9a-fA-F]{2,}\b",
        r"\b(RO|RW|WO|W1C|RC|R/W)\b",
        r"\[[0-9]+:[0-9]+\]",
        r"\breset\b",
        r"\baddress\b",
        r"\boffset\b",
    ],
    "bitfield": [
        r"\[[0-9]+:[0-9]+\]",
        r"\bbit\s*[0-9]+",
        r"\b(RO|RW|WO|W1C|RC)\b",
        r"\breserved\b",
    ],
    "parameter": [
        r"\b(range|范围|default|默认值|type|类型)\b",
        r"^\s*[\w_]+\s+(int|uint|float|str|bool|enum)\b",
    ],
    "error_code": [
        r"\b(error|错误|code|码)\b",
        r"^\s*0x[0-9a-fA-F]+\s",
        r"\b(retry|重试|ignore|忽略|abort)\b",
    ],
    "glossary": [
        r"^\s*\w[\w\s\-]{1,30}$",
        r"^\s*[\w\-]+(缩写|定义|描述|说明|术语)",
    ],
    "interface": [
        r"\b(field|字段|name|名称|type|类型)\b",
        r"\b(mandatory|required|必填|可选|optional)\b",
        r"\b(example|示例|description|描述)\b",
    ],
    "revision": [
        r"\b(V\d+\.\d+|版本|修订|日期|date|version)\b",
        r"^\s*[A-Za-z]/\d+\s",
    ],
}


def _score_kind(rows: Sequence[Sequence[str]], patterns: List[str]) -> float:
    if not rows or not patterns:
        return 0.0
    sample_texts = [" ".join(r) for r in rows[:12]]
    combined = " ".join(sample_texts)
    import re

    hits = 0
    for pat in patterns:
        if re.search(pat, combined, re.IGNORECASE):
            hits += 1
    return hits / len(patterns) if patterns else 0.0


def _column_count_match(rows: Sequence[Sequence[str]], kind: str) -> float:
    """Check if column count is plausible for the kind."""
    if not rows:
        return 0.0
    col_count = max(len(r) for r in rows)

    expected = {
        "glossary": (2, 2),
        "revision": (5, 6),
        "register": (5, 8),
        "bitfield": (4, 6),
        "parameter": (4, 6),
        "error_code": (3, 5),
        "interface": (3, 4),
        "bnf": (3, 4),
    }
    lo, hi = expected.get(kind, (2, 10))
    if lo <= col_count <= hi:
        return 1.0
    if abs(col_count - (lo + hi) / 2) <= 2:
        return 0.5
    return 0.0


def _row_count_quality(rows: Sequence[Sequence[str]]) -> float:
    """More rows = more signal."""
    if not rows:
        return 0.0
    n = len(rows)
    if n >= 5:
        return 1.0
    if n >= 3:
        return 0.6
    return 0.3


def _first_col_repetition_penalty(rows: Sequence[Sequence[str]]) -> float:
    """If the first column has many duplicate entries, it's weaker signal."""
    if len(rows) < 3:
        return 1.0
    first_vals = [_visible_first(r) for r in rows[1:10] if r]
    if not first_vals:
        return 1.0
    unique_ratio = len(set(first_vals)) / len(first_vals)
    if unique_ratio >= 0.7:
        return 1.0
    if unique_ratio >= 0.4:
        return 0.7
    return 0.4


def _visible_first(row: Sequence[str]) -> str:
    import re
    if not row:
        return ""
    return re.sub(r"\s+", " ", (row[0] or "").strip().lower())


# ----------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------


def suggest_table_kind(
    rows: Sequence[Sequence[str]], current: TableAnalysis
) -> TableSuggestionReport:
    """Generate suggestions when the current classification confidence is low.

    Returns a report even when confidence is high (empty suggestions list),
    so callers don't need to branch on None.
    """
    if not rows:
        return TableSuggestionReport(
            table_index=0,
            current_kind=current.kind,
            current_confidence=current.confidence,
        )

    if current.confidence >= SUGGESTION_CONFIDENCE_THRESHOLD:
        return TableSuggestionReport(
            table_index=0,
            current_kind=current.kind,
            current_confidence=current.confidence,
        )

    suggestions: List[Suggestion] = []
    row_quality = _row_count_quality(rows)
    first_col_penalty = _first_col_repetition_penalty(rows)

    for kind, patterns in _KIND_PATTERNS.items():
        if kind == current.kind:
            continue

        pattern_score = _score_kind(rows, patterns)
        col_score = _column_count_match(rows, kind)

        if pattern_score < 0.35 or col_score < 0.3:
            continue

        combined = (
            pattern_score * 0.50
            + col_score * 0.20
            + row_quality * 0.15
            + first_col_penalty * 0.15
        )

        if combined < 0.40:
            continue

        reasoning = _build_reasoning(kind, pattern_score, col_score)
        action = f"Add <!-- table: {kind} --> before the table to override."
        suggestions.append(
            Suggestion(
                kind_hint=kind,
                confidence=round(combined, 2),
                reasoning=reasoning,
                action=action,
            )
        )

    suggestions.sort(key=lambda s: s.confidence, reverse=True)

    return TableSuggestionReport(
        table_index=0,
        current_kind=current.kind,
        current_confidence=current.confidence,
        suggestions=suggestions[:3],
    )


def _build_reasoning(kind: str, pattern_score: float, col_score: float) -> str:
    kind_labels = {
        "register": "寄存器表",
        "bitfield": "位域表",
        "parameter": "参数表",
        "error_code": "错误码表",
        "glossary": "术语/缩写表",
        "interface": "接口定义表",
        "revision": "修订记录表",
    }
    label = kind_labels.get(kind, kind)

    parts = [f"内容特征与{label}（{kind}）匹配度 {pattern_score:.0%}"]

    if col_score >= 1.0:
        parts.append("列数与典型模式一致")
    elif col_score >= 0.5:
        parts.append("列数接近典型模式")

    return "；".join(parts)


# ----------------------------------------------------------------
# Provider interface (for future AI model drop-in)
# ----------------------------------------------------------------


SuggestionProvider = Callable[
    [Sequence[Sequence[str]], TableAnalysis], TableSuggestionReport
]


def heuristic_provider() -> SuggestionProvider:
    """Return the default heuristic suggestion provider.

    To swap in an AI model later, provide a function with the same signature.
    """
    return suggest_table_kind
