"""DOCX adapter readiness evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from core.model import (
    BlockQuote,
    CodeBlock,
    Diagram,
    Figure,
    Heading,
    HorizontalRule,
    ListBlock,
    PageBreak,
    Paragraph,
    RawHtmlBlock,
    Table,
    UnsupportedBlock,
)


SUPPORTED_BLOCKS = {
    Heading,
    Paragraph,
    CodeBlock,
    Table,
    Figure,
    ListBlock,
    BlockQuote,
    PageBreak,
    HorizontalRule,
    RawHtmlBlock,
}


@dataclass
class DocxReadinessReport:
    supported_nodes: List[str] = field(default_factory=list)
    unsupported_nodes: List[str] = field(default_factory=list)
    degraded_features: List[str] = field(default_factory=list)
    fidelity_score: int = 100
    regression_status: str = "not_run"
    fidelity_level: str = "conformant"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_docx_adapter_readiness(document, render_result=None, comparison_report: Optional[Any] = None) -> DocxReadinessReport:
    supported = []
    unsupported = []
    for block in document.blocks:
        name = block.__class__.__name__
        if isinstance(block, UnsupportedBlock) or block.__class__ not in SUPPORTED_BLOCKS:
            unsupported.append(name)
        else:
            supported.append(name)

    degraded = []
    diagnostics = list(getattr(render_result, "diagnostics", []) or [])
    for diag in diagnostics:
        code = diag.get("code", "")
        if code and diag.get("severity") in ("warning", "error"):
            degraded.append(code)
    if any(isinstance(block, Diagram) for block in document.blocks):
        degraded.append("unsupported_docx_feature:diagram_prerender")

    score = 100
    score -= len(set(unsupported)) * 15
    score -= len(set(degraded)) * 5
    if any(diag.get("severity") == "error" for diag in diagnostics):
        score -= 30
    score = max(0, min(100, score))

    regression = "not_run"
    if comparison_report is not None:
        regression = comparison_report.fidelity_classification
        if comparison_report.fidelity_classification != "conformant":
            score = min(score, 80)

    if score >= 90:
        fidelity = "conformant"
    elif score >= 70:
        fidelity = "review"
    elif score >= 40:
        fidelity = "degraded"
    else:
        fidelity = "non_conformant"

    return DocxReadinessReport(
        supported_nodes=sorted(set(supported)),
        unsupported_nodes=sorted(set(unsupported)),
        degraded_features=sorted(set(degraded)),
        fidelity_score=score,
        regression_status=regression,
        fidelity_level=fidelity,
    )
