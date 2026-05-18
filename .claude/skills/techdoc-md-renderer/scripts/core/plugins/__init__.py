"""Minimal plugin interfaces for maintenance mode."""

from .interfaces import (
    AssetResolverPlugin,
    DiagramRendererPlugin,
    DocumentProfilePlugin,
    PluginInfo,
    PluginRegistry,
    QualityGatePlugin,
    RendererAdapterPlugin,
    TableClassifierPlugin,
)

__all__ = [
    "AssetResolverPlugin",
    "DiagramRendererPlugin",
    "DocumentProfilePlugin",
    "PluginInfo",
    "PluginRegistry",
    "QualityGatePlugin",
    "RendererAdapterPlugin",
    "TableClassifierPlugin",
]
