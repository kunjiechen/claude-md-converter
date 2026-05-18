# Architecture

## Pipeline

The target architecture is renderer-independent:

```text
Markdown
  -> legacy parser AST
  -> Typed DocumentModel
  -> SemanticAnalysis
  -> RenderPolicy
  -> LayoutPlan
  -> HTML/DOCX/PDF RendererAdapter
```

## Rule Ownership

- Parser: syntax recognition and source preservation only.
- DocumentModel: typed document structure, source hints, unsupported content.
- SemanticAnalysis: table kind, document profile guess, asset status, diagram risk.
- RenderPolicy: rules resolved from `config/render-rules.yaml`.
- LayoutPlan: renderer-independent layout intent.
- RendererAdapter: target-specific mapping and output only.

Renderers must not reclassify table kind, infer document profile, invent overflow
strategy, or silently discard unsupported content.

## Observability

`UnifiedRenderReport` includes:

- diagnostics and diagnostics summary
- quality gate result
- render trace and phase timings
- selected semantic profile and render policy
- layout risk summary through LayoutPlan
- backend used and fallback metadata

## Legacy Posture

Legacy exporters, polish, preflight, and postflight remain available. Retirement
is governed by audit metrics and patch retirement conditions, not by direct
deletion.

## Maintenance Mode Extension Points

Phase 12 freezes the core boundaries and adds explicit extension mechanisms:

- plugins are registered through `core.plugins.PluginRegistry`;
- profiles are added as YAML files in `config/profiles/`;
- versioned surfaces are tracked in `schema_versions`;
- default legacy behavior remains unchanged.
