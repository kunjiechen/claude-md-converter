"""Patch retirement report for legacy cutover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .legacy_audit import LegacyRuleAudit


@dataclass
class PatchRetirementItem:
    category: str
    retirement_class: str
    owner: str
    replacement: str
    retirement_condition: str
    evidence_count: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "retirement_class": self.retirement_class,
            "owner": self.owner,
            "replacement": self.replacement,
            "retirement_condition": self.retirement_condition,
            "evidence_count": self.evidence_count,
        }


RETIREMENT_CLASSES = {
    "mapped_to_policy": "requires_migration",
    "requires_migration": "requires_migration",
    "renderer_specific_necessary": "renderer_specific_necessary",
    "obsolete": "removable_now",
    "dangerous": "temporary_compatibility_patch",
}


def build_patch_retirement_report(audits: Iterable[LegacyRuleAudit]) -> List[PatchRetirementItem]:
    grouped: Dict[str, List[LegacyRuleAudit]] = {}
    for audit in audits:
        grouped.setdefault(audit.category, []).append(audit)
    report = []
    for category, items in sorted(grouped.items()):
        classification = _dominant_classification(items)
        report.append(PatchRetirementItem(
            category=category,
            retirement_class=RETIREMENT_CLASSES.get(classification, "requires_migration"),
            owner="renderer_adapter_cutover",
            replacement=items[0].replacement,
            retirement_condition=_retirement_condition(category, classification),
            evidence_count=len(items),
        ))
    return report


def _dominant_classification(items: List[LegacyRuleAudit]) -> str:
    priority = ["dangerous", "requires_migration", "mapped_to_policy", "renderer_specific_necessary", "obsolete"]
    classes = {item.classification for item in items}
    for item in priority:
        if item in classes:
            return item
    return "requires_migration"


def _retirement_condition(category: str, classification: str) -> str:
    if classification == "renderer_specific_necessary":
        return "Keep only inside adapter unit/style mapping modules with explicit diagnostics."
    if category in ("duplicated_overflow_handling", "hardcoded_table_width"):
        return "All supported renderers consume LayoutPlan table intent and golden diff has no structural regressions."
    if category == "duplicated_image_scaling":
        return "All supported renderers consume AssetAnalysis/FigureLayout and missing/SVG fallbacks are diagnosed."
    if category == "duplicated_toc_logic":
        return "Document furniture policy is generated once and adapter readiness is review-or-better."
    return "Replacement is covered by regression tests and rollout fallback remains enabled for one release window."
