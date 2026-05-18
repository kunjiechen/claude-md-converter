# Maintenance Roadmap

## Near Term

- Keep legacy default behavior.
- Use `pipeline=auto` for controlled V2 rollout.
- Track fallback rate by profile and renderer.
- Add targeted golden tests before retiring individual polish patches.

## Medium Term

- Promote lightweight HTML/DOCX V2 if quality gate and fallback metrics remain stable.
- Expand adapter readiness reporting for chip manuals.
- Move remaining rule-like thresholds into `render-rules.yaml` or profile YAML.
- Add plugin host integration only after explicit use cases appear.

## Long Term

- Retire legacy HTML after rollout metrics pass.
- Retire DOCX/PDF legacy areas only after profile/backend evidence is strong.
- Preserve compatibility-required validation and target-format shims.
- Version all profile and adapter capability changes.
