# Phase 11 Legacy Deletion Candidate Review

This review is a deletion decision aid, not a deletion patch. Legacy remains
present and usable.

## Executive Summary

Generated inventory summary:

- legacy inventory items: 257
- `remove_after_rollout`: 101
- `compatibility_required`: 13
- `renderer_specific_required`: 129
- `unknown_risk`: 14
- `safe_to_remove`: 0
- hardcoded rule findings: 147
- patch audit findings: 195

Conclusion: no legacy area is currently safe for immediate deletion. The best
candidate class is `remove_after_rollout`, mostly legacy HTML/DOCX/PDF rendering
functions that have V2 replacements but still depend on rollout and fallback
metrics.

## Classification Rules

| Classification | Meaning | Deletion posture |
| --- | --- | --- |
| `safe_to_remove` | Fully replaced, not used, tested, rollback exists. | None currently. |
| `remove_after_rollout` | V2 replacement exists, but profile/format rollout is incomplete. | Candidate after one clean release window. |
| `compatibility_required` | Independent source/artifact safety or compatibility behavior. | Retain long term unless equivalent V2 validation exists. |
| `renderer_specific_required` | Target-specific OOXML/CSS/backend quirk. | Keep inside adapter boundary or legacy fallback. |
| `unknown_risk` | Patch/heuristic lacks enough coverage or replacement certainty. | Do not delete. Add tests and replacement first. |

## Legacy Inventory Areas

| Area | Score | Rollout coverage | Fidelity confidence | Removal risk |
| --- | ---: | --- | --- | --- |
| legacy_html_renderer | 40 | partial default candidate | high for lightweight/chip HTML | high |
| legacy_docx_renderer | 36 | profile-gated | medium; formal/chip remain gated | high |
| legacy_pdf_renderer | 20 | manual opt-in only | low-to-medium; backend-dependent | high |
| post_polish | 23 | patch-by-patch | unknown; visual regression sensitive | high |
| preflight | 26 | not replaced | compatibility safety | high |
| postflight | 25 | not fully replaced | compatibility safety | high |

## Patch Audit Summary

Patch purposes found:

- table width/layout stabilization
- image insertion/scaling/placeholder behavior
- TOC/revision/heading/list furniture
- OOXML/CSS/backend compatibility quirks
- postflight artifact validation
- rendered-output polish after legacy conversion

Retirement rule: each patch needs a named replacement, targeted tests, rollout
evidence, and rollback path. Post-polish patches must be retired one at a time.

## Hardcoded Rule Audit

Findings include:

- DOCX DXA/EMU and physical width constants
- table width fallback values such as `9000` / `9500`
- image constants such as EMU and one-inch table-cell image sizing
- local overflow thresholds such as column count checks
- implicit fallback paths through broad exception handling

Disposition:

- Renderer-unit conversion may remain in adapter or legacy renderer boundary.
- Semantic/layout thresholds should live in `render-rules.yaml` or semantic rules.
- Silent fallback must become diagnostic-backed fallback before deletion.

## Rollout Dependency Report

Profiles still relying on legacy:

- `automotive_formal_spec`: DOCX, PDF, HTML review
- `chip_register_manual`: DOCX review, PDF
- `lightweight_tech_note`: PDF review/legacy

Renderer gaps:

- HTML: lowest risk, but legacy fallback still required until rollout metrics pass.
- DOCX: profile-gated; formal document structure remains sensitive.
- PDF: backend-dependent; formal PDF must remain legacy by default.

Deletion blocker: do not delete a legacy path if fallback rate exceeds 1% for a
profile/format over the release window.

## Compatibility Retention Policy

Retain long term:

- DOCX OOXML helpers for fields, numbering, hyperlinks, section quirks, and
  repeat headers until adapter parity is proven.
- PDF backend fallback wrappers where backend availability depends on deployment.
- Preflight source checks that prevent irreversible source/document damage.
- Postflight artifact validators for independently verifying generated outputs.
- LibreOffice/Word compatibility workarounds that are renderer-specific, tested,
  and diagnosed.

Retention rules:

- Keep compatibility-required code behind legacy or adapter boundary.
- Do not migrate target-unit conversion into semantic or layout layers.
- Every retained shim must have owner, purpose, tests, and diagnostics.

## Recommended Removal Order

1. Legacy HTML rendering functions marked `remove_after_rollout`.
2. Legacy HTML default revision/furniture shims once V2 report/golden coverage is stable.
3. Legacy DOCX table/image behavior only after profile-gated adapter rollout passes.
4. Legacy PDF adapter wrappers only after backend metrics prove stable.
5. Individual `polisher.py` patches, one patch per release, after equivalent adapter behavior and visual golden tests.

Do not start with preflight, postflight, DOCX OOXML quirks, or PDF fallback.

## High-Risk Areas

- `polisher.py`: visual regression-sensitive, patch-by-patch retirement only.
- `preflight.py`: source safety, not a renderer replacement concern.
- `postflight.py`: independent artifact validation, not fully replaced by V2 quality gate.
- `exporters/word/*`: many OOXML quirks are renderer-specific and should not be deleted wholesale.
- `exporters/pdf/*`: backend availability and fidelity vary by environment.

## Rollback Strategy

- Keep legacy code on branch until adapter coverage and rollout metrics pass removal gates.
- Delete only one classified area per release.
- Keep feature flag fallback for one release window after deletion candidate rollout.
- Restore deleted area from previous tag if quality gate, fidelity, or fallback metrics regress.
- Never remove `compatibility_required` or `renderer_specific_required` code without replacement adapter tests.
