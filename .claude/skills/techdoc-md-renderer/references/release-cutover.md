# Phase 10 Release Cutover

## Rollout Matrix

| Profile | HTML | DOCX | PDF | Default |
| --- | --- | --- | --- | --- |
| lightweight_tech_note | V2 | V2 | legacy/review | partial |
| chip_register_manual | V2 | review | legacy | partial |
| automotive_formal_spec | review | legacy | legacy | legacy |

## Release Modes

- `legacy_only`: always use legacy renderer.
- `v2_canary`: use V2 only for selected canary traffic.
- `v2_default_with_fallback`: use V2 where the matrix allows it and fall back to legacy on failure.
- `v2_strict`: use V2 only when the matrix and readiness allow it; otherwise fail before rendering.

## Pipeline Selector

The selector consumes:

- document profile
- output format
- feature flags
- quality gate requirement
- adapter readiness
- user override
- release mode

It returns one of:

- `use_legacy`
- `use_v2`
- `use_v2_with_legacy_fallback`
- `fail_before_render`

## CLI/API

CLI additions:

```text
--pipeline legacy|v2|auto
--profile automotive_formal_spec|chip_register_manual|lightweight_tech_note
--quality-gate pass|review|fail
--strict
--report
```

Backward compatibility: using `--pipeline` without a value still runs the old
preflight/convert/postflight/polish quality loop.

API example:

```python
from api import Converter

result = Converter().convert_file(
    "note.md",
    format="html",
    pipeline="auto",
    profile="lightweight_tech_note",
    report=True,
)
```

## Recommended Default

Keep process default as legacy unless `pipeline="auto"` or `pipeline="v2"` is
explicitly requested. For `auto`, use `v2_default_with_fallback`:

- lightweight technical notes: HTML/DOCX V2 with fallback
- chip manuals: HTML V2, DOCX review/fallback, PDF legacy
- automotive formal specs: legacy for DOCX/PDF, review-only HTML

## Rollback

- Use `--pipeline legacy`.
- Omit V2 pipeline options in API calls.
- Set `feature_flags.unified_pipeline_rollout.release_mode: legacy_only`.
- Legacy renderer paths remain present and are not deleted by this phase.
