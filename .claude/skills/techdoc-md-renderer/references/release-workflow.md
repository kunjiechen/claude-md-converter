# Release Workflow

## Release Checklist

- Confirm default legacy behavior is unchanged.
- Run full unit/regression test suite.
- Run `phase1_regression.py`.
- Validate `render-rules.yaml` loads.
- Generate release readiness and legacy deletion review reports.
- Confirm rollout matrix and release mode.

## Regression Checklist

- no silent content loss
- mixed text/image paragraph
- raw HTML diagnostics
- register/bitfield/interface tables
- missing image and SVG image
- Mermaid diagram fallback
- DOCX structural diff
- PDF backend fallback
- quality gate pass/review/fail behavior

## Golden Update Policy

- Golden updates require a reason, before/after artifact, and reviewer note.
- Do not update golden output to hide a regression.
- Update one document family at a time.

## Adapter Readiness Policy

- HTML may graduate first.
- DOCX requires profile-specific readiness.
- PDF requires backend-specific readiness and formal PDF stays legacy by default.

## Rollback Checklist

- Set pipeline to `legacy`.
- Set release mode to `legacy_only`.
- Disable adapter feature flags.
- Restore previous golden baseline if needed.
- Keep legacy code until one clean release window after any deletion.
