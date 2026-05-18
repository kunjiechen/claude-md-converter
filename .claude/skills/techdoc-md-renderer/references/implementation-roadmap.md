# Implementation Roadmap

## Phase 0. Baseline and Safety

Files to inspect/freeze:

- `.claude/skills/techdoc-md-renderer/scripts/parser.py`
- `.claude/skills/techdoc-md-renderer/scripts/html_engine/renderer.py`
- `.claude/skills/techdoc-md-renderer/scripts/exporters/word/*`
- `.claude/skills/techdoc-md-renderer/scripts/exporters/pdf/exporter.py`
- `.claude/skills/techdoc-md-renderer/scripts/polisher.py`
- `.claude/skills/techdoc-md-renderer/scripts/analyzers/*`

Actions:

1. Add regression fixtures for current behavior before refactoring.
2. Keep the existing pipeline operational.
3. Add golden tests for known fragile cases: mixed image paragraph, raw HTML block, register table, split table, Mermaid failure, code block.

Rollback:

- Preserve current `Converter` and `ConversionPipeline` APIs.
- Gate new model pipeline behind a feature flag, for example `use_document_model=false`.

## Phase 1. Config Loading

Create:

- `scripts/config/__init__.py`
- `scripts/config/loader.py`
- `scripts/config/schema.py`
- `scripts/config/default_render_rules.yaml`

Design:

- Load defaults from packaged YAML.
- Allow user override file.
- Merge profile selection into `RenderPolicy`.
- Validate required sections.

Migration:

- Current constants remain as fallback.
- New config mirrors legacy defaults first.

Tests:

- YAML parses.
- profile selection works.
- missing config fields produce clear errors.

## Phase 2. Normalized Document Model

Create:

- `scripts/document_model/__init__.py`
- `scripts/document_model/nodes.py`
- `scripts/document_model/normalize.py`
- `scripts/document_model/diagnostics.py`

Model:

- block nodes: Heading, Paragraph, Table, CodeBlock, Figure, Diagram, List, BlockQuote, PageBreak, RawHtmlBlock, UnsupportedBlock.
- inline nodes: Text, Strong, Emphasis, Link, InlineCode, Image, Math, Break, FootnoteReference.

Modify:

- `parser.py` remains as parser AST producer initially.
- `normalize.py` converts current dict AST to typed model.

Critical fix:

- Preserve mixed text/image paragraphs.

Tests:

- parser AST -> model snapshot tests.
- unsupported raw HTML preserved as diagnostic node.

Rollback:

- renderers can still consume old dict AST until adapters are ready.

## Phase 3. Semantic Analysis and Reason Codes

Create:

- `scripts/analyzers/semantic_analyzer.py`
- `scripts/analyzers/header_analyzer.py`
- `scripts/analyzers/asset_analyzer.py`

Refactor:

- `table_classifier.py` returns evidence and column roles.
- `paragraph_classifier.py` returns reason codes.
- document classification consumes model nodes.

Tests:

- table kind evidence tests.
- low-confidence generic table tests.
- explicit marker conflict warning.

Rollback:

- Keep old classifier API as wrapper around new result object.

## Phase 4. Asset Resolver

Create:

- `scripts/assets/resolver.py`

Responsibilities:

- resolve local paths against source document directory;
- data URI handling;
- remote image policy;
- temp/cache management;
- mime and dimension probing.

Modify:

- `html_engine/renderer.py`
- `exporters/word/image_builder.py`
- `exporters/word/table_builder.py`
- `exporters/html/exporter.py`

Fixes:

- relative image inlining.
- consistent missing-image diagnostics.

Tests:

- relative image inlining.
- missing required/optional asset.
- data URI image.

## Phase 5. Layout Planner

Create:

- `scripts/layout/__init__.py`
- `scripts/layout/page.py`
- `scripts/layout/table_layout.py`
- `scripts/layout/figure_layout.py`
- `scripts/layout/plan.py`
- `scripts/layout/font_metrics.py`

