# TechDoc Engine — Legacy vs V2 Verification Plan

## Purpose

This document defines the systematic plan for verifying that the V2 adapter
pipeline (`Markdown → DocumentModel → SemanticAnalysis → RenderPolicy →
LayoutPlan → RendererAdapter`) produces output at least as correct as the legacy
pipeline (`Markdown → HtmlRenderer → Exporter`), and for identifying exactly
where it does not — at which layer, for which format, with what severity.

This is not a test plan. It is the verification architecture that governs which
tests must exist, which gaps must be closed, and what evidence is required
before any profile+format combination can advance its rollout mode.

---

## 1. Verification Strategy Overview

### 1.1 The Core Premise

The legacy pipeline and V2 pipeline share a common parser (`MarkdownParser` →
dict AST). The divergence begins at the normalization step. This gives us a
natural comparison point:

```
                    Markdown Source
                         │
                         ▼
              ┌── MarkdownParser ──┐
              │                    │
              ▼                    ▼
      Legacy AST              Legacy AST
   (dict, HtmlRenderer)    (dict, core/normalize)
              │                    │
              ▼                    ▼
         body_html           DocumentModel
              │                    │
              ▼                    ▼
       Exporter (per         SemanticAnalysis
       format)                    │
              │                   ▼
              ▼             RenderPolicy
       Output File                │
                                  ▼
                            LayoutPlan
                                  │
                                  ▼
                          RendererAdapter
                                  │
                                  ▼
                            Output File
```

Both paths start from the same AST. Any difference in output can therefore be
attributed to a difference in how the AST is processed downstream.

### 1.2 Verification Dimensions

We verify across five independent dimensions:

| Dimension | What is Compared | Tool |
|---|---|---|
| **Content Preservation** | Does V2 lose any content the legacy path preserves? | `content_loss_checker.py` + AST diff |
| **Semantic Correctness** | Are table types, paragraph roles, headings correctly classified? | Unit tests + golden comparison |
| **Layout Fidelity** | Do tables, figures, code blocks render with correct sizing? | `validation/benchmark.py` + adapter diff |
| **Format Fidelity** | Per-format output (HTML/DOCX/PDF) — structural and visual | Per-format comparison suite |
| **Diagnostics Completeness** | Are all degradations explicitly diagnosed? | Diagnostic audit |

### 1.3 Verification Tiers

| Tier | Scope | Frequency | Gates |
|---|---|---|---|
| **Tier 0 — Unit** | Per-layer correctness | Every commit | pytest must pass |
| **Tier 1 — Golden** | Known input → known output | Every commit | Golden files must match |
| **Tier 2 — Adapter Diff** | Same AST → legacy vs V2 output diff | Pre-merge | No regressions |
| **Tier 3 — Real Document** | Full document rendering | Per-release | Fallback < 1%, degraded < 5% |
| **Tier 4 — Visual** | Pixel-level PDF/image comparison | Per-release (manual) | Human sign-off |

---

## 2. Layer-by-Layer Correctness Verification

### 2.1 Parser Layer (Shared)

**Status:** Both pipelines share `MarkdownParser`. Verification is only needed
to confirm the parser remains untouched.

**Existing Tests:**
- `test_phase1_no_silent_content_loss.py` — 3 tests
- `phase1_regression.py` — AST-level scan of all regression samples

**Required Tests:**
- [x] Mixed text+image paragraph preserves inline structure
- [x] Single-image paragraph retains image node
- [x] Raw HTML block is explicit and diagnosed
- [ ] **GAP:** Nested list preservation (ordered list inside bullet list)
- [ ] **GAP:** Link with mixed inline children (bold+code inside link)
- [ ] **GAP:** Footnote block with equation number preservation
- [ ] **GAP:** HTML entity handling inside code blocks
- [ ] **GAP:** Empty document (no content loss)
- [ ] **GAP:** YAML frontmatter handling

### 2.2 Normalization Layer (AST → DocumentModel)

**Status:** `core/normalize/ast_to_model.py` and `core/normalize/raw_html_normalizer.py`
convert the legacy dict AST to typed `Document` nodes. The reverse bridge
`model_to_ast.py` exists for round-trip verification.

**Existing Tests:**
- `test_phase2_document_model.py` — 7 tests
- `test_raw_html_image_normalization.py` — 5 tests

**Required Tests:**
- [x] Mixed text+image paragraph → Paragraph with TextRun + ImageRun
- [x] Single image → Figure node
- [x] Raw HTML block → RawHtmlBlock with diagnostic
- [x] Table structure → Table with Rows and Cells
- [x] Code block identity → CodeBlock with language
- [x] Mermaid fence → Diagram node with type
- [x] Legacy bridge round-trip keeps core shapes
- [x] Model serialization (`node_to_dict`)
- [x] Raw HTML `<img>` → Figure extraction
- [x] Complex HTML div → RawHtmlBlock + extracted Figures
- [x] Table cell raw HTML images → asset analysis + rendering
- [x] Missing raw HTML image → diagnostic
- [ ] **GAP:** OrderedList → ListBlock with ordered style marker
- [ ] **GAP:** BulletList → ListBlock with bullet style marker
- [ ] **GAP:** Nested list (3 levels) round-trip fidelity
- [ ] **GAP:** BlockQuote containing mixed blocks (paragraph + list + code)
- [ ] **GAP:** Inline HTML `<kbd>`, `<sub>`, `<sup>`, `<mark>` → correct RawInlineHtml or typed node
- [ ] **GAP:** Definition list (from markdown-it deflist plugin) → correct model nodes
- [ ] **GAP:** All 21 node types exercised in round-trip test
- [ ] **GAP:** Model node that has no legacy equivalent → `UnsupportedBlock` with diagnostic

