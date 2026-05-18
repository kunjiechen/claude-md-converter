"""Static legacy rule audit.

The audit is intentionally conservative: it flags remaining rule-like code so
cutover decisions can be governed, not silently removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Iterable, List


@dataclass
class LegacyRuleAudit:
    category: str
    classification: str
    file: str
    line: int
    evidence: str
    replacement: str
    owner: str = "phase8_cutover"

    def to_dict(self) -> Dict[str, object]:
        return {
            "category": self.category,
            "classification": self.classification,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
            "replacement": self.replacement,
            "owner": self.owner,
        }


AUDIT_PATTERNS = [
    (
        "hardcoded_table_width",
        "mapped_to_policy",
        re.compile(r"(width|col_width|content_width|column).*?(Cm\(|Inches\(|Pt\(|\d+(\.\d+)?)", re.I),
        "LayoutPlan.table.columns + renderer adapter unit conversion",
    ),
    (
        "post_polish_logic",
        "requires_migration",
        re.compile(r"(polish|postflight|fix_|patch_|normalize_spacing|adjust_)", re.I),
        "RenderPolicy/LayoutPlan decision plus renderer capability diagnostics",
    ),
    (
        "duplicated_image_scaling",
        "mapped_to_policy",
        re.compile(r"(max_image|image_width|scale|aspect|inline_image)", re.I),
        "RenderPolicy.image_policy + LayoutPlan.figure layout intent",
    ),
    (
        "duplicated_overflow_handling",
        "mapped_to_policy",
        re.compile(r"(overflow|landscape|wide_table|wrap_cells|repeat_header)", re.I),
        "Semantic table kind + RenderPolicy.table_policy + LayoutPlan overflow intent",
    ),
    (
        "duplicated_toc_logic",
        "requires_migration",
        re.compile(r"(TOC|toc|revision_history|heading_number|source_number)", re.I),
        "RenderPolicy.document_policy + LayoutPlan section intent",
    ),
    (
        "renderer_specific_patch",
        "renderer_specific_necessary",
        re.compile(r"(OxmlElement|qn\(|EMU|DXA|weasy|chromium|wkhtml|reportlab|CSS|style_mapping)", re.I),
        "Adapter-only target mapping with diagnostics",
    ),
]


SKIP_DIRS = {"tests", "__pycache__"}


def audit_legacy_rules(repo_root: Path) -> List[LegacyRuleAudit]:
    """Scan legacy and adapter files for rule-like code that needs governance."""

    root = Path(repo_root)
    scripts_root = root / ".claude" / "skills" / "techdoc-md-renderer" / "scripts"
    if not scripts_root.exists():
        scripts_root = root
    audits: List[LegacyRuleAudit] = []
    for path in _iter_python_files(scripts_root):
        if "/core/governance/" in path.as_posix():
            continue
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for category, classification, pattern, replacement in AUDIT_PATTERNS:
                if pattern.search(stripped):
                    audits.append(LegacyRuleAudit(
                        category=category,
                        classification=classification,
                        file=str(rel),
                        line=line_no,
                        evidence=stripped[:180],
                        replacement=replacement,
                    ))
                    break
    return audits


def summarize_audit(audits: Iterable[LegacyRuleAudit]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for item in audits:
        summary[item.classification] = summary.get(item.classification, 0) + 1
    return summary


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path
