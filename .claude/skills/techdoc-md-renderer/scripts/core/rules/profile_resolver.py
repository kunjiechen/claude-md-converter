"""Resolve document and page profiles from semantic analysis."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


class ProfileResolver:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def resolve(
        self,
        semantic_analysis: Optional[Dict[str, Any]] = None,
        *,
        document_profile: Optional[str] = None,
        page_profile: Optional[str] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        profiles = self.config.get("profiles") or {}
        page_profiles = self.config.get("page_profiles") or {}
        defaults = self.config.get("defaults") or {}
        source = {"document_profile_source": "default", "page_profile_source": "default"}

        resolved_document = document_profile
        if resolved_document:
            source["document_profile_source"] = "override"
        if not resolved_document and semantic_analysis:
            profile = semantic_analysis.get("document_profile") or {}
            candidate = profile.get("kind")
            if candidate in profiles:
                resolved_document = candidate
                source["document_profile_source"] = "semantic_analysis"

        if resolved_document not in profiles:
            resolved_document = defaults.get("document_profile", "lightweight_tech_note")

        profile_cfg = profiles[resolved_document]
        resolved_page = page_profile
        if resolved_page:
            source["page_profile_source"] = "override"
        if not resolved_page:
            resolved_page = profile_cfg.get("page_profile") or defaults.get("page_profile", "a4_cn_formal")

        if resolved_page not in page_profiles:
            resolved_page = defaults.get("page_profile", "a4_cn_formal")

        return resolved_document, resolved_page, source
