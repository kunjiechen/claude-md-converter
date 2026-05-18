# Rule Quality and Architecture Review

Review target: the extracted `techdoc-spec.md` and `render-rules.yaml`, grounded in the current implementation.

Overall verdict: the rule system is useful and industry-aware, but not yet stable as a formal rendering standard. It is strongest where it models document semantics, such as table kinds and technical-document furniture. It is weakest where layout is encoded as renderer-specific magic numbers, post-processing patches, and hardcoded company assumptions.

## 1. Rule Quality Report

| Rule Area | Classification | Stability | Generalization | Maintainability | Renderer Independence | Industry Suitability | Why |
|---|---|---:|---:|---:|---:|---:|---|
| Markdown parser baseline: markdown-it + table/strikethrough/footnote/math/deflist | GOOD | High | High | High | High | High | Uses standard parser and plugins; predictable and portable. |
| Custom dict AST as IR | FRAGILE | Medium | Medium | Low | Medium | Medium | Lightweight, but untyped. Renderers depend on ad hoc keys like `attributes.raw_html`, `is_header`, and `children`. |
| HTML as canonical intermediate representation | ACCEPTABLE | Medium | High | Medium | Medium | High | Good unifying layer, but Word/PDF layout decisions leak back into HTML classes and post-polish. |
| `==highlight==` regex preprocessing | ACCEPTABLE | Medium | Medium | Medium | High | Medium | Useful extension and excludes code blocks, but regex Markdown extensions should be tokenizer-level rules. |
| `<!-- pagebreak -->` control comment | GOOD | High | High | High | Medium | High | Clear author control. Renderer adapters can map it to page breaks. |
| Table kind marker `<!-- table: kind -->` | GOOD | High | High | High | High | High | Explicit semantic override is explainable and scalable. |
| Prose markers `<!-- prose: compact/preserve -->` | ACCEPTABLE | Medium | Medium | Medium | High | Medium | Good escape hatch, but comment syntax is implicit and not discoverable. |
| Heading renumbering and manual-number stripping | ACCEPTABLE | Medium | Medium | Medium | Medium | High | Good for formal specs, risky for documents where numbering is meaningful source text. |
| Generated TOC replacing source TOC | FRAGILE | Medium | Low | Medium | Low | Medium | TOC detection depends on Chinese title and link pattern; Word and HTML TOC depth differ. |
| Always inserting revision section | FRAGILE | High | Low | Medium | Low | High for formal specs only | Appropriate for controlled company docs, but not a general Markdown renderer rule. Should be document-profile policy. |
| Revision table normalization to six columns | ACCEPTABLE | Medium | Medium | Medium | Medium | High | Strong domain convention, but column mapping is positional and brittle for variants. |
| Table header inference from text features | FRAGILE | Low | Medium | Low | High | Medium | Heuristic has many thresholds and content assumptions. Hard to explain why a row is or is not a header. |
| Table classifier taxonomy | GOOD | Medium | High | Medium | High | High | The kinds are industry-relevant: register, bitfield, BNF, parameter, interface, error code. |
| Table classifier keyword matching | ACCEPTABLE | Medium | Medium | Medium | High | High | Explainable, deterministic, but needs externalized dictionaries and localization packs. |
| Table width weights per kind | FRAGILE | Medium | Low | Low | Low | Medium | Static weights work for samples, but do not adapt to page profile, font metrics, or localized headers. |
| Portrait `9000` / landscape `13200` dxa | BAD | Low | Low | Low | None | Medium | Page geometry is hardcoded and duplicated. Should derive from section/page/margin config. |
| Landscape switch: `col_count >= 7 and estimated_width > 0.85 * 9000` | FRAGILE | Low | Medium | Low | Low | Medium | Better than column-count only, but threshold is magic and assumes A4/10pt/CJK metrics. |
| Character-width estimates: CJK 240, kana 220, other 120 dxa | FRAGILE | Low | Medium | Low | Low | Medium | Useful approximation, but font-size, font-family, bold/code style, and DPI are ignored. |
| DOCX table post-polish width recalculation | ACCEPTABLE | Medium | Medium | Low | None | High | Solves real Word problems, but as a post-hoc mutation it is hard to reason about and test. |
| Consecutive table harmonization | ACCEPTABLE | Medium | Medium | Medium | Low | High | Good for split tables, but depends on document-order OOXML scanning. |
| HTML table wrapper polish bug | CRITICAL TECH DEBT | Low | Low | Low | Low | Medium | The rule may not persist because `modified` is not set. This undermines HTML overflow guarantees. |
| Word native table generation | GOOD | High | High | Medium | Low | High | Correct target-specific implementation. Should be adapter layer, not core rule. |
| Word list manual bullets | FRAGILE | Medium | Low | Medium | None | Medium | Visually stable, semantically poor. Accessibility, copy/paste, nested numbering, and TOC/bookmark behavior suffer. |
| Code blocks converted to line paragraphs in Word | BAD | Medium | Low | Medium | None | Low for software docs | It intentionally optimizes grammar/spec snippets but destroys code block identity. |
| Code/spec classifier: 40% line threshold | FRAGILE | Low | Medium | Low | Medium | Medium | Magic ratio; false positives likely in embedded C, config snippets, and naming examples. |
| Paragraph compacting thresholds: CJK 42, Latin 90, run 2-8 | FRAGILE | Low | Medium | Medium | High | Medium | Helpful for converted Word text, but threshold-driven prose layout can change document rhythm unexpectedly. |
| Paragraph note prefixes | ACCEPTABLE | Medium | Medium | Medium | High | High | Industry-appropriate, but should be localized/profile-driven. |
| Raw HTML table support | ACCEPTABLE | Medium | Medium | Medium | Medium | High | Useful for complex cells and merged cells. Needs stronger sanitization and typed cell AST. |
| Raw HTML blocks ignored | BAD | High | Low | Medium | High | Low | Silent content loss is unacceptable for technical documents. |
| Image paragraph becomes first image node | CRITICAL TECH DEBT | Low | Low | Medium | Medium | Low | Causes content loss for mixed text/images. This violates document-fidelity expectations. |
| Image max width 12cm then 15cm polish | BAD | Low | Low | Low | None | Medium | Conflicting limits in two phases. Should be one layout constraint derived from content box. |
| HTML image inlining path depends on unset renderer input dir | CRITICAL TECH DEBT | Low | Low | Low | Low | Medium | Makes `inline_images=True` unreliable for relative paths. |
| Mermaid HTML browser mode | GOOD | High | High | High | High | High | Correct for interactive HTML and avoids server dependencies. |
| Word/PDF diagram server rendering fallback chain | ACCEPTABLE | Medium | High | Medium | Low | High | Pragmatic, but needs explicit fidelity states and no raw Mermaid fallback in final PDF/Word unless allowed. |
| Python flowchart painter size constants | FRAGILE | Medium | Low | Medium | None | High for G-C110 subset | Domain-aligned but hardcoded. Needs diagram profile/config. |
| PDF backend chain | GOOD | Medium | High | Medium | Low | High | Strong resiliency strategy. Needs quality/fidelity levels in formal output contract. |
| ReportLab text fallback | ACCEPTABLE | High | Medium | High | Low | Low for final deliverables | Fine as emergency readable fallback, but should be marked non-conformant for layout deliverables. |
| PDF A4/2.5cm/page footer | ACCEPTABLE | High | Medium | High | Medium | High for Chinese formal docs | Good default, but belongs in a page profile, not global rule. |
| Postflight placeholder regexes | ACCEPTABLE | Medium | Medium | Medium | Medium | High | Useful safety net, but placeholders should be structured diagnostics from renderers. |
| Preflight mutating source in pipeline | FRAGILE | Medium | Low | Medium | High | Medium | Good for automation, risky for audit-controlled documents. Needs dry-run/patch mode and backups as first-class policy. |

