"""Renderer adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .render_context import RenderContext
from .render_result import RenderResult


class RendererAdapter(ABC):
    target: str = "unknown"

    @abstractmethod
    def render(self, context: RenderContext) -> RenderResult:
        """Render a DocumentModel using an already-built RenderPolicy and LayoutPlan."""
