"""Build RenderPolicy from DocumentModel metadata and render-rules.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.model import Document
from .loader import RuleLoader
from .policy import RenderPolicy
from .profile_resolver import ProfileResolver
from .resolver import RuleResolver


class PolicyBuilder:
    def __init__(self, loader: Optional[RuleLoader] = None):
        self.loader = loader or RuleLoader()

    def build(
        self,
        document: Document,
        *,
        document_profile: Optional[str] = None,
        page_profile: Optional[str] = None,
    ) -> RenderPolicy:
        config = self.loader.load()
        semantic = document.metadata.get("semantic_analysis") or {}
        resolved_document, resolved_page, source = ProfileResolver(config).resolve(
            semantic,
            document_profile=document_profile,
            page_profile=page_profile,
        )
        rules = RuleResolver(config).resolve(resolved_document, resolved_page)
        source.update({
            "config_path": str(Path(self.loader.config_path)),
            "semantic_profile": (semantic.get("document_profile") or {}).get("kind"),
            "semantic_profile_confidence": (semantic.get("document_profile") or {}).get("confidence"),
        })
        return RenderPolicy(
            document_profile=resolved_document,
            page_profile=resolved_page,
            page_policy=rules["page_profile_policy"],
            document_policy=rules["document_policy"],
            typography_policy=rules["typography_policy"],
            table_policy=rules["table_policy"],
            image_policy=rules["image_policy"],
            diagram_policy=rules["diagram_policy"],
            code_policy=rules["code_policy"],
            renderer_policy=rules["renderer_policy"],
            quality_policy=rules["quality_policy"],
            source=source,
        )
