"""Table header reliability analysis."""

from __future__ import annotations

from diagnostics import make_diagnostic
from core.model import Table
from .results import AnalysisResult, Evidence
from .rules import HEADER_RELIABLE
from .utils import table_rows_text


class HeaderAnalyzer:
    """Assess parser-supplied table header information without rewriting rows."""

    @classmethod
    def analyze(cls, table: Table, index: int = 0) -> AnalysisResult:
        rows = table_rows_text(table)
        parser_header = bool(table.rows and table.rows[0].header)
        first_row = rows[0] if rows else []
        non_empty = sum(1 for cell in first_row if str(cell).strip())
        confidence = 0.0
        kind = "missing"
        evidence = [
            Evidence("parser_header", "header flag preserved from parser", parser_header),
            Evidence("first_row_non_empty_cells", "non-empty cells in first row", non_empty),
            Evidence("first_row", "first row text", first_row),
        ]
        diagnostics = []

        if parser_header and non_empty >= 2:
            confidence = HEADER_RELIABLE
            kind = "reliable"
            fallback = "use_parser_header"
        elif parser_header and non_empty == 1:
            confidence = 0.55
            kind = "review"
            fallback = "use_parser_header_with_review"
        else:
            confidence = 0.45
            kind = "missing"
            fallback = "no_header_assumed"

        if confidence < HEADER_RELIABLE:
            diagnostics.append(make_diagnostic(
                "table_header_requires_review",
                "Table header confidence is low; semantic analysis did not reinterpret the first row.",
                severity="warning",
                category="semantic",
                fallback=fallback,
                evidence=[f"table_index={index}", f"parser_header={parser_header}", f"non_empty={non_empty}"],
            ))

        return AnalysisResult(
            kind=kind,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes={"table_index": index, "parser_header": parser_header},
        )
