"""Technical debt dashboard assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .capabilities import renderer_capability_registry
from .legacy_audit import audit_legacy_rules
from .metrics import collect_legacy_retirement_metrics
from .patch_retirement import build_patch_retirement_report


def build_technical_debt_dashboard(repo_root: Path) -> Dict[str, object]:
    audits = audit_legacy_rules(repo_root)
    retirement = build_patch_retirement_report(audits)
    metrics = collect_legacy_retirement_metrics(repo_root, audits)
    return {
        "rule_source_governance": {
            "semantic_source": "SemanticAnalysis",
            "rule_source": "RenderPolicy",
            "layout_source": "LayoutPlan",
            "renderer_boundary": "Adapters execute target mappings only; they must not classify table kind, profile, or overflow strategy.",
        },
        "legacy_rule_audit": [item.to_dict() for item in audits],
        "patch_retirement_report": [item.to_dict() for item in retirement],
        "legacy_retirement_metrics": metrics,
        "renderer_capabilities": renderer_capability_registry(),
        "rollout_expansion_strategy": {
            "per_profile": True,
            "per_renderer": True,
            "canary_rollout": "planned",
            "adapter_default_enable_policy": {
                "lightweight_tech_note": {"html": True, "docx": True, "pdf": False},
                "chip_register_manual": {"html": True, "docx": False, "pdf": False},
                "automotive_formal_spec": {"html": True, "docx": False, "pdf": False},
            },
            "fallback": "legacy renderer remains enabled and every fallback emits diagnostic fallback_to_legacy_renderer",
        },
    }
