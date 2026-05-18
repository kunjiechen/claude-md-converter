"""Renderer capability governance."""

from __future__ import annotations

from typing import Dict


def renderer_capability_registry() -> Dict[str, Dict[str, object]]:
    """Return explicit renderer capabilities and fallback governance."""

    return {
        "html": {
            "semantic_source": "Document.metadata.semantic_analysis",
            "rule_source": "RenderPolicy",
            "layout_source": "LayoutPlan",
            "capabilities": ["raw_html_preserve", "responsive_tables", "mermaid_browser_render"],
            "fallback_policy": "legacy_html_renderer_when_adapter_fails",
            "default_fidelity": "conformant",
        },
        "docx": {
            "semantic_source": "Document.metadata.semantic_analysis",
            "rule_source": "RenderPolicy",
            "layout_source": "LayoutPlan",
            "capabilities": ["basic_tables", "local_images", "heading_numbering", "toc_field_placeholder"],
            "fallback_policy": "legacy_docx_renderer_when_profile_rollout_blocks_or_adapter_fails",
            "default_fidelity": "review",
        },
        "pdf": {
            "semantic_source": "Document.metadata.semantic_analysis",
            "rule_source": "RenderPolicy",
            "layout_source": "LayoutPlan",
            "capabilities": ["html_to_pdf_backend", "paged_media_when_backend_supports"],
            "fallback_policy": "legacy_pdf_renderer_when_adapter_fails_or_backend_unavailable",
            "default_fidelity": "review",
        },
    }
