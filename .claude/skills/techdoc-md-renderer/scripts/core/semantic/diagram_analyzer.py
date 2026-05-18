"""Diagram semantic analysis."""

from __future__ import annotations

from typing import List

from diagnostics import make_diagnostic
from core.model import Diagram, Document
from .results import AnalysisResult, Evidence
from .utils import walk_blocks


class DiagramAnalyzer:
    @classmethod
    def analyze(cls, document: Document) -> List[AnalysisResult]:
        results: List[AnalysisResult] = []
        for index, block in enumerate(b for b in walk_blocks(document) if isinstance(b, Diagram)):
            results.append(cls._analyze_diagram(block, index))
        return results

    @staticmethod
    def _analyze_diagram(diagram: Diagram, index: int) -> AnalysisResult:
        diagram_type = (diagram.diagram_type or diagram.language or "unknown").lower()
        evidence = [
            Evidence("diagram_type", "diagram type from parser/model", diagram_type),
            Evidence("language", "source fence language", diagram.language),
            Evidence("subtype", "diagram subtype", diagram.subtype),
        ]
        diagnostics = list(diagram.diagnostics)
        fallback = "source_preserved"
        confidence = 0.60
        kind = "unknown_diagram"
        fidelity_risk = "review"
        requires_static_asset_for_paginated_outputs = True

        if diagram_type == "mermaid":
            kind, confidence, fallback, fidelity_risk = "mermaid", 0.90, "preserve_source_until_prerender", "source_only_if_not_prerendered"
        elif diagram_type == "plantuml":
            kind, confidence, fallback, fidelity_risk = "plantuml", 0.88, "preserve_source_until_prerender", "source_only_if_not_prerendered"
        else:
            diagnostics.append(make_diagnostic(
                "unknown_diagram_type",
                "Diagram type is unknown; source-only fallback may reduce fidelity.",
                severity="warning",
                category="semantic",
                fallback="source_only_review",
                evidence=[f"diagram_index={index}", diagram_type],
            ))

        if requires_static_asset_for_paginated_outputs:
            diagnostics.append(make_diagnostic(
                "diagram_static_asset_required",
                "Diagram source should be pre-rendered for paginated outputs to avoid source-only fallback.",
                severity="warning",
                category="diagram",
                fallback=fallback,
                evidence=[f"diagram_index={index}", kind],
            ))

        return AnalysisResult(
            kind=kind,
            confidence=confidence,
            evidence=evidence,
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes={
                "diagram_index": index,
                "fidelity_risk": fidelity_risk,
                "requires_static_asset_for_paginated_outputs": requires_static_asset_for_paginated_outputs,
            },
        )
