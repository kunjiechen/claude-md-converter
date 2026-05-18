# TechDoc Engine Engineering Playbook

The operational methodology for a long-lived document compiler system. This is
not a README and not an architecture doc — it is the field manual for every
engineer who touches this codebase: debugging, adding features, analyzing
fidelity, fixing renderers, extending profiles, governing regression, rolling
out, or retiring legacy code.

---

## 1. System Architecture Principle

```
Markdown
    ↓  [Parser]
DocumentModel      ← Normalization produces standard nodes from raw HTML
    ↓
SemanticAnalysis   ← The only source of semantic truth
    ↓
RenderPolicy       ← The only source of rendering rules
    ↓
LayoutPlan         ← The only source of layout decisions
    ↓
RendererAdapter    ← Consumes the above; invents nothing
    ↓
HTML / DOCX / PDF
```

### Core Principles

| Principle | Meaning |
|---|---|
| **Semantic is the only semantic source** | Table classification, paragraph role, diagram type — all resolved in `core/semantic/`. Renderers must never re-classify. |
| **RenderPolicy is the only rule source** | Page size, column width policy, overflow strategy — all resolved in `core/rules/`. Renderers must never invent rules. |
| **LayoutPlan is the only layout source** | Column widths, page breaks, section flow — all resolved in `core/layout/`. Renderers must never re-layout. |
| **Renderer only executes** | A renderer adapter (in `renderers/`) receives `DocumentModel + RenderPolicy + LayoutPlan` and produces output + diagnostics. It does not analyze, classify, or invent strategy. |
| **All degraded/fallback paths must emit diagnostics** | Every fallback, degradation, or approximation produces a `Diagnostic` via `diagnostics.py`. No silent workaround. |
| **No silent content loss** | `content_loss_checker.py` verifies that every content element either survives into output or produces an explicit diagnostic. |

### Layer Boundaries (Hard)

```
┌──────────────────────────────────────────────┐
│ renderers/  ← consume model/policy/layout     │
│               emit output + diagnostics        │
│               NO analysis, NO rule invention    │
├──────────────────────────────────────────────┤
│ core/layout/  ← consume model + policy        │
│                 produce LayoutPlan             │
├──────────────────────────────────────────────┤
│ core/rules/   ← consume model + profile       │
│                 produce RenderPolicy           │
├──────────────────────────────────────────────┤
│ core/semantic/  ← consume DocumentModel       │
│                   produce semantic annotations │
├──────────────────────────────────────────────┤
│ core/normalize/  ← consume parser AST         │
│                    produce DocumentModel       │
├──────────────────────────────────────────────┤
│ parser.py  ← consume Markdown text            │
│              produce dict AST                  │
└──────────────────────────────────────────────┘
```

Violating a layer boundary creates technical debt that must be tracked in the
legacy audit (`core/governance/legacy_audit.py`).

---

## 2. Problem Diagnosis Method

**Every problem must be located to its pipeline layer before any fix is
attempted.**

### Layer-to-Problem Mapping

| Symptom | First Check |
|---|---|
| Image missing from output | `core/normalize/` — raw HTML image not converted to standard node |
| Image referenced but not found | `core/semantic/asset_analyzer.py` — path resolution |
| Register table misrendered | `core/semantic/table_analyzer.py` — classification wrong |
| Table too wide for page | `core/layout/` — column width policy not applied |
| Word style wrong | `renderers/docx/` — OOXML mapping incorrect |
| PDF page break bad | `renderers/pdf/` — backend paged-media support |
| Raw HTML block vanished | `core/normalize/raw_html_normalizer.py` |
| Heading numbering wrong | `core/semantic/header_analyzer.py` |
| Mermaid diagram broken in PDF | `core/semantic/diagram_analyzer.py` + backend capability |

### Diagnosis Protocol

