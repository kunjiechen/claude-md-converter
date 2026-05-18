"""Base renderer adapter contracts."""

from .render_context import RenderContext
from .render_result import RenderResult
from .renderer_adapter import RendererAdapter

__all__ = ["RenderContext", "RenderResult", "RendererAdapter"]
