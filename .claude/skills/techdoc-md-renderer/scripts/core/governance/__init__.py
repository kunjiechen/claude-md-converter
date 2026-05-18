"""Governance helpers for Phase 8 legacy retirement."""

from .capabilities import renderer_capability_registry
from .dashboard import build_technical_debt_dashboard
from .deletion_review import build_legacy_deletion_review, build_legacy_inventory
from .legacy_audit import LegacyRuleAudit, audit_legacy_rules
from .metrics import collect_legacy_retirement_metrics
from .patch_retirement import build_patch_retirement_report

__all__ = [
    "LegacyRuleAudit",
    "audit_legacy_rules",
    "build_patch_retirement_report",
    "collect_legacy_retirement_metrics",
    "build_technical_debt_dashboard",
    "build_legacy_deletion_review",
    "build_legacy_inventory",
    "renderer_capability_registry",
]