### 2.3 Semantic Analysis Layer

**Status:** 6 analyzers run against the DocumentModel. Results attach to
`document.metadata["semantic_analysis"]`.

**Existing Tests:**
- `test_phase3_semantic_analysis.py` — 9 tests

**Required Tests:**
- [x] Register table classification (explicit marker)
- [x] Bitfield table classification
- [x] Interface table classification
- [x] Generic table fallback + low-confidence diagnostic
- [x] Reliable header detection (2+ non-empty cells)
- [x] Paragraph type detection (note, preserve)
- [x] Document profile detection (chip_register_manual)
- [x] Asset analysis — missing image
- [x] Diagram analysis — mermaid requires static asset
- [ ] **GAP:** All 10 table kinds (revision, register, bitfield, bnf, interface, parameter, error_code, glossary, reference, generic)
- [ ] **GAP:** Table classification from vocabulary signals (not explicit marker)
- [ ] **GAP:** Header "review" status (single non-empty cell)
- [ ] **GAP:** Header "missing" status (no header row)
- [ ] **GAP:** Profile detection for automotive_formal_spec
- [ ] **GAP:** Profile detection for lightweight_tech_note
- [ ] **GAP:** Asset analysis — local_image, data_uri, remote_image, svg, unsupported_format
- [ ] **GAP:** Diagram analysis — plantuml, unknown_diagram
- [ ] **GAP:** Paragraph analysis — compact, caption, warning prefix
- [ ] **GAP:** DocumentProfileAnalyzer: unknown profile when confidence < 0.60
- [ ] **GAP:** Semantic thresholds sourced from render-rules.yaml (currently Python constants only)
- [ ] **GAP:** 5 extended profiles (chip_manual, autosar_spec, api_reference, test_report, requirement_spec) have no auto-detection signals

### 2.4 Render Policy Layer

**Status:** `core/rules/` loads `render-rules.yaml`, resolves profiles, deep-merges
policy areas, and produces a `RenderPolicy`.

**Existing Tests:**
- `test_phase4_render_policy.py` — 7 tests

**Required Tests:**
- [x] YAML loading + schema validation
- [x] Rejection of missing required profiles
- [x] Auto-detection of profile from semantic analysis
- [x] Profile override (document_profile, page_profile)
- [x] Full policy dict structure (8 areas)
- [x] Renderer-specific settings isolated under renderer_policy
- [x] RuleResolver deep-merge with profile overrides
- [ ] **GAP:** Profile inheritance chain resolution (extends mechanism)
- [ ] **GAP:** All 8 profile YAMLs loadable via extends
- [ ] **GAP:** Missing page profile in profile YAML → fallback to default
- [ ] **GAP:** Invalid YAML schema → RuleLoader rejects with specific error
- [ ] **GAP:** Policy override at individual key granularity
- [ ] **GAP:** Feature flag toggles: use_legacy_renderer, enable_html_adapter, enable_docx_adapter, enable_pdf_adapter
- [ ] **GAP:** unsupported_content_policy validation (must be "diagnostic_required")
- [ ] **GAP:** quality_policy threshold validation

### 2.5 Layout Planning Layer

**Status:** `core/layout/planner.py` builds renderer-independent `LayoutPlan`.

**Existing Tests:**
- `test_phase5_layout_planner.py` — 7 tests

**Required Tests:**
- [x] Layout plan attaches to document metadata
- [x] Column roles by table kind (register vs generic)
- [x] Width ratios by column role
- [x] Overflow risk detection for wide tables
- [x] Landscape recommendation for overflow tables
- [x] Missing image placeholder intent
- [x] Code block layout (language, preserve_identity)
- [x] Diagram prerender requirements
- [ ] **GAP:** Section splitting (currently single-section only — test that landscape intent exists)
- [ ] **GAP:** All column role combinations across 10 table kinds
- [ ] **GAP:** Figure layout for local_image, data_uri, svg, missing_asset
- [ ] **GAP:** Page layout with non-A4 page profile
- [ ] **GAP:** Mixed orientation document (portrait + landscape)
- [ ] **GAP:** Layout plan for document with zero tables/images/diagrams
- [ ] **GAP:** Layout plan for document with 50+ tables

### 2.6 Renderer Adapter Layer

