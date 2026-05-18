# Architecture Decision: Rule Ownership Boundary

Status: accepted

## Decision

V2 refactoring must establish the rule ownership layers before renderer rewrites:

1. Normalized `DocumentModel`
2. `SemanticAnalysis`
3. `RenderPolicy` from `render-rules.yaml`
4. `LayoutPlan`
5. `Diagnostics`

Renderers may only consume these inputs and execute target-format output. Renderers must not invent, reinterpret, or mutate document rules.

## Non-Negotiable Acceptance Gate

Any refactoring proposal, AI-generated plan, or code change must satisfy:

- Renderer does not classify table kind.
- Renderer does not choose document profile.
- Renderer does not decide whether a section/table becomes landscape.
- Renderer does not resolve or repair image paths directly.
- Renderer does not silently drop raw HTML or unsupported content.
- Renderer does not modify fallback policy.
- Renderer does not hardcode business rules or magic layout thresholds.

## Required Pre-render Inputs

Before any HTML/DOCX/PDF renderer executes, the pipeline should have produced:

- `DocumentModel`
- `SemanticAnalysis`
- `RenderPolicy`
- `LayoutPlan`
- `Diagnostics`

During migration, legacy renderers may still run behind feature flags, but V2 renderer adapters must be designed around these inputs.

## Renderer Responsibilities

Allowed renderer responsibilities:

- HTML Renderer: map model/policy/layout to semantic HTML, CSS classes, and asset references.
- DOCX Renderer: map model/policy/layout to native DOCX/OOXML structures.
- PDF Renderer: map model/policy/layout to paged output backend calls and fidelity metadata.

Forbidden renderer responsibilities:

- semantic classification;
- profile selection;
- layout policy decisions;
- asset discovery policy;
- unsupported-content policy;
- fallback severity decisions.

## Review Rule

When reviewing any future AI output or PR, reject the design if it skips `DocumentModel / SemanticAnalysis / LayoutPlan` and moves rule decisions directly into HTML, DOCX, or PDF renderer code.
