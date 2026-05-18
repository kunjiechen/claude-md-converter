"""Resolve effective rules from defaults, document profile, and page profile."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


class RuleResolver:
    POLICY_AREAS = [
        "document_policy",
        "typography_policy",
        "table_policy",
        "image_policy",
        "diagram_policy",
        "code_policy",
        "renderer_policy",
        "quality_policy",
    ]

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def resolve(self, document_profile: str, page_profile: str) -> Dict[str, Any]:
        profile = self.config["profiles"][document_profile]
        page = self.config["page_profiles"][page_profile]
        effective: Dict[str, Any] = {
            "document_profile": document_profile,
            "page_profile": page_profile,
            "page_profile_policy": deepcopy(page),
        }
        for area in self.POLICY_AREAS:
            effective[area] = self._deep_merge(
                deepcopy(self.config.get(area) or {}),
                deepcopy(profile.get(area) or {}),
            )
        return effective

    @classmethod
    def _deep_merge(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = cls._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
