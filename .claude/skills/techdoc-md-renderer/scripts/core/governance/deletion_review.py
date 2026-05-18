"""Legacy deletion candidate review for Phase 11.

This module produces a conservative deletion-readiness report. It never deletes
files; it classifies legacy areas and makes removal preconditions explicit.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


CLASSIFICATIONS = {
    "safe_to_remove",
    "remove_after_rollout",
    "compatibility_required",
    "renderer_specific_required",
    "unknown_risk",
}


@dataclass
class LegacyInventoryItem:
    file: str
    function: str
    rule_type: str
    current_owner: str
    replacement: str
    replacement_exists: bool
    still_used: bool
    rollout_dependency: str
    classification: str
    removal_risk: str
    readiness_score: int
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "file": self.file,
            "function": self.function,
            "rule_type": self.rule_type,
            "current_owner": self.current_owner,
            "replacement": self.replacement,
            "replacement_exists": self.replacement_exists,
            "still_used": self.still_used,
            "rollout_dependency": self.rollout_dependency,
            "classification": self.classification,
            "removal_risk": self.removal_risk,
            "readiness_score": self.readiness_score,
            "evidence": self.evidence,
        }


@dataclass
class PatchAuditItem:
    patch: str
    file: str
    purpose: str
    original_bug: str
    replacement: str
    replacement_status: str
    retirement_condition: str
    test_coverage: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "patch": self.patch,
            "file": self.file,
            "purpose": self.purpose,
            "original_bug": self.original_bug,
            "replacement": self.replacement,
            "replacement_status": self.replacement_status,
            "retirement_condition": self.retirement_condition,
            "test_coverage": self.test_coverage,
        }


@dataclass
class HardcodedRuleItem:
    file: str
    line: int
    rule_type: str
    value: str
    migration_status: str
    recommendation: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "rule_type": self.rule_type,
            "value": self.value,
            "migration_status": self.migration_status,
            "recommendation": self.recommendation,
        }


LEGACY_ROOTS = [
    "scripts/exporters",
    "scripts/html_engine",
    "scripts/polisher.py",
    "scripts/preflight.py",
    "scripts/postflight.py",
]


AREA_RULES = [
    ("legacy_html_renderer", re.compile(r"scripts/html_engine|scripts/exporters/html", re.I), "html_rendering"),
    ("legacy_docx_renderer", re.compile(r"scripts/exporters/word", re.I), "docx_rendering"),
    ("legacy_pdf_renderer", re.compile(r"scripts/exporters/pdf", re.I), "pdf_rendering"),
    ("post_polish", re.compile(r"scripts/polisher.py", re.I), "post_polish"),
    ("preflight", re.compile(r"scripts/preflight.py", re.I), "preflight_validation"),
    ("postflight", re.compile(r"scripts/postflight.py", re.I), "postflight_validation"),
]


REPLACEMENTS = {
    "html_rendering": ("HtmlRendererAdapter + RenderPolicy + LayoutPlan", True),
    "docx_rendering": ("DocxRendererAdapter + DOCX governance/readiness", True),
    "pdf_rendering": ("PdfRendererAdapter + backend registry", True),
    "post_polish": ("LayoutPlan/adapter writers for known rules; quality gate for residual risks", False),
    "preflight_validation": ("No full V2 replacement; still useful before source mutation", False),
    "postflight_validation": ("UnifiedRenderReport/quality gate covers diagnostics, but artifact validation remains useful", False),
    "table_layout": ("SemanticAnalysis.table + RenderPolicy.table_policy + LayoutPlan.tables", True),
    "image_handling": ("AssetAnalysis + RenderPolicy.image_policy + LayoutPlan.figures", True),
    "toc_numbering": ("RenderPolicy.document_policy + adapter furniture support", True),
    "renderer_quirk": ("Renderer adapter target mapping; retain if compatibility-critical", False),
}


def build_legacy_deletion_review(repo_root: Path) -> Dict[str, object]:
    inventory = build_legacy_inventory(repo_root)
    patch_audit = build_patch_audit(inventory)
    hardcoded = audit_hardcoded_rules(repo_root)
    rollout = build_rollout_dependency_report()
    retention = compatibility_retention_policy()
    return {
        "legacy_inventory": [item.to_dict() for item in inventory],
        "deletion_candidate_report": build_deletion_candidate_report(inventory),
        "patch_audit": [item.to_dict() for item in patch_audit],
        "hardcoded_rule_audit": [item.to_dict() for item in hardcoded],
        "compatibility_retention_policy": retention,
        "rollout_dependency_report": rollout,
        "deletion_readiness_scores": deletion_readiness_scores(inventory),
        "recommended_removal_order": recommended_removal_order(inventory),
        "high_risk_legacy_areas": high_risk_legacy_areas(inventory),
        "rollback_strategy": [
            "Keep legacy code on branch until adapter coverage and rollout metrics pass removal gates.",
            "Delete only one classified area per release and keep feature flag fallback for one release window.",
            "Restore deleted area from previous tag if quality gate, fidelity, or fallback metrics regress.",
            "Never remove compatibility_required or renderer_specific_required code without replacement adapter tests.",
        ],
    }


def build_legacy_inventory(repo_root: Path) -> List[LegacyInventoryItem]:
    root = Path(repo_root)
    script_root = root / ".claude" / "skills" / "techdoc-md-renderer"
    items: List[LegacyInventoryItem] = []
    for path in _legacy_python_files(script_root):
        rel = path.relative_to(root) if _is_relative_to(path, root) else path
        area, default_rule_type = _area_for_file(str(rel))
        functions = _functions_in_file(path)
        if not functions:
            functions = ["<module>"]
        text = _read_text(path)
        for fn in functions:
            rule_type = _rule_type_for_function(default_rule_type, fn, text)
            replacement, replacement_exists = REPLACEMENTS.get(rule_type, REPLACEMENTS.get(default_rule_type, ("planned", False)))
            still_used = _still_used(area, rule_type)
            classification = _classify(area, rule_type, replacement_exists, still_used, str(rel), fn)
            risk = _risk(classification, rule_type)
            score = _score(classification, replacement_exists, still_used, rule_type)
            items.append(LegacyInventoryItem(
                file=str(rel),
                function=fn,
                rule_type=rule_type,
                current_owner=area,
                replacement=replacement,
                replacement_exists=replacement_exists,
                still_used=still_used,
                rollout_dependency=_rollout_dependency(area, rule_type),
                classification=classification,
                removal_risk=risk,
                readiness_score=score,
                evidence=_evidence_for(text, fn),
            ))
    return items


def build_deletion_candidate_report(inventory: Iterable[LegacyInventoryItem]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {key: [] for key in CLASSIFICATIONS}
    for item in inventory:
        grouped.setdefault(item.classification, []).append(item.to_dict())
    return grouped


def build_patch_audit(inventory: Iterable[LegacyInventoryItem]) -> List[PatchAuditItem]:
    patches = []
    seen = set()
    for item in inventory:
        if item.rule_type not in ("post_polish", "table_layout", "image_handling", "toc_numbering", "renderer_quirk", "postflight_validation"):
            continue
        key = (item.file, item.function, item.rule_type)
        if key in seen:
            continue
        seen.add(key)
        patches.append(PatchAuditItem(
            patch=item.function,
            file=item.file,
            purpose=_patch_purpose(item.rule_type),
            original_bug=_original_bug(item.rule_type),
            replacement=item.replacement,
            replacement_status="exists" if item.replacement_exists else "partial_or_missing",
            retirement_condition=_retirement_condition(item),
            test_coverage=_test_coverage(item.rule_type),
        ))
    return patches


def audit_hardcoded_rules(repo_root: Path) -> List[HardcodedRuleItem]:
    root = Path(repo_root)
    script_root = root / ".claude" / "skills" / "techdoc-md-renderer"
    items: List[HardcodedRuleItem] = []
    patterns = [
        ("layout_magic_number", re.compile(r"\b(9000|9500|914400|6\.5|5\.8|72|600|300|2\.54|3\.18)\b")),
        ("renderer_local_threshold", re.compile(r"(col_count\s*[><=]|len\(.*\)\s*[><=]|confidence|threshold)", re.I)),
        ("implicit_fallback", re.compile(r"(except Exception|return False|fallback|placeholder)", re.I)),
    ]
    for path in _legacy_python_files(script_root):
        rel = path.relative_to(root) if _is_relative_to(path, root) else path
        for line_no, line in enumerate(_read_text(path).splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for rule_type, pattern in patterns:
                if pattern.search(stripped):
                    items.append(HardcodedRuleItem(
                        file=str(rel),
                        line=line_no,
                        rule_type=rule_type,
                        value=stripped[:160],
                        migration_status=_migration_status(str(rel), stripped, rule_type),
                        recommendation=_hardcoded_recommendation(rule_type),
                    ))
                    break
    return items


def compatibility_retention_policy() -> Dict[str, object]:
    return {
        "long_term_retain": [
            "DOCX OOXML helpers for fields, numbering, hyperlinks, section quirks, and repeat headers until adapter parity is proven.",
            "PDF backend fallback wrappers where backend availability depends on deployment environment.",
            "Preflight source checks that prevent irreversible source/document damage.",
            "Postflight artifact validators for independently verifying generated outputs.",
            "LibreOffice/Word compatibility workarounds that are renderer-specific, tested, and diagnosed.",
        ],
        "retention_rules": [
            "Keep compatibility_required code behind legacy or adapter boundary.",
            "Do not migrate target-unit conversion into semantic or layout layers.",
            "Every retained shim must have owner, purpose, tests, and diagnostics for degraded behavior.",
        ],
    }


def build_rollout_dependency_report() -> Dict[str, object]:
    return {
        "profiles_relying_on_legacy": {
            "automotive_formal_spec": ["docx", "pdf", "html review"],
            "chip_register_manual": ["docx review", "pdf"],
            "lightweight_tech_note": ["pdf review/legacy"],
        },
        "renderer_fidelity_gaps": {
            "html": "lowest risk; V2 candidate",
            "docx": "profile-gated; formal document structure still review-sensitive",
            "pdf": "backend-dependent; formal PDF remains legacy",
        },
        "degraded_paths": [
            "PDF ReportLab fallback is non_conformant",
            "complex DOCX section landscape remains diagnostic/review",
            "raw HTML in paginated targets is fallback/review",
            "advanced table splitting remains review",
        ],
        "fallback_frequency_policy": "Do not delete legacy path if fallback rate exceeds 1% for a profile/format over release window.",
    }


def deletion_readiness_scores(inventory: Iterable[LegacyInventoryItem]) -> Dict[str, Dict[str, object]]:
    grouped: Dict[str, List[LegacyInventoryItem]] = {}
    for item in inventory:
        grouped.setdefault(item.current_owner, []).append(item)
    scores = {}
    for area, items in grouped.items():
        avg = int(sum(item.readiness_score for item in items) / max(1, len(items)))
        scores[area] = {
            "readiness_score": avg,
            "rollout_coverage": _area_rollout_coverage(area),
            "fidelity_confidence": _area_fidelity_confidence(area),
            "regression_confidence": _area_regression_confidence(area),
            "removal_risk": "high" if avg < 50 else "medium" if avg < 75 else "low",
        }
    return scores


def recommended_removal_order(inventory: Iterable[LegacyInventoryItem]) -> List[Dict[str, object]]:
    candidates = [item for item in inventory if item.classification in ("safe_to_remove", "remove_after_rollout")]
    candidates.sort(key=lambda item: (-item.readiness_score, item.removal_risk, item.file, item.function))
    return [
        {
            "file": item.file,
            "function": item.function,
            "classification": item.classification,
            "readiness_score": item.readiness_score,
            "removal_gate": _retirement_condition(item),
        }
        for item in candidates[:50]
    ]


def high_risk_legacy_areas(inventory: Iterable[LegacyInventoryItem]) -> List[Dict[str, object]]:
    high = []
    for item in inventory:
        if item.classification in ("compatibility_required", "renderer_specific_required", "unknown_risk") or item.removal_risk == "high":
            high.append({
                "file": item.file,
                "function": item.function,
                "rule_type": item.rule_type,
                "classification": item.classification,
                "risk": item.removal_risk,
                "reason": item.rollout_dependency,
            })
    return high


def _legacy_python_files(script_root: Path):
    for marker in LEGACY_ROOTS:
        path = script_root / marker
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*.py"):
                if "__pycache__" not in child.parts:
                    yield child


def _functions_in_file(path: Path) -> List[str]:
    try:
        tree = ast.parse(_read_text(path))
    except SyntaxError:
        return []
    result = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append(node.name)
    return sorted(set(result))


def _area_for_file(rel: str):
    for area, pattern, rule_type in AREA_RULES:
        if pattern.search(rel):
            return area, rule_type
    return "legacy_misc", "unknown"


def _rule_type_for_function(default_rule_type: str, fn: str, text: str) -> str:
    name = fn.lower()
    if "table" in name or "toc" in name or "revision" in name:
        return "toc_numbering" if "toc" in name or "revision" in name else "table_layout"
    if "image" in name or "picture" in name or "flowchart" in name:
        return "image_handling"
    if "number" in name or "heading" in name:
        return "toc_numbering"
    if "polish" in name or "fix" in name or "patch" in name:
        return "post_polish"
    if "xml" in text.lower() or "qn(" in text or "OxmlElement" in text:
        return "renderer_quirk"
    return default_rule_type


def _still_used(area: str, rule_type: str) -> bool:
    if area in ("preflight", "postflight", "post_polish"):
        return True
    if area in ("legacy_docx_renderer", "legacy_pdf_renderer"):
        return True
    if area == "legacy_html_renderer":
        return True
    return True


def _classify(area: str, rule_type: str, replacement_exists: bool, still_used: bool, rel: str, fn: str) -> str:
    if rule_type in ("preflight_validation", "postflight_validation"):
        return "compatibility_required"
    if rule_type == "renderer_quirk":
        return "renderer_specific_required"
    if rule_type == "post_polish":
        return "unknown_risk"
    if area == "legacy_html_renderer" and replacement_exists:
        return "remove_after_rollout"
    if area == "legacy_docx_renderer" and replacement_exists:
        return "remove_after_rollout"
    if area == "legacy_pdf_renderer" and replacement_exists:
        return "remove_after_rollout"
    if replacement_exists and not still_used:
        return "safe_to_remove"
    if replacement_exists:
        return "remove_after_rollout"
    return "unknown_risk"


def _risk(classification: str, rule_type: str) -> str:
    if classification == "safe_to_remove":
        return "low"
    if classification == "remove_after_rollout":
        return "medium"
    if classification in ("compatibility_required", "renderer_specific_required"):
        return "high_if_removed"
    return "high"


def _score(classification: str, replacement_exists: bool, still_used: bool, rule_type: str) -> int:
    base = {
        "safe_to_remove": 90,
        "remove_after_rollout": 70,
        "compatibility_required": 25,
        "renderer_specific_required": 35,
        "unknown_risk": 20,
    }.get(classification, 20)
    if replacement_exists:
        base += 5
    if still_used:
        base -= 10
    if rule_type in ("post_polish", "renderer_quirk"):
        base -= 10
    return max(0, min(100, base))


def _rollout_dependency(area: str, rule_type: str) -> str:
    if area == "legacy_html_renderer":
        return "Delete only after HTML V2 default rollout has one clean release window."
    if area == "legacy_docx_renderer":
        return "Depends on DOCX adapter readiness for formal and chip profiles."
    if area == "legacy_pdf_renderer":
        return "Depends on PDF backend availability/fidelity metrics; formal PDF remains legacy."
    if rule_type in ("preflight_validation", "postflight_validation"):
        return "Independent safety validation; retain until V2 has equivalent artifact/source checks."
    if rule_type == "post_polish":
        return "Retire one patch at a time after adapter/layout replacement and golden coverage."
    return "Requires fallback rate and regression confidence gates."


def _patch_purpose(rule_type: str) -> str:
    return {
        "post_polish": "Repair rendered output formatting after legacy conversion.",
        "table_layout": "Stabilize table width, borders, wrapping, or section behavior.",
        "image_handling": "Recover image insertion, scaling, or placeholder behavior.",
        "toc_numbering": "Maintain TOC/revision/heading/list behavior in target formats.",
        "renderer_quirk": "Handle target-specific OOXML/CSS/backend compatibility.",
        "postflight_validation": "Detect broken generated artifact behavior.",
    }.get(rule_type, "Legacy compatibility behavior.")


def _original_bug(rule_type: str) -> str:
    return {
        "post_polish": "Generated output could be readable but visually degraded.",
        "table_layout": "Wide/dense technical tables overflowed or lost structure.",
        "image_handling": "Images could be missing, oversized, or silently omitted.",
        "toc_numbering": "Formal document furniture could be absent or stale.",
        "renderer_quirk": "Word/PDF/HTML engines require target-specific low-level handling.",
        "postflight_validation": "Artifact failures were not visible until manual review.",
    }.get(rule_type, "Legacy behavior lacked a renderer-independent rule source.")


def _retirement_condition(item: LegacyInventoryItem) -> str:
    if item.classification == "compatibility_required":
        return "Retain unless V2 adds equivalent independent validation and release evidence."
    if item.classification == "renderer_specific_required":
        return "Move only into adapter boundary; do not delete without target-format parity tests."
    if item.rule_type == "post_polish":
        return "Adapter implements equivalent behavior, diagnostics exist, golden tests pass, and fallback rate is below threshold."
    if item.classification == "remove_after_rollout":
        return "V2 default rollout for profile/format is complete, quality gate pass/review is stable, and rollback path is tested."
    return "Replacement and tests exist with one clean release window."


def _test_coverage(rule_type: str) -> str:
    return {
        "table_layout": "Phase 5/6B/6C/7/8/10 table and rollout tests.",
        "image_handling": "Phase 1/5/6A/6B/6C/7 image tests.",
        "toc_numbering": "Phase 6D document structure tests.",
        "post_polish": "Partial; requires targeted golden diff before deletion.",
        "renderer_quirk": "Partial; retain unless adapter-specific tests cover exact quirk.",
        "postflight_validation": "Legacy pipeline tests; V2 quality gate is not a full replacement.",
    }.get(rule_type, "Coverage unknown; treat as high risk.")


def _hardcoded_recommendation(rule_type: str) -> str:
    if rule_type == "layout_magic_number":
        return "Migrate to RenderPolicy/LayoutPlan unless it is target unit conversion inside adapter boundary."
    if rule_type == "renderer_local_threshold":
        return "Move heuristic threshold to render-rules.yaml or semantic rules config."
    return "Make fallback diagnostic explicit or keep as compatibility shim with owner."


def _migration_status(rel: str, line: str, rule_type: str) -> str:
    if "renderers/" in rel and rule_type == "layout_magic_number":
        return "adapter_boundary_allowed_review"
    if "exporters/" in rel or "html_engine/" in rel:
        return "legacy_not_migrated_or_rollout_dependent"
    if "polisher.py" in rel:
        return "partial_replacement_requires_patch_retirement"
    return "review_required"


def _area_rollout_coverage(area: str) -> str:
    return {
        "legacy_html_renderer": "partial default candidate",
        "legacy_docx_renderer": "profile-gated",
        "legacy_pdf_renderer": "manual opt-in only",
        "post_polish": "patch-by-patch",
        "preflight": "not replaced",
        "postflight": "not fully replaced",
    }.get(area, "unknown")


def _area_fidelity_confidence(area: str) -> str:
    return {
        "legacy_html_renderer": "high for lightweight/chip HTML",
        "legacy_docx_renderer": "medium; formal/chip remain gated",
        "legacy_pdf_renderer": "low-to-medium; backend-dependent",
        "post_polish": "unknown; visual regression sensitive",
        "preflight": "compatibility safety",
        "postflight": "compatibility safety",
    }.get(area, "unknown")


def _area_regression_confidence(area: str) -> str:
    return {
        "legacy_html_renderer": "high",
        "legacy_docx_renderer": "medium",
        "legacy_pdf_renderer": "medium",
        "post_polish": "partial",
        "preflight": "legacy-covered",
        "postflight": "legacy-covered",
    }.get(area, "unknown")


def _evidence_for(text: str, fn: str) -> List[str]:
    lines = text.splitlines()
    evidence = []
    for i, line in enumerate(lines):
        if ("def %s" % fn) in line:
            evidence.append(line.strip())
            evidence.extend(l.strip() for l in lines[i + 1:i + 4] if l.strip())
            break
    return evidence[:4]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
