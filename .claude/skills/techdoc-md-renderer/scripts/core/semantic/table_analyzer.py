"""Renderer-independent table semantic analysis."""

from __future__ import annotations

from typing import List

from analyzers.table_classifier import TableClassifier
from diagnostics import make_diagnostic
from core.model import Table
from .results import AnalysisResult, Evidence
from .rules import TABLE_LOW_CONFIDENCE
from .utils import table_rows_text


SUPPORTED_TABLE_KINDS = {
    "revision",
    "register",
    "bitfield",
    "bnf",
    "interface",
    "parameter",
    "error_code",
    "glossary",
    "reference",
    "generic",
}


class TableAnalyzer:
    """Classify table semantics without changing table content."""

    @classmethod
    def analyze(cls, table: Table, index: int = 0) -> AnalysisResult:
        rows = table_rows_text(table)
        explicit = (table.explicit_kind or "").strip().lower().replace("-", "_")
        analysis = TableClassifier.classify(rows, explicit_kind=explicit or None)
        kind = analysis.kind if analysis.kind in SUPPORTED_TABLE_KINDS else "generic"
        confidence = analysis.confidence
        evidence: List[Evidence] = [
            Evidence("row_count", "non-empty table row count", len(rows)),
            Evidence("column_count", "maximum table column count", max((len(r) for r in rows), default=0)),
        ]
        if explicit:
            evidence.append(Evidence("explicit_marker", "table kind marker from source", explicit))
        if rows:
            evidence.append(Evidence("header_cells", "first table row text used as header signal", rows[0]))
        if analysis.issues:
            evidence.append(Evidence("legacy_classifier_issues", "existing table classifier issues", analysis.issues))

        diagnostics = list(table.diagnostics)
        fallback = "classified"
        candidate_kind = analysis.kind
        if confidence < TABLE_LOW_CONFIDENCE:
            diagnostics.append(make_diagnostic(
                "low_confidence_table_classification",
                "Table semantic classification is low-confidence and requires generic table review.",
                severity="warning",
                category="semantic",
                fallback="generic_table_review",
                evidence=[f"table_index={index}", f"confidence={analysis.confidence}", f"candidate={candidate_kind}"],
            ))
            kind = "generic"
            confidence = min(confidence, TABLE_LOW_CONFIDENCE)
            fallback = "generic_table_review"
        elif explicit and explicit not in SUPPORTED_TABLE_KINDS:
            kind = "generic"
            confidence = min(confidence, TABLE_LOW_CONFIDENCE)
            fallback = "generic_table_review"
        if explicit and explicit not in SUPPORTED_TABLE_KINDS:
            diagnostics.append(make_diagnostic(
                "unsupported_explicit_table_kind",
                f"Explicit table kind is not supported: {explicit}",
                severity="warning",
                category="semantic",
                fallback="generic_table_review",
                evidence=[explicit],
            ))

        return AnalysisResult(
            kind=kind,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes={
                "table_index": index,
                "explicit_kind": explicit,
                "legacy_candidate": analysis.kind,
                "layout_hint_present": True,
            },
        )