**Status:** Three adapters: `HtmlRendererAdapter`, `DocxRendererAdapter`,
`PdfRendererAdapter`. Each consumes `RenderContext` and produces `RenderResult`.

**Existing Tests:**
- `test_phase6_renderer_adapters.py` — 6 tests (integration)
- `test_phase6a_html_adapter_stability.py` — 5 tests (golden)
- `test_phase6b_docx_adapter.py` — 11 tests
- `test_phase6c_docx_table_image_enhancements.py` — 5 tests
- `test_phase6d_docx_document_structure.py` — 10 tests
- `test_phase6e_docx_governance.py` — 6 tests
- `test_phase7_pdf_adapter.py` — 8 tests

See Section 3 for per-format verification details.

---

## 3. Format-by-Format Fidelity Comparison

### 3.1 HTML Output

#### 3.1.1 Architecture Difference

| Aspect | Legacy (`HtmlRenderer` + `HtmlExporter`) | V2 (`HtmlRendererAdapter`) |
|---|---|---|
| Rendering model | AST → inline HTML strings + Jinja2 template | DocumentModel → direct HTML5 string generation |
| Table classification | Inline in HtmlRenderer (own TableClassifier) | From SemanticAnalysis metadata |
| Heading numbering | Inline in HtmlRenderer | Adapter-internal counter (duplicated logic — see 3.1.3) |
| CSS | Jinja2 theme CSS template | Hardcoded inline `<style>` block |
| Raw HTML | Preserved as-is (unescaped) | Preserved or escaped per policy |
| Mermaid | Injected via CDN + init script | `<pre class="mermaid">` + CDN injection |

#### 3.1.2 Verification Items

- [x] **Golden test:** `html_adapter_golden.md` → 15 HTML fragment assertions
- [x] **Diagnostic:** adapter-specific codes (`html_adapter_raw_html_review`, `html_adapter_missing_inline_image_placeholder`)
- [x] **Table kind:** `data-table-kind` attribute present
- [x] **Landscape:** `data-landscape-recommendation` attribute present
- [x] **Missing image:** `class="missing-image"` placeholder
- [x] **Mermaid:** `class="mermaid"` on `<pre>`
- [x] **No reclassification:** Adapter does not classify tables (verified via `patch`)
- [ ] **GAP:** CSS output comparison: legacy Jinja2 theme vs adapter inline `<style>` — pixel-level rendering diff for same content
- [ ] **GAP:** TOC HTML output: legacy generates TOC via `_build_toc_html()`, adapter does not generate TOC HTML (only `<nav>` if configured)
- [ ] **GAP:** Cover page: legacy has `include_cover` mechanism, adapter has no cover support
- [ ] **GAP:** Revision table: legacy detects and renders revision table, adapter emits as standard table
- [ ] **GAP:** Responsive behavior: legacy theme is responsive, adapter CSS is minimal
- [ ] **GAP:** Print CSS: legacy has `@media print`, adapter has none (PDF handled by separate adapter)
- [ ] **GAP:** Math rendering: legacy uses TeX math plugin, adapter preserves MathRun as text
- [ ] **GAP:** Footnote rendering: legacy processes footnotes, adapter does not

#### 3.1.3 Known Layer Violations

- **Heading numbering duplicated:** Both HTML and DOCX adapters implement identical `_heading_number()` counter logic. This should be driven by `RenderPolicy.heading_numbering` policy passed through `LayoutPlan`, not re-implemented per adapter.
- **CSS hardcoded:** `_document_shell()` inlines static CSS. Should use a template or be configurable via policy.
- **Asset status re-query:** `_asset_status_for_src()` searches `semantic_analysis.assets[]` by src string. This data should be in `FigureLayout` directly.

### 3.2 DOCX Output

#### 3.2.1 Architecture Difference

This is the most significant architectural divergence:

| Aspect | Legacy (`WordExporter`) | V2 (`DocxRendererAdapter`) |
|---|---|---|
| Rendering model | AST → HtmlRenderer → HTML → BeautifulSoup → python-docx | DocumentModel → direct python-docx construction |
| Table handling | BS4-parsed HTML table → Word table builder | DocumentModel Table → `table_writer.py` |
| Image handling | BS4-parsed `<img>` → embedded or linked | `image_writer.py` with semantic asset resolution |
| Heading numbering | HtmlRenderer generates numbered text, BS4 strips it, DOCX re-applies | Adapter-internal counter |
| Style system | Template-based (loads .docx template, clears body, keeps styles) | `style_mapper.py` from renderer_policy.docx.adapter_policy |
| Font fallback | Hardcoded: West=Calibri, CJK=Microsoft YaHei, Mono=Consolas | From style mapper configuration |
| Post-processing | `polisher.py` in-place patches (column widths, image scaling, heading breaks, font consistency) | Governance diagnostics + `patch_retirement.py` tracking |

#### 3.2.2 Key Risk: The HTML Round-Trip

The legacy Word path is:
```
AST → HtmlRenderer → HTML string → BeautifulSoup parse → python-docx
```

