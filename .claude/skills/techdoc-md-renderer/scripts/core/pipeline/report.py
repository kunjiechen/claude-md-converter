"""Unified rendering report for Phase 8 cutover governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UnifiedRenderReport:
    """Single report carrying semantic, policy, layout, renderer, and fidelity state."""

    success: bool
    format: str
    output_path: str = ""
    renderer_used: str = ""
    fallback_used: bool = False
    legacy_used: bool = False
    fidelity_level: str = "review"
    degradation_reason: str = ""
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics_summary: Dict[str, int] = field(default_factory=dict)
    quality_gate: Dict[str, Any] = field(default_factory=dict)
    render_trace: Dict[str, Any] = field(default_factory=dict)
    performance_report: Dict[str, Any] = field(default_factory=dict)
    semantic_analysis: Dict[str, Any] = field(default_factory=dict)
    render_policy: Dict[str, Any] = field(default_factory=dict)
    layout_plan: Dict[str, Any] = field(default_factory=dict)
    renderer_metadata: Dict[str, Any] = field(default_factory=dict)
    legacy_metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "format": self.format,
            "output_path": self.output_path,
            "renderer_used": self.renderer_used,
            "fallback_used": self.fallback_used,
            "legacy_used": self.legacy_used,
            "fidelity_level": self.fidelity_level,
            "degradation_reason": self.degradation_reason,
            "diagnostics": self.diagnostics,
            "diagnostics_summary": self.diagnostics_summary,
            "quality_gate": self.quality_gate,
            "render_trace": self.render_trace,
            "performance_report": self.performance_report,
            "semantic_analysis": self.semantic_analysis,
            "render_policy": self.render_policy,
            "layout_plan": self.layout_plan,
            "renderer_metadata": self.renderer_metadata,
            "legacy_metrics": self.legacy_metrics,
            "error": self.error,
        }
