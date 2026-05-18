"""Shared diagnostics primitives for migration-safe rendering checks.

Phase 1 deliberately keeps diagnostics lightweight and serializable so existing
dict AST/renderers can carry them without adopting the full V2 DocumentModel.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Diagnostic:
    """A renderer-independent diagnostic attached to source or AST nodes."""

    code: str
    message: str
    severity: str = "warning"
    category: str = "content"
    source_line: Optional[int] = None
    fallback: Optional[str] = None
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_diagnostic(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    category: str = "content",
    source_line: Optional[int] = None,
    fallback: Optional[str] = None,
    evidence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a plain dict diagnostic for use inside the legacy dict AST."""

    return Diagnostic(
        code=code,
        message=message,
        severity=severity,
        category=category,
        source_line=source_line,
        fallback=fallback,
        evidence=evidence or [],
    ).to_dict()


def attach_diagnostic(node: Dict[str, Any], diagnostic: Dict[str, Any]) -> None:
    """Attach a diagnostic to a legacy AST node."""

    attrs = node.setdefault("attributes", {})
    attrs.setdefault("diagnostics", []).append(diagnostic)


def collect_diagnostics(ast: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect diagnostics recursively from a legacy dict AST."""

    found: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any]) -> None:
        attrs = node.get("attributes") or {}
        for diag in attrs.get("diagnostics", []) or []:
            found.append(diag)
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                walk(child)

    for node in ast:
        if isinstance(node, dict):
            walk(node)
    return found