## 2. Technical Debt Report

### Critical Tech Debt

1. **Content Loss in Image Paragraphs**
   - Current behavior: if a paragraph contains an image token, the parser returns the first image node instead of a paragraph with mixed inline content.
   - Risk: technical documents frequently say “see below” or include inline icons with text. Text can disappear silently.
   - Better rule: paragraphs are block containers with inline children, including images.
   - Scalable abstraction: `ParagraphInline[]` with `TextRun`, `ImageRun`, `LinkRun`, `MathRun`, `BreakRun`.
   - Config alternative: `images.inline_policy: preserve | promote_single_image | error_on_mixed`.

2. **Renderer-Specific Magic Geometry**
   - Current behavior: widths such as `9000`, `13200`, `600`, `240`, `120`, `9500`, `12cm`, `15cm` are embedded as rules.
   - Risk: changing page size, margins, font, orientation, or locale invalidates layout.
   - Better rule: derive content area from a `PageProfile` and derive text metrics from a `FontMetricsProvider`.
   - Scalable abstraction: `LayoutContext(page, margins, section, font_map, target_renderer)`.
   - Config alternative: `profiles.page.A4.content_width` generated or declared once, referenced by name.

3. **HTML Polisher Mutation Bug**
   - Current behavior: table wrapper changes are not guaranteed to be written because `modified` is not set.
   - Risk: documented overflow handling may not occur.
   - Better rule: every mutating polish operation must return a patch object and mark dirty.
   - Scalable abstraction: `PolishPatch {target, operation, changed, diagnostics}`.
   - Config alternative: `html.overflow.tables.wrapper.enabled: true`, tested with golden HTML.