Every transformation step is a potential fidelity loss point. The V2 adapter
eliminates the HTML intermediate representation entirely:
```
DocumentModel → python-docx
```

This means the V2 adapter must independently achieve all the fidelity that the
legacy path achieved through the HtmlRenderer. The verification plan must catch
every case where the V2 adapter's direct construction falls short of what the
HtmlRenderer produced.

#### 3.2.3 Verification Items

**Table Tests:**
- [x] Simple table structure preservation
- [x] Register table with kind annotation
- [x] Bitfield table with kind annotation
- [x] Interface table with kind annotation
- [x] Generic table (no kind)
- [x] Table header cell color (D9EAF7, E2F0D9, EDE7F6)
- [x] Column width via `w:tcW`
- [x] Wide table overflow risk + landscape recommendation diagnostic
- [x] colspan/rowspan unsupported diagnostic
- [x] No table reclassification in adapter (verified via `patch`)
- [ ] **GAP:** Table with 10+ columns — column width distribution
- [ ] **GAP:** Table with CJK content — character width estimation accuracy
- [ ] **GAP:** Multi-page table — header row repeat behavior
- [ ] **GAP:** Table inside blockquote
- [ ] **GAP:** Nested table (markdown table inside HTML table)
- [ ] **GAP:** Empty cells, merged header rows

**Image Tests:**
- [x] Local PNG insertion (`add_picture`)
- [x] SVG → placeholder + diagnostic
- [x] Missing image → diagnostic
- [x] Inline image in mixed text paragraph
- [x] Image scaling diagnostic (`docx_image_scaling_applied`)
- [ ] **GAP:** Image with explicit width/height attributes in markdown
- [ ] **GAP:** Remote image URL → download + embed, or diagnostic
- [ ] **GAP:** Data URI image → embed
- [ ] **GAP:** Image inside table cell
- [ ] **GAP:** Image with caption (paragraph immediately following)
- [ ] **GAP:** Large image exceeding page width → scaling behavior

**Document Structure Tests:**
- [x] Heading numbering (4 levels: 1, 1.1, 1.1.1, 1.1.1.1)
- [x] Source number stripping via policy
- [x] TOC field insertion + `toc_requires_update` diagnostic
- [x] Revision table detection
- [x] Page setup (A4, margins > 3.0cm)
- [x] Page footer with PAGE field
- [x] Header title from options
- [x] Landscape recommendation diagnostic
- [ ] **GAP:** Multi-section document (portrait + landscape switch — not yet implemented)
- [ ] **GAP:** Cover page generation
- [ ] **GAP:** Different first page header/footer
- [ ] **GAP:** Odd/even page headers
- [ ] **GAP:** Custom page size (US Letter, B5)
- [ ] **GAP:** Revision table rendering quality vs legacy

**Inline Formatting Tests:**
- [x] Bold, italic, code, link (as text)
- [ ] **GAP:** Bold+italic combined (strong + emphasis)
- [ ] **GAP:** Link with inline formatting inside (bold link text)
- [ ] **GAP:** Inline code with backtick-escaped content
- [ ] **GAP:** Strikethrough, highlight, subscript, superscript
- [ ] **GAP:** Line break within paragraph
- [ ] **GAP:** Math inline → MathRun preservation

**Style & Font Tests:**
- [ ] **GAP:** CJK font fallback (Microsoft YaHei) for Chinese text
- [ ] **GAP:** Western font (Calibri) for Latin text
- [ ] **GAP:** Monospace font (Consolas) for code
- [ ] **GAP:** Custom style mapping from renderer_policy
- [ ] **GAP:** Missing style → fallback to Word built-in
- [ ] **GAP:** Font size consistency across document sections

**Edge Case Tests:**
- [ ] **GAP:** Blockquote with nested list
- [ ] **GAP:** Definition list rendering
- [ ] **GAP:** Horizontal rule rendering
- [ ] **GAP:** Page break rendering
- [ ] **GAP:** Very long paragraph (> 10,000 chars)
- [ ] **GAP:** Document with only tables, no text
- [ ] **GAP:** Document with only code blocks
- [ ] **GAP:** Mixed CN/EN in same paragraph

### 3.3 PDF Output

#### 3.3.1 Architecture Difference

| Aspect | Legacy (`PdfExporter`) | V2 (`PdfRendererAdapter`) |
|---|---|---|
| Rendering model | AST → HtmlRenderer → HTML → Jinja2 → PDF via backend | DocumentModel → HtmlRendererAdapter → HTML → PDF via backend |
| Backend chain | WeasyPrint → Chromium → wkhtmltopdf → LibreOffice → ReportLab | WeasyPrint → Chromium → wkhtmltopdf → ReportLab |
| Mermaid | Server-mode pre-rendered images | `degraded_pagination` diagnostic (no pre-render) |
| Base URL | `input_dir` from `convert_file()` | Output file parent directory |
| Sidecar | None | `.pdf.backend.json` recording backend used |

Note: The V2 PDF adapter is essentially a wrapper around the V2 HTML adapter +
a PDF backend. This means all HTML adapter fidelity issues propagate to PDF.

