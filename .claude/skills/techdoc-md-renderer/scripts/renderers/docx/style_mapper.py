"""DOCX adapter style mapping from RenderPolicy."""

from __future__ import annotations

from typing import Any, Dict, List

from diagnostics import make_diagnostic


class DocxStyleMapper:
    def __init__(self, document, policy, diagnostics):
        self.document = document
        self.policy = policy
        self.diagnostics = diagnostics

    def heading_style(self, level: int) -> str:
        return self._existing_or_fallback(f"Heading {max(1, min(level, 6))}", "Normal", "heading")

    def paragraph_style(self) -> str:
        return self._existing_or_fallback("Normal", "Normal", "paragraph")

    def code_style(self) -> str:
        return self._existing_or_fallback("规范", "No Spacing", "code")

    def blockquote_style(self) -> str:
        return self._existing_or_fallback("Quote", "Normal", "blockquote")

    def table_style(self) -> str:
        mapping = (((self.policy.renderer_policy.get("docx") or {}).get("adapter_policy") or {}).get("word_style_mapping") or {})
        requested = mapping.get("table") or "Table Grid"
        return self._existing_or_fallback(requested, "Table Grid", "table")

    def table_kind_style_tokens(self, kind: str) -> Dict[str, str]:
        tokens = {
            "register": {"header_fill": "D9EAF7", "code_fill": "F4F8FB"},
            "bitfield": {"header_fill": "E2F0D9", "code_fill": "F6FBF3"},
            "interface": {"header_fill": "EDE7F6", "code_fill": "FAF8FD"},
            "parameter": {"header_fill": "FFF2CC", "code_fill": "FFF9E6"},
            "generic": {"header_fill": "D9D9D9", "code_fill": ""},
            "glossary": {"header_fill": "D9D9D9", "code_fill": ""},
        }
        return tokens.get(kind, tokens["generic"])

    def adapter_policy(self) -> Dict[str, Any]:
        return ((self.policy.renderer_policy.get("docx") or {}).get("adapter_policy") or {})

    def content_width_inches(self) -> float:
        return float(self.adapter_policy().get("content_width_inches", 6.5))

    def max_image_width_inches(self) -> float:
        return float(self.adapter_policy().get("max_image_width_inches", 5.8))

    def cell_content_style(self) -> str:
        return self._existing_or_fallback("图表正文", "Normal", "cell_content")

    def repeat_table_header_enabled(self) -> bool:
        return bool(self.adapter_policy().get("repeat_table_header", True))

    def _existing_or_fallback(self, requested: str, fallback: str, role: str) -> str:
        if self._has_style(requested):
            return requested
        self.diagnostics.append(make_diagnostic(
            "docx_style_fallback",
            f"DOCX style is missing; fallback style will be used for {role}.",
            severity="warning",
            category="renderer",
            fallback=fallback,
            evidence=[requested, role],
        ))
        return fallback if self._has_style(fallback) else "Normal"

    def _has_style(self, name: str) -> bool:
        try:
            self.document.styles[name]
            return True
        except Exception:
            return False