4. **Relative Image Inlining Bug**
   - Current behavior: renderer `_input_dir` is not reliably set before inlining.
   - Risk: single-file HTML distribution can lose images.
   - Better rule: all asset resolution uses a central `AssetResolver`.
   - Scalable abstraction: `AssetResolver.resolve(uri, base_dir, output_dir, embed_policy)`.
   - Config alternative: `assets.base_dir: source_document_dir`.

5. **Silent Raw HTML Block Dropping**
   - Current behavior: raw HTML blocks other than full tables/control comments are ignored.
   - Risk: content loss, especially warnings, custom blocks, embedded figures, and vendor snippets.
   - Better rule: unsupported raw HTML emits an explicit warning and either preserves sanitized HTML or converts text fallback.
   - Scalable abstraction: `UnsupportedNodePolicy = preserve_html | text_fallback | reject`.
   - Config alternative: `markdown.raw_html.block_policy`.

### High-Risk Fragility

1. **Table Header Heuristic**
   - Risk: data rows with short labels or technical symbols can be misclassified.
   - Better rule: keep parser header info as evidence, run classifier with confidence, and expose reason codes.
   - Abstraction: `HeaderAnalysis {is_header, confidence, evidence[], override_source}`.

2. **Table Kind Width Weights**
   - Risk: fixed weights cannot handle localized headers, unusual data, or target-specific page sizes.
   - Better rule: table kind suggests semantic column roles; layout engine calculates final widths from roles and measured content.
   - Abstraction: `ColumnRole {id, priority, min, max, wrap, align, font_role}`.

3. **Word Post-Polish as Primary Layout Engine**
   - Risk: layout happens after rendering, so outputs are hard to test and explain.
   - Better rule: layout plan is computed before rendering and consumed by each renderer.
   - Abstraction: `LayoutPlan` attached to table/figure/section nodes.

4. **Always-On Formal Furniture**
   - Risk: every document gets TOC/revision, even tutorials, lightweight specs, or web articles.
   - Better rule: document profile controls furniture.
   - Abstraction: `DocumentProfile` with `furniture: toc/revision/cover/header/footer`.

5. **Code Block Reclassification**
   - Risk: actual code may be rendered as body/spec paragraphs.
   - Better rule: code blocks remain code blocks unless explicitly tagged as grammar/spec.
   - Abstraction: `CodeBlock.kind = code | grammar | naming_rule | register_formula`.

## 3. Recommended Rule Architecture

The current rule file should be split into layers:

```text
Document Semantics
  headings, paragraphs, lists, tables, figures, diagrams, math, footnotes

Domain Profiles
  automotive_spec, chip_manual, register_doc, api_spec, coding_standard

Layout Intent
  page profile, furniture, table roles, wrap policies, keep rules

Renderer Adapters
  html, docx, pdf backend capabilities and target mappings

Quality Policy
  preflight severity, postflight gates, fallback acceptability
```

### Core Types

`DocumentModel`
- typed AST, not dictionaries;
- block nodes and inline nodes are distinct;
- raw HTML and unsupported syntax are explicit nodes, not dropped.

`RuleSet`
- contains semantic rules and domain decisions;
- no renderer units such as DXA or Word style names in semantic rules.

`LayoutPlan`
- computed once from content, page profile, and domain profile;
- contains table column roles, figure bounds, section breaks, keep constraints, and pagination intent.

`RendererAdapter`
- maps semantic/layout intent to target-specific implementation;
- DOCX adapter handles OOXML details;
- HTML adapter handles CSS classes;
- PDF adapter handles paged-media and backend limitations.

`Diagnostics`
- every heuristic emits evidence and confidence;
- every fallback emits fidelity level and delivery recommendation.

### Better Rule Principles

