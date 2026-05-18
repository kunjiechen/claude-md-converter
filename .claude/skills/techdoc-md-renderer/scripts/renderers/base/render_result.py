"""Renderer adapter output result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RenderResult:
    success: bool
    output_path: str = ""
    content: str = ""
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    fidelity_level: str = "review"
    degradation_reason: str = ""
    fallback_used: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
