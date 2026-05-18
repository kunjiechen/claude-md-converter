# Version Governance

## Versioned Surfaces

- spec version: `schema_versions.spec_version`
- render rules schema: `schema_versions.render_rules_schema`
- profile schema: `schema_versions.profile_schema`
- adapter capability schema: `schema_versions.adapter_capability_schema`
- plugin capability version: `PluginInfo.capability_version`

## Compatibility

Patch changes may add diagnostics or profile fields without breaking existing
profiles. Minor changes may add optional policy fields. Major changes require a
migration guide and compatibility shim.

## Deprecated Rule Policy

- Mark deprecated rule fields in documentation first.
- Keep compatibility for at least one release window.
- Emit diagnostics only when deprecated behavior affects output.
- Remove only after migration tests pass.

## Legacy Retention Policy

Legacy stays available for fallback and compatibility until deletion readiness
criteria are met. Compatibility-critical shims may remain indefinitely inside
adapter or legacy boundaries.

## Removal Policy

Removal candidates require:

- named replacement;
- tests;
- rollout evidence;
- fallback/rollback plan;
- updated migration guide.
