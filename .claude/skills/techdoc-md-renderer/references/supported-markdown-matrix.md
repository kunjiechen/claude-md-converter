# Supported Markdown Matrix

| Feature | V2 Status | Notes |
| --- | --- | --- |
| Headings | supported | Preserved in DocumentModel; heading numbering is policy-driven for adapters. |
| Paragraphs | supported | Inline runs preserved, including mixed text and images. |
| Tables | supported | Semantic classification and LayoutPlan table intent are available. |
| Register tables | supported with review | Classification supports explicit marker and header/content heuristics. |
| Bitfield tables | supported with review | Layout risk is diagnosed for wide/dense tables. |
| Code blocks | supported | Code identity and language are preserved. |
| Mermaid | supported as diagram source | Static prerender remains a renderer/backend concern; PDF/DOCX may degrade. |
| Raw HTML block | preserved with diagnostics | Non-HTML targets use fallback or placeholder behavior. |
| Raw inline HTML | preserved/review | HTML may preserve; paginated targets diagnose fallback. |
| Images | supported | Local/missing/SVG status is analyzed before rendering. |
| Pagebreak | supported | Adapter support varies; degraded behavior is diagnosed. |
| Complex colspan/rowspan | partial | DOCX adapter diagnoses unsupported/degraded behavior. |
| Advanced pagination | planned | Widow/orphan and perfect table split are not implemented. |
| Footnotes | legacy/parser-dependent | Not a V2 adapter completeness guarantee yet. |