1. Reproduce the problem on a minimal markdown fragment.
2. Dump the `DocumentModel` at the suspected layer.
3. Dump the `RenderPolicy` if layout-dependent.
4. Dump the `LayoutPlan` if renderer-dependent.
5. Compare legacy output vs V2 output (`phase1_regression.py`).
6. Identify the exact layer where divergence occurs.
7. Fix at that layer — never patch downstream to compensate.

### Forbidden

- **Seeing output anomaly → directly patching a renderer.** This is the most
  common anti-pattern in compiler systems. It works once and breaks everything
  else.
- **Adding `if format == "docx":` inside semantic analysis.** Format-specific
  behavior belongs in the renderer adapter or the RenderPolicy, never in the
  shared pipeline.
- **Silently converting unsupported content.** If a backend cannot render a
  diagram, the fallback must produce a diagnostic, not a hidden substitution.

---

## 3. Fidelity Issue Handling

### Standard Flow

```
Problem discovered (user report / benchmark / golden diff)
    ↓
legacy vs V2 diff  ← phase1_regression.py
    ↓
Locate layer  ← Section 2 diagnosis protocol
    ↓
Root cause analysis
    ↓
Minimum fix at the correct layer
    ↓
Update golden files  ← samples/regression/
    ↓
Benchmark regression  ← core/validation/benchmark.py
    ↓
Rollout judgment  ← core/release/selector.py
```

### Fidelity Levels

Defined in `renderers/base/render_result.py`:

| Level | Meaning | Action |
|---|---|---|
| `pass` | Output matches expectation | None |
| `review` | Acceptable but needs human check | Flag for review |
| `degraded` | Feature degraded, fallback active | Must have diagnostic + fallback reason |
| `non_conformant` | Output is structurally wrong | Must not ship to production |

### Golden File Convention

- Location: `.claude/skills/techdoc-md-renderer/samples/regression/`
- Naming: `{feature}_{scenario}.md`
- Each golden file is a minimal, self-contained markdown fragment that exercises
  exactly one rendering concern.
- Updating a golden requires: (a) documented reason, (b) benchmark re-run,
  (c) code review.

---

## 4. New Feature Process

**Every new feature must be assigned to exactly one pipeline layer before
implementation begins.**

### Feature-to-Layer Classification

| Feature Example | Correct Layer |
|---|---|
| New table kind (e.g. "register map") | `core/semantic/table_analyzer.py` |
| New overflow strategy | `core/rules/policy.py` (table_policy) |
| Landscape section support | `core/layout/planner.py` |
| Word OOXML style mapping | `renderers/docx/` |
| New PDF backend | `renderers/pdf/` |
| New document profile | `core/rules/profile_resolver.py` + config YAML |
| New diagram type | `core/semantic/diagram_analyzer.py` |
| Raw HTML element normalization | `core/normalize/raw_html_normalizer.py` |

### Implementation Checklist

1. Layer assignment documented.
2. Unit test at the assigned layer.
3. Golden test exercising the new feature.
4. Adapter diff (HTML/DOCX/PDF all checked for regressions).
5. Benchmark update.
6. If the feature introduces a new fallback: diagnostic code registered.
7. Profile compatibility verified (not just the default profile).

### Forbidden

- **"New feature → add code to renderer."** A new feature touching the renderer
  should only be wiring — consuming a new field from the model/policy/layout
  that was already produced upstream.
- **Adding a feature that works for HTML but silently degrades for PDF.**
  Cross-format capability must be declared in `core/governance/capabilities.py`.

---

## 5. Raw HTML Handling

### Principle

```
Raw HTML in Markdown
    ↓
core/normalize/raw_html_normalizer.py
    ↓
Standard DocumentModel node (image, table, etc.)
```

Raw HTML is not a renderer concern. It is a normalization concern.

### Rules

- **The normalizer owns all raw HTML interpretation.** Renderers receive only
  standard nodes.
- **If a raw HTML pattern is not recognized,** the normalizer produces a
  `raw_html` node with an attached diagnostic.
