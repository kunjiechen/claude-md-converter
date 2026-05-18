"""Legacy retirement metrics for Phase 8."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from .legacy_audit import LegacyRuleAudit, summarize_audit


def collect_legacy_retirement_metrics(repo_root: Path, audits: Iterable[LegacyRuleAudit] = None) -> Dict[str, object]:
    root = Path(repo_root)
    audit_items = list(audits or [])
    scripts_root = root / ".claude" / "skills" / "techdoc-md-renderer" / "scripts"
    remaining_legacy_paths = _count_paths(scripts_root, ["exporters", "polisher.py", "preflight.py", "postflight.py"])
    patch_functions = _count_text_matches(scripts_root, ["patch", "polish", "fix_", "postflight"])
    return {
        "remaining_legacy_paths": remaining_legacy_paths,
        "remaining_hardcoded_rules": sum(1 for item in audit_items if item.category.startswith("hardcoded")),
        "remaining_patch_functions": patch_functions,
        "duplicated_logic_count": sum(1 for item in audit_items if item.category.startswith("duplicated")),
        "audit_summary": summarize_audit(audit_items),
        "adapter_coverage": {
            "html": "stable",
            "docx": "governed",
            "pdf": "minimal",
        },
        "fidelity_pass_rate": "planned_metric_from_regression_suite",
    }


def _count_paths(root: Path, markers) -> int:
    if not root.exists():
        return 0
    count = 0
    for path in root.rglob("*.py"):
        posix = path.as_posix()
        if any(marker in posix for marker in markers):
            count += 1
    return count


def _count_text_matches(root: Path, needles) -> int:
    if not root.exists():
        return 0
    count = 0
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        count += sum(text.count(needle.lower()) for needle in needles)
    return count
