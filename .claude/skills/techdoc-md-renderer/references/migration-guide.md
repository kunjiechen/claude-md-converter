# Migration Guide

## Phase 1: Observe

Run the unified pipeline in CI or local regression without replacing the legacy
output path. Compare `UnifiedRenderReport` diagnostics, fidelity, and quality
gate results.

## Phase 2: Enable HTML Adapter

Use `render_document(..., format="html")` for lightweight technical notes.
Keep legacy fallback enabled.

## Phase 3: Profile-Gated DOCX

Enable DOCX adapter only for profiles that pass readiness:

- `lightweight_tech_note`: candidate
- `chip_register_manual`: review
- `automotive_formal_spec`: keep legacy default

## Phase 4: PDF Manual Opt-In

PDF adapter should remain explicit opt-in. Prefer WeasyPrint when available.
ReportLab fallback is readable only and is marked `non_conformant`.

## Rollback

Disable adapter feature flags or stop calling `core.pipeline.render_document()`.
Legacy renderer code paths remain intact.

## Profile Migration

New document families should start as profile YAML extensions under
`config/profiles/`. Do not add profile-specific logic to renderers. If a profile
needs custom classification or assets, add a plugin behind an explicit registry
instead of changing the core pipeline.