- **Renderers must never `BeautifulSoup`-parse raw HTML on their own.**
  The one exception is `renderers/html/` which may preserve raw HTML passthrough
  as a deliberate capability, not as a parsing fallback.

### Forbidden

- `if '<img' in content: do_something_in_renderer()` — this is the canonical
  example of a layer violation that causes silent divergence between formats.

---

## 6. Renderer Development Rules

### What Renderers ARE Allowed to Do

1. Consume `DocumentModel` nodes and emit format-specific output.
2. Consume `RenderPolicy` and apply format-specific styling decisions.
3. Consume `LayoutPlan` and implement layout instructions.
4. Emit `Diagnostic` entries for format-specific limitations.
5. Delegate to backends (`WeasyPrint`, `Chromium`, `python-docx`, etc.).

### What Renderers MUST NOT Do

| Forbidden | Why | Correct Location |
|---|---|---|
| Semantic analysis (classify table type, paragraph role) | Duplicates logic, causes divergence | `core/semantic/` |
| Table classification | Leads to format-specific table handling | `core/semantic/table_analyzer.py` |
| Invent overflow strategy | Each renderer would invent different behavior | `core/rules/policy.py` |
| Silently substitute unsupported features | Violates no-silent-content-loss | Must emit diagnostic |
| Parse raw HTML | Bypasses normalization | `core/normalize/` |
| Decide page size or margins | Duplicates layout logic | `core/layout/` |

### Renderer Adapter Contract

From `renderers/base/renderer_adapter.py`:

```python
class RendererAdapter(ABC):
    def render(self, context: RenderContext) -> RenderResult:
        # context contains: document_model, render_policy, layout_plan,
        #                   diagnostics, assets, options
        # Result contains:  success, output, diagnostics, fidelity_level,
        #                   degradation_reason, fallback_used
```

Every renderer adapter must implement exactly this interface. No additional
responsibilities.

---

## 7. Diagnostics & Fidelity Governance

### Every Output Carries

From `renderers/base/render_result.py`:

```
fidelity_level    ← pass / review / degraded / non_conformant
diagnostics       ← list of Diagnostic
fallback_used     ← bool
degradation_reason ← human-readable string
```

### Diagnostic Severity

| Severity | Meaning |
|---|---|
| `info` | Expected behavior, for traceability |
| `warning` | Acceptable degradation, should be reviewed |
| `critical` | Content loss or structural error, must block release |

### Quality Gate

From `core/pipeline/quality_gate.py`:

- `pass` — fidelity >= review, no critical diagnostics
- `review` — fidelity >= degraded, no critical diagnostics
- `blocked` — critical diagnostics present

A `blocked` quality gate means: do not ship to any production path.

---

## 8. Real Document Validation

### Required Benchmark Documents

The validation suite (`core/validation/benchmark.py`) must cover:

| Document Type | Key Characteristics |
|---|---|
| Chip manual | Register tables, memory maps, bit-field diagrams |
| Requirement spec | Numbered requirements, traceability tables, formal language |
| AUTOSAR spec | Nested sections, formal notation, large tables |
| Mixed CN/EN | Bidirectional text, Chinese headings, mixed paragraphs |
| Table-heavy | 50+ tables, wide tables, merged cells |
| Image-heavy | Screenshots, diagrams, inline images |
| TOC/revision | Long document structure, revision history tables |

### Rollout Gate

Before any format+profile combination moves to `v2_default`:

1. **fallback rate < 1%** — less than 1% of elements use fallback rendering.
2. **degraded rate < 5%** — less than 5% of elements are degraded.
3. **Manual sign-off** on at least 2 real documents from the benchmark suite.
4. **Benchmark run clean** — no regression in any covered format.

---

## 9. Rollout Governance

### Release Modes

From `core/release/selector.py`:

| Mode | Behavior |
|---|---|
| `legacy_only` | V2 pipeline not invoked. Legacy renderer used exclusively. |
| `v2_canary` | V2 pipeline runs in parallel; output compared but legacy output shipped. |
| `v2_default_with_fallback` | V2 pipeline is the default; falls back to legacy on failure. |
| `v2_strict` | V2 pipeline only; failure is a hard error. No legacy fallback. |

### Rollout Dimensions

- **Profile-based:** `lightweight_tech_note` may be `v2_default` while
  `automotive_formal_spec` stays `legacy_only`.
- **Format-based:** HTML may be `v2_strict` while PDF stays
  `v2_default_with_fallback`.
- **Renderer-based:** The HTML adapter may be stable while the DOCX adapter is
  still governed.

### Promotion Criteria

A profile+format combination advances one release mode when:
1. Real document validation passes for that combination.
2. No critical diagnostics for 2 consecutive releases.
3. Rollout matrix in `core/release/selector.py` updated with documented reason.

---

## 10. Legacy Governance

### Principle

**Code removed from the legacy path must have a verified replacement, not just
a hopeful one.**

### Deletion Checklist

From `core/governance/deletion_review.py`:

1. **Replacement exists** — A V2 equivalent covers the same functionality.
2. **Tests exist** — Unit tests for the V2 equivalent pass.
3. **Golden tests match** — Regression golden files pass with the V2 equivalent.
4. **Rollback exists** — Feature flag can revert to the legacy path.
5. **Readiness score sufficient** — `core/pipeline/readiness.py` score meets
   threshold.

### Forbidden

- **Deleting a legacy patch without a V2 equivalent.** "We think the V2
  pipeline handles this" is not sufficient — must be verified.
- **Deleting a legacy function that is still referenced by any active code
  path.**
- **"Cleanup" commits that mix deletion with new features.**

---

## 11. New Profile Process

### What is a Profile

A document profile (e.g., `chip_register_manual`, `automotive_formal_spec`,
`api_reference`) describes the semantic expectations and rendering preferences
for a class of documents. Profiles are resolved in `core/rules/profile_resolver.py`.

### Adding a Profile

1. **Profile config** — YAML in `config/profiles/` defining document structure
   expectations.
2. **Policy extension** — If the profile requires new rendering behavior, add to
   `core/rules/policy_builder.py` (profile-specific policy overrides).
3. **Semantic extension** — If the profile requires new semantic analysis (e.g.,
   "register table" classification for chip manuals), add to
   `core/semantic/` as a profile-gated analyzer.
4. **Rollout matrix** — Add the profile to `core/release/selector.py` with
   initial release mode (typically `legacy_only` or `review`).

### Constraint

**Adding a profile must not modify the core pipeline stages.** Profiles extend
behavior through configuration and policy, not by adding conditionals to the
pipeline.

---

## 12. Backend Governance

### PDF Backends

Managed in `renderers/pdf/`:

| Backend | Fidelity | Degradation | Best For |
|---|---|---|---|
| WeasyPrint | High for CSS paged media | Limited JS, no Mermaid runtime | Formal specs |
| Chromium | Highest overall | Larger output, slower | Complex layouts, Mermaid |
| wkhtmltopdf | Moderate | No flexbox/grid, limited CSS3 | Legacy compatibility |
| ReportLab | Low (programmatic) | Everything is a compromise | Last-resort fallback |

### Backend Selection

Backend selection is a capability decision, not a user preference. The PDF
adapter (`renderers/pdf/pdf_adapter.py`) selects the backend based on:

1. Required capabilities (Mermaid → needs Chromium or pre-rendered image).
2. Available backends (what is installed).
3. RenderPolicy preferences.

### Backend Capability Declaration

From `core/governance/capabilities.py`: each backend declares what it can and
cannot do. The pipeline checks this before dispatching. If no backend supports
a required feature, a diagnostic is emitted and the feature degrades.

---

## 13. Test Governance

### Test Layers

