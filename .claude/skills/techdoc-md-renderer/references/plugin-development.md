# Plugin Development

Plugins are optional extension points. They are registered explicitly through
`PluginRegistry`; core rendering does not auto-import plugin code.

## Plugin Types

- `table_classifier`
- `document_profile`
- `renderer_adapter`
- `asset_resolver`
- `diagram_renderer`
- `quality_gate`

## Minimal Example

```python
from core.plugins import PluginInfo, PluginRegistry

class MyClassifier:
    info = PluginInfo(
        name="my_classifier",
        kind="table_classifier",
        version="1.0.0",
        capability_version="1.0",
    )

    def classify(self, table, context):
        return {
            "kind": "generic",
            "confidence": 0.8,
            "evidence": ["plugin rule"],
            "diagnostics": [],
        }

registry = PluginRegistry()
registry.register(MyClassifier())
```

## Contract

Plugins must:

- return diagnostics for degraded or unsupported behavior;
- expose `PluginInfo` with name, kind, version, and capability version;
- avoid mutating DocumentModel content silently;
- treat RenderPolicy and LayoutPlan as authoritative;
- declare fidelity/fallback when producing rendered artifacts.

## Non-Goals

Phase 12 does not add plugin auto-discovery, package loading, or remote plugin
execution. Those are future host-application concerns.
