# Profile Authoring

Profiles can be added without changing core code by placing YAML files in:

```text
.claude/skills/techdoc-md-renderer/config/profiles/
```

## Minimal Profile

```yaml
profile: api_reference
extends: lightweight_tech_note
profile_version: "1.0"
description: API reference profile.
document_policy:
  toc: optional
table_policy:
  supported_table_kinds: [interface, parameter, error_code, reference, generic]
```

`extends` names an existing profile from `render-rules.yaml` or another loaded
profile. The extension is deep-merged over the base profile.

## Built-In Extension Profiles

- `chip_manual`
- `autosar_spec`
- `api_reference`
- `test_report`
- `requirement_spec`

## Rules

- `unsupported_content_policy` must remain `diagnostic_required`.
- Every profile must resolve to a `page_profile`, `document_policy`, and
  `table_policy`.
- Profile-specific renderer units are not allowed outside renderer policy.
- Profile changes require regression coverage for affected document families.
