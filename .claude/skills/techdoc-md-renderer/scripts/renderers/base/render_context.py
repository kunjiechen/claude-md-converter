"""Renderer adapter input context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.layout import LayoutPlan
from core.model import Document
from core.rules import RenderPolicy


@dataclass
class RenderContext:
    document: Document
    policy: RenderPolicy
    layout_plan: LayoutPlan
    output_path: Optional[Path] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    assets: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
