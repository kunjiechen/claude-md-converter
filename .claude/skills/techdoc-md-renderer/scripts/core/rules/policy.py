"""Renderer-independent RenderPolicy structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class RenderPolicy:
    document_profile: str
    page_profile: str
    page_policy: Dict[str, Any] = field(default_factory=dict)
    document_policy: Dict[str, Any] = field(default_factory=dict)
    typography_policy: Dict[str, Any] = field(default_factory=dict)
    table_policy: Dict[str, Any] = field(default_factory=dict)
    image_policy: Dict[str, Any] = field(default_factory=dict)
    diagram_policy: Dict[str, Any] = field(default_factory=dict)
    code_policy: Dict[str, Any] = field(default_factory=dict)
    renderer_policy: Dict[str, Any] = field(default_factory=dict)
    quality_policy: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