- **Semantic first**: classify a table column as `address`, not “column 0 is centered and Consolas”.
- **Profile-driven**: A4 formal Chinese spec is a profile, not a universal default.
- **Measured layout**: use font metrics and content-box dimensions instead of fixed char widths where possible.
- **Explainable heuristics**: every classifier result includes matched keywords, score, and override source.
- **Renderer capability negotiation**: if PDF backend lacks CSS counters or SVG support, report that before rendering.
- **No silent loss**: unsupported content must be preserved, degraded with diagnostics, or rejected by policy.

## 4. Suggested `render-rules.yaml` Redesign

The current YAML is a flattened snapshot. A v2 design should separate semantics, profiles, layout, renderers, and quality.

```yaml
schema_version: "2.0"

defaults:
  document_profile: automotive_formal_spec
  page_profile: a4_cn_formal
  locale: zh-CN
  unsupported_policy: warn_and_preserve_text

page_profiles:
  a4_cn_formal:
    size: A4
    margins: {top: 2.5cm, right: 2.5cm, bottom: 2.5cm, left: 2.5cm}
    derive_content_box: true
    footer:
      page_number: {position: bottom-center, first_page: false}
  web_responsive:
    content_width: fluid
    margins: responsive

document_profiles:
  automotive_formal_spec:
    furniture:
      toc: {enabled: true, levels_html: [1, 2, 3], levels_docx: [1, 2]}
      revision_history: {enabled: true, required: true}
      cover: {enabled: false}
    numbering:
      headings: {enabled: true, strip_source_numbering: true}
    fonts: cn_formal
    quality_gate: formal_delivery
  lightweight_tech_note:
    furniture:
      toc: {enabled: auto, min_headings: 4}
      revision_history: {enabled: false}
    numbering:
      headings: {enabled: false}

semantic_rules:
  markdown:
    parser: markdown-it-py
    plugins: [table, strikethrough, footnote, texmath, deflist]
    raw_html:
      block_policy: preserve_sanitized
      inline_policy: parse_known_preserve_unknown
    extensions:
      pagebreak_comment: "<!-- pagebreak -->"
      table_kind_marker: "<!-- table: {kind} -->"
      prose_policy_marker: "<!-- prose: {policy} -->"

  blocks:
    paragraph:
      mixed_inline_images: preserve
      compacting:
        enabled: profile
        classifiers:
          - name: short_cjk
            max_visual_chars: 42
            locale: zh
          - name: short_latin
            max_visual_chars: 90
            locale: latin
        emit_reason_codes: true
    code_block:
      preserve_identity: true
      grammar_detection:
        enabled: true
        require_explicit_marker_for_full_restyle: true
        marker: "<!-- code: grammar -->"

table_semantics:
  classifiers:
    - kind: register
      headers_any: [address, addr, offset, register, reg, bits, bit, field, access, reset, description]
      content_patterns: [hex_address, bit_range, access_mode]
      min_score: 0.75
    - kind: bitfield
      headers_any: [bits, bit, field, name, access, reset, description]
      content_patterns: [bit_range, access_mode]
      min_score: 0.75
    - kind: interface
      headers_any: [field, element_name, type, required, description, example]
      min_score: 0.70
  explicit_override:
    enabled: true
    validation: warn_if_content_conflicts
  output:
    attach_analysis:
      confidence: true
      reason_codes: true

table_layout_roles:
  roles:
    address: {font_role: code, align: center, min: 8mm, wrap: false}
    bit_range: {font_role: code, align: center, min: 10mm, wrap: false}
    access: {font_role: code, align: center, min: 8mm, wrap: false}
    reset: {font_role: code, align: center, min: 10mm, wrap: false}
    description: {font_role: body, align: left, min: 25mm, flex: 3, wrap: true}
    symbol: {font_role: code, align: center, min: 15mm, wrap: false}
  strategy:
    compute_from_content: true
    use_font_metrics: true
    allow_landscape:
      when: overflow_risk
      threshold: content_box_ratio
      ratio: 0.92
    min_column_width: 6mm
    max_single_column_ratio: profile

assets:
  resolver:
    base_dir: source_document_dir
    remote_policy: warn_and_fetch_if_enabled
    missing_policy: diagnostic_placeholder
  images:
    max_width: content_box
    preserve_aspect_ratio: true
    caption:
      source: alt_or_title
      numbering: profile
    svg_policy:
      html: preserve
      docx: convert_to_png_or_warn

diagrams:
  mermaid:
    detection: fence_language_or_content
    html: {mode: browser}
    paged_outputs:
      mode: prerender
      fallback_policy: fail_or_placeholder
      allowed_fallbacks: [python_flowchart, kroki, mmdc]
      fidelity_required_for_delivery: rendered_image
  plantuml:
    paged_outputs:
      allowed_fallbacks: [plantuml_cli, kroki]

renderer_adapters:
  html:
    classes_from_semantics: true
    css_profile: cn_formal
    overflow:
      tables: {wrapper: true, scroll: horizontal}
  docx:
    styles:
      map:
        body: 正文2
        note: 正文3
        compact: 紧凑正文
        code: CodeBlock
        grammar: 规范
    lists:
      mode: native_numbering
      fallback: manual_prefix
    tables:
      mode: native_docx
      apply_layout_plan: true
  pdf:
    preferred_backend: weasyprint
    fallback_policy:
      chromium: conformant
      wkhtmltopdf: review
      libreoffice: review
      reportlab_text: non_conformant

quality:
  no_silent_content_loss: true
  diagnostics_required_for:
    - unsupported_raw_html
    - missing_assets
    - renderer_fallback
    - classifier_low_confidence
    - layout_overflow_risk
  gates:
    formal_delivery:
      fail_on: [content_loss, missing_required_asset, unrendered_diagram]
      review_on: [low_confidence_table, degraded_pdf_backend, unupdated_toc]
```

