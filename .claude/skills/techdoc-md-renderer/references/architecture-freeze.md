# Architecture Freeze

Phase 12 freezes the public architecture boundaries for maintenance mode.

## Frozen Core Boundaries

### DocumentModel

Owns typed document structure, source hints, diagnostics, and unsupported
content preservation. It must not contain renderer units such as DXA, EMU, CSS
pixels, backend names, or Word style names.

### SemanticAnalysis

Owns renderer-independent meaning: table kind, profile guess, header confidence,
paragraph intent, asset status, and diagram risk. Every heuristic must expose
confidence, evidence, diagnostics, and fallback policy.

### RenderPolicy

Owns resolved rules from `render-rules.yaml` and profile extensions. Renderers
must not invent semantic or layout rules.

### LayoutPlan

Owns renderer-independent layout intent: page profile, table overflow risk,
column roles/ratios, figure handling, code block intent, and diagram prerender
requirements.

### RendererAdapter

Owns target-format mapping only. Adapters consume DocumentModel, RenderPolicy,
LayoutPlan, diagnostics, and assets. They may convert units and target styles,
but must not reclassify tables or infer document profile.

### UnifiedRenderReport

Owns product-level observability: diagnostics, diagnostics summary, quality
gate, trace timings, selected profile/policy/layout, renderer metadata,
fidelity, fallback chain, and errors.

## Change Policy

- Additive changes are allowed with tests and schema/version notes.
- Breaking changes require migration guide updates and compatibility shims.
- Legacy remains default unless rollout policy explicitly changes.
- New profiles and plugins must not require core code edits.
