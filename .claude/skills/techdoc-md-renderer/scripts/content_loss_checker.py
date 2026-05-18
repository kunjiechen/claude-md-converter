"""No-silent-content-loss checks for the legacy dict AST.

This is a Phase 1 migration guard. It does not replace renderers or introduce
the full typed DocumentModel; it verifies that known content-loss hazards are
represented as AST content or explicit diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from diagnostics import collect_diagnostics


@dataclass
class ContentLossReport:
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(d.get("severity") == "critical" for d in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        return bool(self.diagnostics)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_ast(ast: List[Dict[str, Any]]) -> ContentLossReport:
    """Check the AST for Phase 1 no-silent-content-loss diagnostics."""

    diagnostics = collect_diagnostics(ast)

    def walk(node: Dict[str, Any]) -> None:
        node_type = node.get("type")
        if node_type == "paragraph":
            _check_mixed_image_paragraph(node, diagnostics)
        elif node_type == "raw_html":
            # raw_html is allowed only because it is explicit and diagnosed.
            attrs = node.get("attributes") or {}
            if not attrs.get("diagnostics"):
                diagnostics.append({
                    "code": "raw_html_without_diagnostic",
                    "message": "Raw HTML block is present without an explicit diagnostic.",
                    "severity": "warning",
                    "category": "unsupported",
                    "fallback": "preserve_raw_html",
                    "evidence": [node.get("content", "")[:120]],
                    "source_line": None,
                })
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                walk(child)

    for node in ast:
        if isinstance(node, dict):
            walk(node)
    return ContentLossReport(diagnostics=diagnostics)


def _check_mixed_image_paragraph(node: Dict[str, Any], diagnostics: List[Dict[str, Any]]) -> None:
    """Ensure mixed text/image paragraphs remain represented as paragraphs."""

    children = node.get("children") or []
    has_image = any(c.get("type") == "image" for c in children if isinstance(c, dict))
    if not has_image:
        return
    text_parts = [
        c.get("content", "")
        for c in children
        if isinstance(c, dict) and c.get("type") == "text" and c.get("content")
    ]
    if node.get("content") and not text_parts:
        diagnostics.append({
            "code": "mixed_image_paragraph_text_not_segmented",
            "message": "Paragraph contains an image and source text; verify inline text is preserved.",
            "severity": "warning",
            "category": "content",
            "fallback": "preserve_paragraph_children",
            "evidence": [node.get("content", "")[:120]],
            "source_line": None,
        })