## 5. Long-Term Renderer Architecture Recommendations

### 1. Replace Dict AST With Typed Document Model

Use dataclasses or Pydantic models:

- `Document`
- `Section`
- `Heading`
- `Paragraph`
- `Table`
- `TableCell`
- `Figure`
- `Diagram`
- `CodeBlock`
- `RawHtmlBlock`
- inline nodes

This makes unsupported content explicit and prevents renderers from depending on incidental dict shape.

### 2. Add a Semantic Analysis Pass

Produce structured annotations:

```text
TableAnalysis(kind, confidence, columns[], evidence[])
ParagraphAnalysis(kind, confidence, evidence[])
DocumentAnalysis(profile, confidence, evidence[])
AssetAnalysis(resolved_uri, status, mime, dimensions)
```

These should be renderer-independent. Renderers consume annotations, not raw heuristics.

### 3. Add a Layout Planning Pass

Before any renderer writes output, compute:

- page profile;
- content box;
- section orientation decisions;
- table column roles and widths;
- figure/image bounds;
- keep-with-next / page-break policy;
- fallback acceptability.

DOCX polish should become a verifier/normalizer, not the primary place where layout is invented.

### 4. Introduce Renderer Capability Contracts

Each backend should declare capabilities:

```yaml
supports:
  css_paged_media: true
  table_header_repeat: true
  svg_images: partial
  mermaid_runtime: false
  native_footnotes: false
```

The pipeline can then decide whether an output is conformant, review-grade, or fallback-only.

### 5. Externalize Domain Profiles

Keep automotive/chip/manual defaults, but make them named profiles:

- `automotive_formal_spec`
- `chip_register_manual`
- `embedded_api_spec`
- `coding_standard`
- `lightweight_html_doc`

Each profile controls furniture, font set, table taxonomy, page defaults, and quality gates.

### 6. Build Golden Regression and Explainability Tests

Every heuristic should have:

- input examples;
- expected classification;
- expected reason codes;
- expected layout plan;
- expected renderer output assertions.

For example:

```yaml
expected:
  table.kind: register
  confidence: ">=0.90"
  evidence: [header:offset, header:bits, content:access_mode]
  layout.orientation: portrait
```

### 7. Fix Highest-Value Implementation Issues First

Priority order:

1. Preserve mixed image/text paragraphs.
2. Centralize asset resolution and set source base dir everywhere.
3. Make HTML polisher write all mutations.
4. Replace hardcoded page widths with page-profile content-box calculation.
5. Preserve unsupported raw HTML with diagnostics.
6. Keep Word code blocks as code blocks unless explicitly classified as grammar.
7. Add reason codes to table and paragraph classifiers.

## Summary

The current rules are good as an implementation inventory and acceptable as a first-generation domain renderer. They are not yet a stable formal rule system because semantics, style, layout, renderer hacks, and fallback behavior are collapsed together.

The strongest path forward is to promote semantic rules into a renderer-independent model, move formal-document assumptions into profiles, compute layout plans before rendering, and require diagnostics for every heuristic or degradation.