#### 3.3.2 Verification Items

- [x] Backend registry with all 4 backends
- [x] Simple A4 document rendering
- [x] Page break rendering
- [x] Automotive profile rendering
- [x] Wide register table diagnostic
- [x] Mermaid diagnostic (`degraded_pagination`)
- [x] Missing image diagnostic
- [x] SVG diagnostic (`degraded_svg_render`)
- [x] ReportLab-only fallback → non_conformant
- [x] ReportLab backend capability limitations
- [ ] **GAP:** WeasyPrint backend — real end-to-end rendering with actual WeasyPrint installed
- [ ] **GAP:** Chromium backend — real end-to-end with actual Chrome/Chromium installed
- [ ] **GAP:** wkhtmltopdf backend — real end-to-end
- [ ] **GAP:** Backend fallback chain: preferred fails → next backend used
- [ ] **GAP:** Multiple backends installed → correct preferred selected
- [ ] **GAP:** PDF page count verification (not just file size > 0)
- [ ] **GAP:** PDF/A compliance metadata
- [ ] **GAP:** TOC page numbers and hyperlinks in PDF
- [ ] **GAP:** Image DPI/resolution in generated PDF
- [ ] **GAP:** CJK font embedding verification
- [ ] **GAP:** Multi-page table with repeated header (paged media)
- [ ] **GAP:** CSS `@page` rules effect on output
- [ ] **GAP:** PDF file size comparison: legacy vs V2 (same content)

---

## 4. Real Document Benchmark Suite

### 4.1 Current State

The benchmark framework (`core/validation/benchmark.py`) defines a 5-document
corpus. Only 1 document has a real file path:

| Case ID | Profile | Status | Path |
|---|---|---|---|
| `g-c110-flowchart-spec-a0` | `lightweight_tech_note` | Active | Real file exists |
| `chip-manual-seed` | `chip_register_manual` | Placeholder | `TODO/real-corpus/` |
| `autosar-spec-seed` | `automotive_formal_spec` | Placeholder | `TODO/real-corpus/` |
| `api-reference-seed` | `api_reference` | Placeholder | `TODO/real-corpus/` |
| `test-report-seed` | `test_report` | Placeholder | `TODO/real-corpus/` |

### 4.2 Required Corpus Expansion

Per the Engineering Playbook Section 8, the following document types must be
added to the corpus:

| # | Document Type | Profile | Key Characteristics | Priority |
|---|---|---|---|---|
| 1 | Chip manual | `chip_register_manual` | Register tables, memory maps, bit-field diagrams | **P0** |
| 2 | Requirement spec | `automotive_formal_spec` | Numbered requirements, traceability tables | **P0** |
| 3 | AUTOSAR spec | `autosar_spec` | Nested sections, formal notation, large tables | **P1** |
| 4 | Mixed CN/EN | `lightweight_tech_note` | Bidirectional text, mixed paragraphs | **P1** |
| 5 | Table-heavy | varies | 50+ tables, wide tables, merged cells | **P1** |
| 6 | Image-heavy | varies | Screenshots, diagrams, inline images | **P1** |
| 7 | TOC/revision | `automotive_formal_spec` | Long document, revision history | **P2** |
| 8 | API reference | `api_reference` | Function signatures, parameter tables | **P2** |
| 9 | Test report | `test_report` | Test case tables, pass/fail summary | **P2** |

### 4.3 Per-Document Verification Protocol

For each corpus document, all three formats (HTML, DOCX, PDF) must be run and:

1. **Convert:** `Converter.convert_file()` with `pipeline="legacy"` and `pipeline="v2"`
2. **Compare:** Run `FidelityBenchmarkResult` comparison metrics:
   - Layout fidelity: file size ratio (current heuristic → upgrade to structural)
   - Semantic fidelity: diagnostic count and severity
   - Image fidelity: rendered image count vs source reference count
   - Table fidelity: rendered table count vs source table count
   - TOC/revision: presence and correctness
3. **Diagnose:** Any metric that is not "pass"
4. **Record:** Results stored in `validation/reports/{case_id}/` with:
   - Legacy output files (`.html`, `.docx`, `.pdf`)
   - V2 output files (`v2.html`, `v2.docx`, `v2.pdf`)
   - Unified report JSON for V2 runs
   - Benchmark result JSON per format
   - Validation dashboard JSON (aggregate)

### 4.4 Metrics Upgrade Plan

Current metrics are heuristic and coarse. Required upgrades:

| Current | Required |
|---|---|
| File size ratio (±2x = pass) | Structural element count comparison per element type |
| Element count only | Element-level content hash comparison |
| No visual diff | Pixel-level screenshot comparison for HTML/PDF |
| No DOCX structural diff | XML tree diff for DOCX (ignoring RSIDs, timestamps) |
| "review" default for TOC/revision | Actual TOC entry count and revision row count comparison |
| Single-run metrics | Statistical comparison across N runs (for non-deterministic backends) |

---

## 5. Regression Governance

### 5.1 Golden File Registry

