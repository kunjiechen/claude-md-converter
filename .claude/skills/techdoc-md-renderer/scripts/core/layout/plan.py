"""Renderer-independent LayoutPlan structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class PageLayout:
    page_profile: str
    content_box: Dict[str, Any] = field(default_factory=dict)
    margin_profile: str = ""
    orientation_policy: str = "portrait"
    landscape_allowed: bool = False
    section_break_intent: str = "preserve_flow"


@dataclass
class SectionLayout:
    section_index: int
    block_start: int
    block_end: int
    section_break_intent: str = "preserve_flow"
    orientation_intent: str = "portrait"


@dataclass
class ColumnLayout:
    index: int
    role: str = "content"
    width_ratio: float = 0.0
    min_width_policy: str = "content_intrinsic"
    wrap_policy: str = "wrap"


@dataclass
class TableLayout:
    block_index: int
    table_index: int
    kind: str
    header_confidence: float
    columns: List[ColumnLayout] = field(default_factory=list)
    wrap_policy: str = "wrap_cells"
    overflow_risk: str = "low"
    landscape_recommendation: str = "not_required"
    split_recommendation: str = "avoid_split_if_possible"
    fallback_strategy: str = "generic_table_review"
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FigureLayout:
    block_index: int
    asset_index: int
    asset_status: str
    max_width_policy: str
    image_handling_intent: str
    missing_image_placeholder_intent: str = "none"
    svg_conversion_required: bool = False
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CodeBlockLayout:
    block_index: int
    language: str
    preserve_identity: bool
    wrap_policy: str = "wrap_long_lines"
    max_width_behavior: str = "fit_content_box"
    style_intent: str = "code"
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DiagramLayout:
    block_index: int
    diagram_index: int
    diagram_kind: str
    prerender_required_targets: List[str] = field(default_factory=list)
    fallback_fidelity_risk: str = "review"
    placeholder_intent: str = "source_placeholder_until_rendered"
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LayoutPlan:
    page: PageLayout
    sections: List[SectionLayout] = field(default_factory=list)
    tables: List[TableLayout] = field(default_factory=list)
    figures: List[FigureLayout] = field(default_factory=list)
    code_blocks: List[CodeBlockLayout] = field(default_factory=list)
    diagrams: List[DiagramLayout] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
