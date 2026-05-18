"""Production readiness report for the V2 pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from core.governance import build_technical_debt_dashboard


def build_production_readiness_report(repo_root: Path) -> Dict[str, object]:
    dashboard = build_technical_debt_dashboard(repo_root)
    metrics = dashboard["legacy_retirement_metrics"]
    return {
        "status": "review",
        "summary": "V2 adapter pipeline is the only conversion path.",
        "default_rollout_policy": {"v2_only": True},
        "adapter_coverage_report": metrics.get("adapter_coverage"),
        "remaining_legacy_dependency_report": {"remaining_legacy_paths": metrics.get("remaining_legacy_paths")},
        "known_risks": [
            "PDF output depends on external backend availability and may fall back to review/non_conformant fidelity.",
            "Golden diff equivalence is structural, not binary-identical.",
        ],
        "dashboard": dashboard,
    }
