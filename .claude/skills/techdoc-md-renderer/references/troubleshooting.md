# Troubleshooting

## Adapter Falls Back to Legacy

Check diagnostics for `fallback_to_legacy_renderer` and the original adapter
error. This is expected when rollout policy blocks a profile or an adapter
fails.

## PDF Backend Changes

PDF output records `backend_used`. WeasyPrint is preferred. Chromium and
wkhtmltopdf are review fidelity. ReportLab is `non_conformant` readable
fallback.

## Missing Images

Missing assets are diagnosed during semantic/layout stages and rendered as
explicit placeholders by adapters that support placeholders.

## Raw HTML

Raw HTML is not silently dropped. It is preserved for HTML and diagnosed for
paginated targets.

## Wide Tables

Wide tables produce layout diagnostics. Landscape recommendation is an intent
in LayoutPlan; adapters must diagnose if they cannot fully apply it.

## Config Errors

`RuleLoader` validates `render-rules.yaml` before policy construction. Invalid
profiles, unknown PDF backends, invalid fidelity levels, and unsafe unsupported
content policies fail early.

## Profile Extension Does Not Load

Check that the file is under `config/profiles/`, has `profile`, optional
`extends`, and resolves to a profile with `page_profile`, `document_policy`, and
`table_policy`.

## Plugin Is Ignored

Phase 12 plugins are explicit. Register the plugin with `PluginRegistry`; there
is no automatic import or discovery.