Location: `.claude/skills/techdoc-md-renderer/samples/regression/`

| Golden File | Tests | Associated Test |
|---|---|---|
| `no_silent_content_loss.md` | Mixed paragraphs, raw HTML, images, tables, code, Mermaid, wide tables | `test_phase1`, `phase1_regression.py` |
| `html_adapter_golden.md` | 15 HTML fragment assertions | `test_phase6a` |
| `standard_tables.md` | Standard tables, split tables, lists | `phase1_regression.py` |
| `register_table.md` | Register and bitfield tables | `phase1_regression.py` |
| `interface_spec.md` | Interface fields, BNF syntax | `phase1_regression.py` |
| `mixed_cell_content.md` | Table HTML internals (lists, code, breaks, data URIs) | `phase1_regression.py` |
| `short_paragraphs.md` | Short paragraphs, compact grouping | `phase1_regression.py` |

### 5.2 Golden File Update Protocol

1. Document the reason for change.
2. Run all existing tests to confirm no unexpected regressions.
3. Run `phase1_regression.py` against ALL regression samples.
4. Run adapter diff (legacy vs V2) for the changed golden file.
5. If output changes: verify the change is an improvement, not a regression.
6. Commit the golden file update together with the code change.
7. Tag the commit with `[golden]` prefix.

### 5.3 Regression Suite Requirements

**Must add golden files for:**
- [ ] Nested lists (3 levels: ordered inside bullet inside ordered)
- [ ] Links with mixed inline children
- [ ] Blockquote with nested blocks (paragraph + list + code)
- [ ] Definition lists
- [ ] All 10 table kinds
- [ ] CJK in tables
- [ ] Inline HTML elements (kbd, sub, sup, mark, del, ins)
- [ ] Footnotes (if markdown-it-footnote plugin used)
- [ ] Math blocks and inline math
- [ ] 50+ row tables
- [ ] Empty cells, merged header rows

---

## 6. Rollout Readiness Assessment

### 6.1 Current Rollout Matrix (from `core/release/selector.py`)

| Profile | HTML | DOCX | PDF |
|---|---|---|---|
| `lightweight_tech_note` | **v2** | **v2** | legacy_review |
| `chip_register_manual` | **v2** | review | legacy |
| `automotive_formal_spec` | review | legacy | legacy |

### 6.2 Promotion Criteria per Profile+Format

To advance from one rollout mode to the next:

| From → To | Required |
|---|---|
| `legacy` → `legacy_review` | Adapter runs without crashing on 2 real documents of this profile |
| `legacy_review` → `review` | Adapter produces structurally valid output; diagnostics are coherent |
| `review` → `v2` | Real document validation passes; fallback < 1%; degraded < 5%; manual sign-off |
| `v2` → `v2_strict` | 2 consecutive releases with zero critical diagnostics; benchmark passes |

### 6.3 Current Readiness Scores

Based on the existing test suite and validation dashboard:

| Profile | HTML | DOCX | PDF |
|---|---|---|---|
| `lightweight_tech_note` | Ready for v2_strict | Ready for v2 (governed) | Needs backend testing |
| `chip_register_manual` | Ready for v2 | Needs real-doc validation | Needs backend + corpus |
| `automotive_formal_spec` | Needs real-doc validation | Needs adapter completeness | Needs significant work |

### 6.4 Blocking Gaps Before Any Further Promotion

1. **PDF adapter has no real-backend testing.** All PDF tests use ReportLab
   (`non_conformant`). WeasyPrint and Chromium backends are untested in CI.
2. **Only 1 real document in corpus.** Promotion criteria require validation on
   at least 2 real documents per profile. The other 4 corpus entries are
   placeholders.
3. **RolloutSelector is not wired into `render_document()`.** The rollout
   governance defined in `core/release/selector.py` is not called by the
   pipeline entrypoint. Promotion decisions exist in code but are not enforced.
4. **No structural DOCX comparison.** DOCX adapter output is verified through
   coarse metrics (file size ratio, element count) and specific XML attribute
   checks. There is no systematic XML tree diff between legacy and V2 DOCX.
5. **No visual PDF comparison.** PDF output is verified only by file size and
   backend used. There is no pixel-level comparison between legacy and V2 PDF.

---

## 7. Gap Analysis Summary

### 7.1 Critical Gaps (Block rollout)

| ID | Gap | Impact |
|---|---|---|
| C1 | PDF adapter: no real-backend end-to-end tests | Cannot assess PDF fidelity for any profile |
| C2 | Real document corpus: only 1 of 5 entries has content | Cannot meet promotion criteria (need 2+ docs) |
| C3 | RolloutSelector not wired into render_document() | Rollout governance is defined but not enforced |
| C4 | DOCX: no structural XML tree comparison | Cannot detect subtle DOCX regressions |
| C5 | LayoutPlanner: no section splitting | Landscape pages are recommended but not implemented |

### 7.2 High Gaps (Block individual format promotions)

