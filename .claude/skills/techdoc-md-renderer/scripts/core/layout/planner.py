"""Build a renderer-independent LayoutPlan from model, semantics, and policy."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from diagnostics import make_diagnostic
from core.model import CodeBlock, Diagram, Document, Figure, Table
from core.rules import RenderPolicy
from .plan import (
    CodeBlockLayout,
    ColumnLayout,
    DiagramLayout,
    FigureLayout,
    LayoutPlan,
    PageLayout,
    SectionLayout,
    TableLayout,
)


class LayoutPlanner:
    """Create layout intent only; renderer adapters perform unit conversion."""

    def plan(self, document: Document, policy: RenderPolicy, *, attach: bool = True) -> LayoutPlan:
        semantic = document.metadata.get("semantic_analysis") or {}
        diagnostics: List[Dict[str, Any]] = []
        if not semantic:
            diagnostics.append(make_diagnostic(
                "missing_semantic_analysis",
                "LayoutPlan was built without semantic analysis metadata.",
                severity="warning",
                category="layout",
                fallback="generic_layout_review",
            ))

        page = self._page_layout(policy)
        sections = [SectionLayout(
            section_index=0,
            block_start=0,
            block_end=max(0, len(document.blocks) - 1),
            section_break_intent="preserve_flow",
            orientation_intent="portrait",
        )]

        tables: List[TableLayout] = []
        figures: List[FigureLayout] = []
        code_blocks: List[CodeBlockLayout] = []
        diagrams: List[DiagramLayout] = []
        table_index = 0
        asset_index = 0
        diagram_index = 0

        table_results = semantic.get("tables") or []
        header_results = semantic.get("headers") or []
        asset_results = semantic.get("assets") or []
        diagram_results = semantic.get("diagrams") or []

        for block_index, block in enumerate(document.blocks):
            if isinstance(block, Table):
                layout = self._table_layout(block, block_index, table_index, table_results, header_results, policy)
                tables.append(layout)
                diagnostics.extend(layout.diagnostics)
                table_index += 1
            elif isinstance(block, Figure):
                layout = self._figure_layout(block_index, asset_index, asset_results, policy)
                figures.append(layout)
                diagnostics.extend(layout.diagnostics)
                asset_index += 1
            elif isinstance(block, CodeBlock):
                layout = self._code_layout(block, block_index, policy)
                code_blocks.append(layout)
                diagnostics.extend(layout.diagnostics)
            elif isinstance(block, Diagram):
                layout = self._diagram_layout(block_index, diagram_index, diagram_results, policy)
                diagrams.append(layout)
                diagnostics.extend(layout.diagnostics)
                diagram_index += 1

        if any(t.landscape_recommendation == "recommended" for t in tables):
            sections[0].section_break_intent = "allow_landscape_section_for_wide_content"
            sections[0].orientation_intent = "mixed_portrait_landscape"

        plan = LayoutPlan(
            page=page,
            sections=sections,
            tables=tables,
            figures=figures,
            code_blocks=code_blocks,
            diagrams=diagrams,
            diagnostics=diagnostics,
        )
        if attach:
            document.metadata["layout_plan"] = plan.to_dict()
        return plan

    @staticmethod
    def _page_layout(policy: RenderPolicy) -> PageLayout:
        page_policy = policy.page_policy or {}
        table_policy = policy.table_policy or {}
        return PageLayout(
            page_profile=policy.page_profile,
            content_box={
                "policy": page_policy.get("content_width_policy", "content_box_derived"),
                "unit": "logical",
                "available_width": "100%",
            },
            margin_profile=page_policy.get("margins", ""),
            orientation_policy="portrait_with_policy_allowed_landscape" if table_policy.get("landscape_allowed") else "portrait",
            landscape_allowed=bool(table_policy.get("landscape_allowed")),
            section_break_intent="policy_driven_section_breaks",
        )

    def _table_layout(
        self,
        table: Table,
        block_index: int,
        table_index: int,
        table_results: List[Dict[str, Any]],
        header_results: List[Dict[str, Any]],
        policy: RenderPolicy,
    ) -> TableLayout:
        table_result = self._by_index(table_results, "table_index", table_index)
        header_result = self._by_index(header_results, "table_index", table_index)
        kind = (table_result or {}).get("kind", "generic")
        header_confidence = float((header_result or {}).get("confidence", 0.0) or 0.0)
        col_count = max((len(row.cells) for row in table.rows), default=0)
        roles = self._column_roles(kind, col_count, policy)
        ratios = self._column_width_ratios(table, kind, col_count, roles)
        columns = [
            ColumnLayout(
                index=i,
                role=roles[i],
                width_ratio=ratios[i],
                min_width_policy="role_intrinsic",
                wrap_policy="preserve_code" if roles[i] == "code" else "wrap",
            )
            for i in range(col_count)
        ]

        diagnostics = list((table_result or {}).get("diagnostics") or [])
        diagnostics.extend((header_result or {}).get("diagnostics") or [])
        overflow_risk = self._table_overflow_risk(table, kind)
        landscape = "not_required"
        if overflow_risk in ("medium", "high") and policy.table_policy.get("landscape_allowed"):
            landscape = "recommended"
        elif overflow_risk in ("medium", "high"):
            landscape = "not_allowed_by_policy"
            diagnostics.append(make_diagnostic(
                "wide_table_landscape_not_allowed",
                "Table has overflow risk but current RenderPolicy does not allow landscape.",
                severity="warning",
                category="layout",
                fallback=policy.table_policy.get("fallback_policy", "generic_table_review"),
                evidence=[f"table_index={table_index}", f"kind={kind}", f"overflow_risk={overflow_risk}"],
            ))

        if overflow_risk != "low":
            diagnostics.append(make_diagnostic(
                "table_overflow_risk",
                "Table may exceed the logical content box.",
                severity="warning",
                category="layout",
                fallback=policy.table_policy.get("fallback_policy", "generic_table_review"),
                evidence=[f"table_index={table_index}", f"columns={col_count}", f"kind={kind}"],
            ))

        split = "allow_row_split_with_header_repeat" if len(table.rows) > 20 else "avoid_split_if_possible"
        return TableLayout(
            block_index=block_index,
            table_index=table_index,
            kind=kind,
            header_confidence=header_confidence,
            columns=columns,
            wrap_policy="preserve_code_and_wrap_descriptions" if kind in ("register", "bitfield") else "wrap_cells",
            overflow_risk=overflow_risk,
            landscape_recommendation=landscape,
            split_recommendation=split,
            fallback_strategy=policy.table_policy.get("fallback_policy", "generic_table_review"),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _figure_layout(block_index: int, asset_index: int, asset_results: List[Dict[str, Any]], policy: RenderPolicy) -> FigureLayout:
        asset = next((item for item in asset_results if (item.get("attributes") or {}).get("asset_index") == asset_index), {})
        status = asset.get("kind", "unknown_asset")
        diagnostics = list(asset.get("diagnostics") or [])
        placeholder = "none"
        if status == "missing_asset":
            placeholder = "render_declared_missing_asset_placeholder"
            diagnostics.append(make_diagnostic(
                "missing_image_placeholder_intent",
                "Missing image requires an explicit placeholder intent.",
                severity="warning",
                category="layout",
                fallback=policy.image_policy.get("missing_asset_policy", "diagnostic_error"),
                evidence=[f"asset_index={asset_index}"],
            ))
        return FigureLayout(
            block_index=block_index,
            asset_index=asset_index,
            asset_status=status,
            max_width_policy=policy.image_policy.get("max_width_policy", "fit_available_content_width"),
            image_handling_intent=policy.image_policy.get("inline_image_policy", "preserve_inline"),
            missing_image_placeholder_intent=placeholder,
            svg_conversion_required=status == "svg" and "prerender" in policy.image_policy.get("svg_policy", ""),
            diagnostics=diagnostics,
        )

    @staticmethod
    def _code_layout(block: CodeBlock, block_index: int, policy: RenderPolicy) -> CodeBlockLayout:
        return CodeBlockLayout(
            block_index=block_index,
            language=block.language,
            preserve_identity=bool(policy.code_policy.get("preserve_code_identity", True)),
            wrap_policy="wrap_long_lines",
            max_width_behavior="fit_content_box",
            style_intent=policy.code_policy.get("grammar_detection_policy", "fence_language_then_content_hint"),
        )

    @staticmethod
    def _diagram_layout(block_index: int, diagram_index: int, diagram_results: List[Dict[str, Any]], policy: RenderPolicy) -> DiagramLayout:
        diagram = next((item for item in diagram_results if (item.get("attributes") or {}).get("diagram_index") == diagram_index), {})
        diagnostics = list(diagram.get("diagnostics") or [])
        targets = list(policy.diagram_policy.get("prerender_required_targets") or [])
        if targets:
            diagnostics.append(make_diagnostic(
                "diagram_prerender_requirement_planned",
                "Diagram requires prerendering for one or more target renderers.",
                severity="warning",
                category="layout",
                fallback=policy.diagram_policy.get("fallback_fidelity", "review"),
                evidence=[f"diagram_index={diagram_index}", ",".join(targets)],
            ))
        return DiagramLayout(
            block_index=block_index,
            diagram_index=diagram_index,
            diagram_kind=diagram.get("kind", "unknown_diagram"),
            prerender_required_targets=targets,
            fallback_fidelity_risk=(diagram.get("attributes") or {}).get("fidelity_risk", policy.diagram_policy.get("fallback_fidelity", "review")),
            placeholder_intent="source_placeholder_until_static_asset_available",
            diagnostics=diagnostics,
        )

    @staticmethod
    def _column_roles(kind: str, col_count: int, policy: RenderPolicy) -> List[str]:
        if col_count <= 0:
            return []
        if kind in ("register", "bitfield"):
            roles = ["code"] * max(0, col_count - 1) + ["description"]
        elif kind in ("interface", "parameter", "error_code"):
            roles = ["code"] + ["content"] * max(0, col_count - 2) + (["description"] if col_count > 1 else [])
        else:
            roles = ["content"] * col_count
        return roles[:col_count]

    @staticmethod
    def _column_width_ratios(table: Table, kind: str, col_count: int, roles: List[str]) -> List[float]:
        if col_count <= 0:
            return []
        col_text_max = [0] * col_count
        col_text_avg = [0.0] * col_count
        for ci in range(col_count):
            samples = []
            for row in table.rows:
                if ci >= len(row.cells):
                    continue
                cell = row.cells[ci]
                text = (cell.text or "").strip()
                if not text and getattr(cell, "children", None):
                    text = "".join(getattr(c, "text", "") for c in (cell.children or [])).strip()
                if text:
                    samples.append(len(text))
            if samples:
                col_text_max[ci] = max(samples)
                col_text_avg[ci] = sum(samples) / len(samples)

        weights = []
        for idx, role in enumerate(roles):
            if role == "description":
                base = 2.4 if kind in ("register", "bitfield") else 1.8
            elif role == "code":
                base = 0.9
            else:
                base = 1.0
            dynamic = 0.65 + min(2.2, 0.012 * col_text_max[idx] + 0.02 * col_text_avg[idx])
            # Prefer wider descriptive columns when header/content suggests narrative text.
            if role == "content":
                header_hint = ""
                if table.rows and table.rows[0].header and idx < len(table.rows[0].cells):
                    header_hint = (table.rows[0].cells[idx].text or "").strip()
                if any(k in header_hint for k in ("描述", "说明", "备注", "detail", "description", "note")):
                    base *= 1.35
            weights.append(base * dynamic)
        total = sum(weights) or 1.0
        ratios = [w / total for w in weights]
        min_ratio = 0.08 if col_count >= 6 else 0.12
        max_ratio = 0.46
        clamped = [max(min_ratio, min(max_ratio, r)) for r in ratios]
        norm = sum(clamped) or 1.0
        return [round(w / norm, 4) for w in clamped]

    @staticmethod
    def _table_overflow_risk(table: Table, kind: str) -> str:
        col_count = max((len(row.cells) for row in table.rows), default=0)
        max_text_len = max((len(cell.text or "") for row in table.rows for cell in row.cells), default=0)
        if col_count >= 8 or max_text_len >= 120:
            return "high"
        if col_count >= 6 or kind in ("register", "bitfield"):
            return "medium"
        return "low"

    @staticmethod
    def _by_index(items: List[Dict[str, Any]], index_key: str, index: int) -> Optional[Dict[str, Any]]:
        for item in items:
            if (item.get("attributes") or {}).get(index_key) == index:
                return item
        return items[index] if index < len(items) else None