Responsibilities:

- derive content box from page profile or DOCX section;
- compute table role constraints;
- evaluate overflow;
- decide wrapping/compact/landscape;
- produce layout plan.

Modify:

- `exporters/word/table_builder.py` consumes table layout plan.
- `polisher.py` shifts from inventing layout to validating/repairing.

Tests:

- A4 portrait/landscape content box.
- register table overflow decision.
- no hardcoded 9000/13200 in semantic classifier.

Rollback:

- allow `legacy_table_layout=true`.

## Phase 6. Renderer Adapters

Create:

- `scripts/renderers/html_adapter.py`
- `scripts/renderers/docx_adapter.py`
- `scripts/renderers/pdf_adapter.py`

Migration approach:

- wrap existing `HtmlRenderer`, `WordExporter`, and `PdfExporter`.
- gradually move logic from old exporters into adapters.

Renderer boundaries:

- adapters consume document model, render policy, and layout plan.
- adapters do not run semantic classifiers.

Tests:

- same document renders HTML/DOCX/PDF.
- renderer fallback diagnostics appear.

## Phase 7. Word Improvements

Modify:

- `exporters/word/list_builder.py`
- `exporters/word/exporter.py`
- `exporters/word/style_config.py`
- `exporters/word/table_builder.py`

Actions:

1. Add native numbering path for lists.
2. Add `CodeBlock` style and preserve code block boundaries.
3. Make TOC/revision controlled by profile.
4. Apply layout plan to tables and images.

Tests:

- native nested list.
- code block remains code block.
- lightweight profile has no revision table.

## Phase 8. HTML and PDF Improvements

Modify:

- `html_engine/renderer.py`
- `exporters/html/exporter.py`
- `exporters/pdf/exporter.py`
- `polisher.py`

Actions:

1. Fix HTML polisher dirty-write behavior.
2. Make table wrappers part of HTML renderer, not post-polish.
3. Add PDF backend capability/fidelity reporting.
4. Fail/review raw Mermaid fallback according to policy.

Tests:

- wide table wrapper persists.
- PDF backend sidecar records fidelity.
- ReportLab fallback marked non-conformant.

## Phase 9. Quality Gates

Modify:

- `analyzers/quality_gate.py`
- `analyzers/quality_report.py`
- `postflight.py`

Actions:

- add content-loss diagnostics;
- add fallback fidelity to quality gate;
- add low-confidence classification review category;
- add profile-specific pass/review/fail criteria.

Tests:

- formal delivery fails on missing required image.
- readable delivery reviews but does not fail on optional missing image.
- non-conformant PDF fails when PDF was explicitly requested for final delivery.

## Phase 10. Migration Strategy

1. Keep current `Converter` API.
2. Add config parameter: `rules_path`, `document_profile`, `use_document_model`.
3. Default to legacy path for one release.
4. Run both pipelines in regression mode and compare diagnostics/output structure.
5. Switch default to document model after parity for core samples.

## Rollback Plan

- Feature flag: `use_document_model=false`.
- Feature flag: `legacy_table_layout=true`.
- Keep old exporters until adapter tests pass.
- Keep old `render-rules.yaml` snapshot in version control as `render-rules.legacy.yaml`.

## Minimum Test Suite

Regression documents:

- mixed inline image/text paragraph;
- raw HTML block and raw HTML table;
- register table and bitfield table;
- interface and BNF table;
- split table normalization;
- short paragraph compacting;
- Mermaid flowchart, sequence diagram, and failing diagram;
- code block with actual C code;
- grammar/spec code block with explicit marker;
- lightweight tech note with no revision history.

Assertions:

- no silent content loss;
- classifier reason codes exist;
- table layout plan exists;
- renderer fallback fidelity recorded;
- formal quality gate outcomes are deterministic.