| ID | Gap | Impact |
|---|---|---|
| H1 | DOCX: no inline formatting combination tests (bold+italic, link+bold) | Silent formatting loss in DOCX output |
| H2 | HTML: no CSS parity test (legacy theme vs adapter inline styles) | Visual regression risk for HTML output |
| H3 | PDF: no CJK font embedding verification | Chinese text may not render in PDF |
| H4 | DOCX: table in blockquote, blockquote in list — no tests | Edge case structural loss |
| H5 | HTML: no TOC/cover/revision parity test | Missing document structure in HTML output |
| H6 | 8 YAML profiles exist, only 3 are auto-detectable | Manual override required for 5 profiles |
| H7 | Semantic thresholds duplicated (Python constants + YAML) | Drift risk: YAML says one thing, code does another |

### 7.3 Medium Gaps (Quality and coverage)

| ID | Gap | Impact |
|---|---|---|
| M1 | No nested list golden file | Nested list regression could go undetected |
| M2 | No definition list test coverage | Definition lists silently dropped or mangled |
| M3 | No 50+ row table test | Performance and overflow behavior unknown at scale |
| M4 | No inline HTML (kbd, sub, sup) golden test | Inline HTML handling unverified |
| M5 | No math rendering fidelity test | Math output quality unknown |
| M6 | No footnotes test | Footnote handling unverified |
| M7 | No empty document / edge case tests | Crash risk for unusual inputs |
| M8 | Chapter numbering: adapter duplicates counter logic | Maintainability: fix in one adapter, miss in other |

### 7.4 Low Gaps (Nice to have)

| ID | Gap | Impact |
|---|---|---|
| L1 | No US Letter / B5 page size tests | Non-A4 documents unverified |
| L2 | No odd/even page header tests | Book-style output unverified |
| L3 | No cover page parity test | Cover page rendering differs between legacy and V2 |
| L4 | No performance benchmark for >1000 line documents | Scale characteristics unknown |
| L5 | No right-to-left language test | Internationalization readiness unknown |
| L6 | Plugin system not integrated | Extension points defined but unusable |

---

## 8. Execution Schedule

### Phase A: Close Critical Gaps (Weeks 1-2)

**Goal:** Enable the first PDF promotion and corpus expansion.

1. **Add WeasyPrint end-to-end tests** (C1)
   - Install WeasyPrint in test environment
   - Create 3 PDF golden tests: simple doc, register table, mixed CN/EN
   - Verify: page count, text searchability, image presence

2. **Source 3 real documents for corpus** (C2)
   - Chip manual (register tables, bit-fields): source from user or create synthetic representative
   - Requirement spec: source from user or create synthetic representative
   - Mixed CN/EN technical note: source from user or create synthetic

3. **Wire RolloutSelector into render_document()** (C3)
   - `render_document()` should call `RolloutSelector.select()` before adapter selection
   - Respect `release_mode` parameter
   - Fall back to legacy per selector decision, not just on exception

4. **Add structural DOCX comparison** (C4)
   - Extract XML from DOCX (unzip, read document.xml)
   - Normalize XML (strip RSIDs, timestamps, revision IDs)
   - Compare element-by-element: paragraphs, runs, tables, cells, images
   - Report structural diff as fidelity metric

### Phase B: Close High Gaps (Weeks 3-4)

**Goal:** Enable profile promotions beyond `lightweight_tech_note`.

1. **DOCX inline formatting combination tests** (H1)
2. **HTML legacy vs V2 CSS visual parity assessment** (H2)
3. **CJK font embedding verification for PDF** (H3)
4. **Edge case structural tests** (H4)
5. **HTML document structure parity** (H5)
6. **Auto-detection signals for 5 extended profiles** (H6)
7. **Threshold source unification** (H7): semantic analyzers read from `render-rules.yaml`

### Phase C: Close Medium Gaps (Weeks 5-6)

**Goal:** Comprehensive coverage for all features.

1. Golden files for: nested lists, definition lists, inline HTML, math, footnotes
2. Scale tests: 50-row tables, 100+ paragraph documents
3. Unify heading numbering logic (remove adapter duplication)
4. Empty document / edge case tests

### Phase D: Close Low Gaps (Ongoing)

**Goal:** Production hardening and internationalization.

1. Non-A4 page sizes
2. Book-style headers/footers
3. Cover page parity
4. Performance benchmarks
5. RTL language support evaluation
6. Plugin system integration

---

## 9. Verification Execution Checklist

Before ANY profile+format advances rollout mode, this checklist must be
completed:

### Per-Profile Checklist

```
Profile: ___________________
Format:  ___________________

[ ] Tier 0: All unit tests pass
[ ] Tier 1: Golden tests for this profile's table kinds pass
[ ] Tier 1: Golden tests for this profile's paragraph types pass
[ ] Tier 2: Adapter diff (legacy vs V2) for 3 representative documents
[ ] Tier 2: No silent content loss (content_loss_checker.py clean)
[ ] Tier 3: Real document benchmark for ≥2 corpus documents
[ ] Tier 3: Fallback rate < 1%
[ ] Tier 3: Degraded rate < 5%
[ ] Tier 3: Quality gate score ≥ 90
[ ] Tier 4: Visual inspection (for visually complex documents)
[ ] Tier 4: Manual sign-off on ≥2 real documents
[ ] Rollout matrix updated in core/release/selector.py
[ ] Promotion reason documented in commit message
```