| Layer | What it Tests | Location |
|---|---|---|
| Unit | Individual analyzer/rule/layout function | `scripts/tests/` |
| Golden | Known input → expected output (per feature) | `samples/regression/` |
| Adapter diff | HTML vs DOCX vs PDF consistency | `scripts/tests/test_phase6_renderer_adapters.py` |
| Benchmark | Real document rendering | `core/validation/benchmark.py` |
| Regression corpus | Systematic regression detection | `phase1_regression.py` |

### Rule

**Every fix must include or update at least one test.** If a bug was not caught
by existing tests, the fix must add a test that would have caught it.

### Forbidden

- **Fixing a bug without adding a regression test.**
- **Updating a golden file without documenting why the output changed.**
- **Disabling a test because it's "flaky" without fixing the root cause.**

---

## 14. Common Problem Patterns

### Raw HTML Image Lost

| Wrong Fix | Correct Fix |
|---|---|
| Add `if '<img' in html: extract_src()` in DOCX adapter | Add normalization rule in `core/normalize/raw_html_normalizer.py` to convert `<img>` to standard `image` node |
| Add `if '<img' in html: extract_src()` in PDF adapter | Same normalization fix — one fix, all formats benefit |

### Register Table Misrendered

| Wrong Fix | Correct Fix |
|---|---|
| Add special table handling in each renderer | Add register-table classification in `core/semantic/table_analyzer.py`; renderers consume the classification |

### Wide Table Overflows Page

| Wrong Fix | Correct Fix |
|---|---|
| Add `auto-fit` in DOCX adapter | Add overflow policy in `core/rules/policy.py` (table_policy); `core/layout/planner.py` computes column widths; renderers apply the plan |
| Add `transform: scale` in HTML renderer | Same policy + layout fix |

### Mermaid Diagram Blank in PDF

| Wrong Fix | Correct Fix |
|---|---|
| Add pre-render hack in PDF renderer | `core/semantic/diagram_analyzer.py` flags Mermaid nodes; backend capability check in PDF adapter selects Chromium (supports Mermaid) or degrades with diagnostic |
| Silently replace with placeholder text | Emit diagnostic + degradation_reason |

### CN/EN Mixed Paragraph Spacing Wrong

| Wrong Fix | Correct Fix |
|---|---|
| Add language-detection spacing hack in each renderer | `core/semantic/paragraph_analyzer.py` tags paragraphs with language mix; `core/rules/policy.py` typography_policy defines spacing rules; renderers apply |

---

## 15. Engineering Philosophy

### This is a Compiler, Not a Script Collection

```
TechDoc Engine is a rule-driven document compiler,
not a collection of renderer patches.
```

Every line of code either:
- Advances the model through a pipeline stage, OR
- Converts the model into a format-specific output, OR
- Validates correctness of the above.

If a change does none of these three things, it is either dead code or a patch
that belongs in a different layer.

### Fix Problems at the Highest Correct Layer

```
Symptom appears in output
    → Is the root cause in the renderer? (rarely)
    → Is it in the layout plan?
    → Is it in the policy?
    → Is it in the semantic analysis?
    → Is it in the normalization?
    → Is it in the parser?

Fix at the highest layer where the information needed to make the
correct decision first becomes available.
```

This is the single most important rule in the entire playbook. Internalize it.

### The System Survives on Governance, Not Heroics

Architecture gets you to v1. Governance gets you to v10.

- Diagnostics are not optional — they are the system's memory of its own
  limitations.
- The rollout matrix is not bureaucracy — it is the mechanism that prevents
  regressions from reaching users.
- Legacy audit is not nagging — it is the scoreboard for technical debt
  retirement.
- Golden tests are not busywork — they are the only thing standing between a
  refactor and silent fidelity loss.

### A Patch in a Renderer is a Bug in the Pipeline

Every time you are tempted to add special-case code to a renderer adapter, ask:
"Should this decision have been made earlier?" The answer is almost always yes.
