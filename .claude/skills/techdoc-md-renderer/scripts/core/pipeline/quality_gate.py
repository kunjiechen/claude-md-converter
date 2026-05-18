"""Unified V2 quality gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class UnifiedQualityGateResult:
    status: str
    score: int
    deliverable: bool
    reasons: List[str] = field(default_factory=list)
    diagnostics_summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "deliverable": self.deliverable,
            "reasons": self.reasons,
            "diagnostics_summary": self.diagnostics_summary,
        }


def evaluate_unified_quality(
    *,
    diagnostics: List[Dict[str, Any]],
    fidelity_level: str,
    fallback_used: bool,
    layout_plan: Dict[str, Any],
    renderer_metadata: Dict[str, Any] = None,
) -> UnifiedQualityGateResult:
    renderer_metadata = renderer_metadata or {}
    summary = _diagnostics_summary(diagnostics)
    reasons: List[str] = []
    score = 100

    errors = summary.get("error", 0)
    warnings = summary.get("warning", 0)
    score -= errors * 15
    score -= warnings * 2

    fidelity_penalties = {
        "conformant": 0,
        "review": 15,
        "degraded": 35,
        "non_conformant": 70,
    }
    score -= fidelity_penalties.get(fidelity_level, 45)
    if fidelity_level != "conformant":
        reasons.append("fidelity_level=%s" % fidelity_level)

    if fallback_used:
        score -= 10
        reasons.append("fallback_used")
    if renderer_metadata.get("backend_used") in ("wkhtmltopdf", "reportlab"):
        score -= 10
        reasons.append("review_or_non_conformant_backend=%s" % renderer_metadata.get("backend_used"))

    layout_risks = _layout_risks(layout_plan)
    if layout_risks:
        score -= min(20, len(layout_risks) * 5)
        reasons.extend(layout_risks)

    blocking_codes = {
        "silent_content_loss",
        "missing_required_asset",
        "unified_pipeline_failed",
        "unified_pipeline_adapter_failed",
    }
    present_codes = {diag.get("code") for diag in diagnostics}
    if blocking_codes & present_codes:
        reasons.append("blocking_diagnostic_present")
        status = "fail"
    elif fidelity_level == "non_conformant":
        status = "fail"
    elif score < 70:
        status = "review"
    elif reasons or score < 90:
        status = "review"
    else:
        status = "pass"

    score = max(0, min(100, score))
    return UnifiedQualityGateResult(
        status=status,
        score=score,
        deliverable=status == "pass",
        reasons=_dedupe(reasons),
        diagnostics_summary=summary,
    )


def _diagnostics_summary(diagnostics: List[Dict[str, Any]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for diag in diagnostics or []:
        severity = diag.get("severity") or "unknown"
        category = "category:%s" % (diag.get("category") or "unknown")
        summary[severity] = summary.get(severity, 0) + 1
        summary[category] = summary.get(category, 0) + 1
    return summary


def _layout_risks(layout_plan: Dict[str, Any]) -> List[str]:
    reasons = []
    for table in layout_plan.get("tables") or []:
        if table.get("overflow_risk") in ("medium", "high"):
            reasons.append("table_overflow_risk:%s" % table.get("overflow_risk"))
        if table.get("landscape_recommendation") == "recommended":
            reasons.append("landscape_recommended")
    for figure in layout_plan.get("figures") or []:
        if figure.get("asset_status") == "missing_asset":
            reasons.append("missing_asset_placeholder")
    for diagram in layout_plan.get("diagrams") or []:
        if diagram.get("fallback_fidelity_risk") in ("review", "degraded", "non_conformant"):
            reasons.append("diagram_fidelity_risk")
    return _dedupe(reasons)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