### Per-Format Checklist

```
Format: ___________________

[ ] All existing tests pass without modification
[ ] New regression tests added for any fix
[ ] Golden files updated with documented reason
[ ] Benchmark re-run, no regression
[ ] Adapter diff shows no unexpected structural difference
[ ] All diagnostics are appropriate (no spurious warnings)
[ ] All real fallbacks produce diagnostics (no silent fallback)
[ ] Renderer capability registry accurate
[ ] Feature flag behavior correct (enabled/disabled/auto)
[ ] Legacy fallback works correctly on adapter failure
```

---

## Appendix A: Test File Index

| Test File | Phase | Tests | Status |
|---|---|---|---|
| `test_phase1_no_silent_content_loss.py` | 1 — AST Parsing | 3 | **Complete** |
| `test_phase2_document_model.py` | 2 — Model Conversion | 7 | Needs 6 gaps |
| `test_phase3_semantic_analysis.py` | 3 — Semantic | 9 | Needs 10 gaps |
| `test_phase4_render_policy.py` | 4 — Policy | 7 | Needs 8 gaps |
| `test_phase5_layout_planner.py` | 5 — Layout | 7 | Needs 6 gaps |
| `test_phase6_renderer_adapters.py` | 6 — Adapter Integration | 6 | Needs 3 gaps |
| `test_phase6a_html_adapter_stability.py` | 6a — HTML Golden | 5 | Needs 5 gaps |
| `test_phase6b_docx_adapter.py` | 6b — DOCX Basic | 11 | Needs 8 gaps |
| `test_phase6c_docx_table_image_enhancements.py` | 6c — DOCX Tables/Images | 5 | Needs 4 gaps |
| `test_phase6d_docx_document_structure.py` | 6d — DOCX Structure | 10 | Needs 7 gaps |
| `test_phase6e_docx_governance.py` | 6e — DOCX Governance | 6 | **Complete** |
| `test_phase7_pdf_adapter.py` | 7 — PDF Adapter | 8 | Needs 10 gaps |
| `test_phase8_unified_pipeline.py` | 8 — Unified Pipeline | 5 | Needs 2 gaps |
| `test_phase9_production_hardening.py` | 9 — Hardening | 5 | Needs 2 gaps |
| `test_phase10_release_cutover.py` | 10 — Release Cutover | 8 | Needs 3 gaps |
| `test_phase11_legacy_deletion_review.py` | 11 — Legacy Deletion | 6 | **Complete** |
| `test_phase12_maintenance_pluginization.py` | 12 — Plugins | 5 | Needs 2 gaps |
| `test_raw_html_image_normalization.py` | Raw HTML | 5 | Needs 3 gaps |
| `test_real_document_validation.py` | Real Docs | 3 | Needs 3 gaps |

**Total existing tests: ~111**
**Total identified gaps: ~94**

## Appendix B: Layer Violation Registry

These are the known places where V2 code violates the layer boundary rules
defined in the Engineering Playbook. Each must be tracked to resolution.

| ID | Violation | Location | Severity | Resolution |
|---|---|---|---|---|
| LV1 | Heading numbering duplicated | HTML adapter `_heading_number()`, DOCX adapter `_heading_number()` | Medium | Move to LayoutPlan or RenderPolicy |
| LV2 | CSS hardcoded in adapter | HTML adapter `_document_shell()` | Low | Externalize to template or policy |
| LV3 | Asset status re-queried in renderer | HTML adapter `_asset_status_for_src()`, DOCX `DocxAssetResolver.resolve()` | Medium | Attach to FigureLayout in layout planner |
| LV4 | Source number stripping in adapter | DOCX adapter `_strip_source_number()` | Low | Move to normalization or semantic layer |
| LV5 | Page dimensions hardcoded | DOCX adapter `_apply_page_setup()` | Low | Derive from page_profile policy |
| LV6 | Column width ratios hardcoded | LayoutPlanner `_column_width_ratios()` | Medium | Source from table_policy in render-rules.yaml |
| LV7 | Semantic thresholds hardcoded | `core/semantic/rules.py` (Python constants) | Medium | Read from render-rules.yaml at runtime |
| LV8 | PDF capability diagnostics at runtime | `pdf_adapter.py` `_capability_diagnostics()` | Low | Declare statically in backend_capability.py |
| LV9 | RolloutSelector not wired | `render_document()` does not call selector | High | Integrate into unified.py |
| LV10 | Legacy fallback via import | `unified.py` imports `Converter` from `api` | High | Resolve circular dependency via adapter registry |
| LV11 | Table classification duplicated | `html_engine/renderer.py` has own `TableClassifier` | Medium | Legacy HtmlRenderer should consume SemanticAnalysis (or be retired) |
