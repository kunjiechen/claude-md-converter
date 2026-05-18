"""Stable minimal plugin interfaces.

Plugins are optional extension points. Core rendering does not import plugin
implementations directly; registries are explicitly passed by callers or future
host applications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass(frozen=True)
class PluginInfo:
    name: str
    kind: str
    version: str
    capability_version: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TableClassifierPlugin(Protocol):
    info: PluginInfo

    def classify(self, table, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return table classification with kind, confidence, evidence, diagnostics."""


class DocumentProfilePlugin(Protocol):
    info: PluginInfo

    def analyze(self, document, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return profile guess with confidence, evidence, diagnostics."""


class RendererAdapterPlugin(Protocol):
    info: PluginInfo

    def render(self, context) -> Any:
        """Render using the standard RenderContext boundary."""


class AssetResolverPlugin(Protocol):
    info: PluginInfo

    def resolve(self, asset_ref: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve an asset without renderer-local path rules."""


class DiagramRendererPlugin(Protocol):
    info: PluginInfo

    def render_diagram(self, diagram, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render or prerender a diagram and report fidelity/fallback."""


class QualityGatePlugin(Protocol):
    info: PluginInfo

    def evaluate(self, report: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a UnifiedRenderReport-like payload."""


class PluginRegistry:
    """In-process explicit plugin registry."""

    VALID_KINDS = {
        "table_classifier",
        "document_profile",
        "renderer_adapter",
        "asset_resolver",
        "diagram_renderer",
        "quality_gate",
    }

    def __init__(self):
        self._plugins: Dict[str, Dict[str, Any]] = {kind: {} for kind in self.VALID_KINDS}

    def register(self, plugin: Any) -> None:
        info = getattr(plugin, "info", None)
        if info is None:
            raise ValueError("plugin must expose PluginInfo as .info")
        if info.kind not in self.VALID_KINDS:
            raise ValueError("unsupported plugin kind: %s" % info.kind)
        if not info.name or not info.version or not info.capability_version:
            raise ValueError("plugin info requires name, version, and capability_version")
        self._plugins[info.kind][info.name] = plugin

    def get(self, kind: str, name: str) -> Any:
        return self._plugins.get(kind, {}).get(name)

    def list(self, kind: str = "") -> List[PluginInfo]:
        if kind:
            return [plugin.info for plugin in self._plugins.get(kind, {}).values()]
        result: List[PluginInfo] = []
        for plugins in self._plugins.values():
            result.extend(plugin.info for plugin in plugins.values())
        return result
