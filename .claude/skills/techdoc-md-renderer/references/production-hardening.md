# Phase 9 Production Hardening Report

## Stability

- Unified pipeline wraps parser, model build, semantic analysis, policy build,
  layout planning, adapter render, and legacy fallback with explicit diagnostics.
- Adapter fallback emits `fallback_to_legacy_renderer`.
- Every unified report exposes `fidelity_level`.
- Diagnostics are summarized in `UnifiedRenderReport.diagnostics_summary`.

## Performance

`UnifiedRenderReport.performance_report` includes per-phase timings and slowest
phases.

Recommended cache strategy:

- parsed Markdown AST by source mtime/content hash
- resolved assets by path/stat signature
- prerendered diagrams by source hash and target renderer
- PDF backend availability checks per process

Optional parallel strategy:

- run asset and diagram analysis independently after DocumentModel build
- validate local images in a bounded thread pool
- batch independent document renders per isolated report

## Test Matrix

- Unit tests: Phase 1-9 module tests
- Integration tests: unified HTML/DOCX/PDF adapter calls
- Golden tests: regression Markdown and DOCX baselines
- Adapter diff tests: DOCX structural comparison
- Profile tests: lightweight, chip register, automotive formal profiles
- Fallback tests: adapter failure and rollout fallback
- Regression tests: no silent content loss and raw HTML preservation

## Quality Gate

Unified quality gate returns:

- `pass`
- `review`
- `fail`

Inputs:

- diagnostics severity/category
- fidelity level
- fallback usage
- backend metadata
- table overflow risk
- missing asset placeholders
- diagram fidelity risk

## Release Readiness

Recommended defaults:

- keep legacy as default
- use Phase 10 `auto` selector for controlled rollout
- allow lightweight HTML/DOCX V2 with fallback
- allow chip manual HTML V2, keep DOCX review-gated
- keep formal DOCX/PDF legacy by default
- keep PDF adapter manual opt-in except explicit review cases

Remaining risks:

- PDF backend availability varies by machine
- formal DOCX profiles still need rollout evidence
- legacy polish/postflight logic remains present
- binary-identical DOCX/PDF output is not guaranteed
