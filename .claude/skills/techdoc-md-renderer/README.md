# TechDoc Markdown Renderer

Markdown-to-HTML/DOCX/PDF rendering engine for technical documents such as
automotive electronics specifications, embedded software notes, chip manuals,
register tables, interface specifications, and Chinese formal documents.

## Current Production Posture

- Legacy renderer remains the default path.
- V2 adapter pipeline is available behind feature flags and the
  `core.pipeline.render_document()` entrypoint.
- V2 pipeline stages are:
  `Markdown -> DocumentModel -> SemanticAnalysis -> RenderPolicy -> LayoutPlan -> RendererAdapter`.
- HTML adapter is stable enough for controlled rollout.
- DOCX adapter is governed by profile rollout and legacy fallback.
- PDF adapter is available as a minimal backend-managed implementation.

## V2 Unified Entrypoint

```python
from core.pipeline import render_document

report = render_document(
    "manual.md",
    format="html",
    output_path="manual.html",
)

print(report.success)
print(report.fidelity_level)
print(report.quality_gate["status"])
```

The report includes diagnostics, selected profile, render policy, layout plan,
phase timings, backend metadata, fallback chain, and quality gate result.

## Default Safety

The existing `Converter` API and CLI behavior are unchanged. Adapter rendering
must be enabled explicitly through feature flags or by calling the unified
pipeline directly.

## Documentation

- **[Skill Reference](.claude/skills/techdoc-md-renderer/references/README.md)** — full skill documentation and usage
- **[Engineering Playbook](.claude/skills/techdoc-md-renderer/references/engineering-playbook.md)** — field manual: diagnosis, feature process, fidelity governance, rollout, legacy retirement.
- **[Verification Plan](.claude/skills/techdoc-md-renderer/references/verification-plan.md)** — legacy vs V2 verification architecture: layer-by-layer, format-by-format, gap analysis, rollout readiness.
- [Architecture](.claude/skills/techdoc-md-renderer/references/architecture.md)
- [Architecture Freeze](.claude/skills/techdoc-md-renderer/references/architecture-freeze.md)
- [Plugin Development](.claude/skills/techdoc-md-renderer/references/plugin-development.md)
- [Profile Authoring](.claude/skills/techdoc-md-renderer/references/profile-authoring.md)
- [Migration Guide](.claude/skills/techdoc-md-renderer/references/migration-guide.md)
- [Release Workflow](.claude/skills/techdoc-md-renderer/references/release-workflow.md)
- [Version Governance](.claude/skills/techdoc-md-renderer/references/version-governance.md)
- [Real Document Validation Program](.claude/skills/techdoc-md-renderer/references/real-document-validation-program.md)
- [Release Cutover](.claude/skills/techdoc-md-renderer/references/release-cutover.md)
- [Legacy Deletion Candidate Review](.claude/skills/techdoc-md-renderer/references/legacy-deletion-candidate-review.md)
- [Supported Markdown Matrix](.claude/skills/techdoc-md-renderer/references/supported-markdown-matrix.md)
- [Troubleshooting](.claude/skills/techdoc-md-renderer/references/troubleshooting.md)
- [Known Limitations](.claude/skills/techdoc-md-renderer/references/known-limitations.md)
- [Maintenance Roadmap](.claude/skills/techdoc-md-renderer/references/maintenance-roadmap.md)
- [Production Hardening Report](.claude/skills/techdoc-md-renderer/references/production-hardening.md)
