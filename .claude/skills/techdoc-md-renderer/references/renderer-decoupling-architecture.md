# Renderer Decoupling Architecture

## Non-Negotiable Gates

V2 must establish `DocumentModel`, `SemanticAnalysis`, `RenderPolicy`, `LayoutPlan`, and `Diagnostics` before renderer rewrites.

Renderers are execution adapters only. They must not classify table kinds, choose document profiles, decide landscape sections, repair image paths, silently drop raw HTML, modify fallback policy, or hardcode business/layout rules.

## 1. Target Pipeline

```text
Markdown
  -> Parser AST
  -> Normalized Document Model
  -> Semantic Analysis
  -> Render Policy
  -> Layout Plan
  -> HTML Renderer
  -> Word Renderer
  -> PDF Renderer
```

The goal is to move decisions out of individual renderers and into explicit, testable phases.

## 2. Parser Responsibilities

Parser owns syntax only:

- tokenize Markdown;
- preserve source order;
- produce parser AST;
- recognize extension markers such as `pagebreak`, `table: kind`, and prose policy comments;
- preserve raw HTML as raw nodes;
- never decide page layout, font, table widths, section orientation, or renderer fallback.

Parser must not:

- drop unknown raw HTML;
- promote image paragraphs destructively;
- classify table kinds;
- decide Word/PDF styles.

## 3. Normalized Document Model Responsibilities

The document model owns semantics:

- typed block and inline nodes;
- normalized tables with rows/cells/spans;
- figures and inline images;
- code blocks with language;
- diagrams with source and diagram type;
- footnotes;
- unsupported content diagnostics.

The document model must be renderer-independent. It can carry annotations but not Word DXA, CSS class names, or PDF backend names.

## 4. Semantic Analysis Responsibilities

Semantic analysis computes:

- document type/profile hints;
- heading structure analysis;
- table classification with confidence and evidence;
- table column role inference;
- paragraph kind and compacting suggestion;
- asset resolution status;
- diagram subtype and render requirements.

Analysis emits diagnostics and reason codes.

## 5. Render Policy Responsibilities

Render policy is loaded from `render-rules.yaml` and selected profiles.

It controls:

- document furniture: TOC, revision, cover, headers/footers;
- typography profile;
- table layout strategy;
- image and asset policy;
- diagram backend policy;
- source auto-fix policy;
- fallback severity;
- quality gate thresholds.

Render policy decides what should happen; renderers decide how to implement it.

## 6. Layout Plan Responsibilities

The layout planner computes renderer-independent layout intent:

- page profile and content box;
- section orientation requirements;
- table column roles and widths as relative/physical constraints;
- figure max bounds;
- keep-with-next/page-break intent;
- overflow risks.

Target-specific adapters translate layout plan into CSS, DOCX OOXML, or PDF backend settings.

## 7. HTML Renderer Responsibilities

HTML renderer owns:

- semantic HTML generation;
- CSS class mapping;
- responsive table wrappers;
- browser-mode Mermaid support;
- data URI asset embedding when policy requests it;
- accessibility attributes where possible.

HTML renderer must not:

- classify tables;
- invent revision history policy;
- calculate DOCX widths;
- silently ignore unsupported nodes.

## 8. Word Renderer Responsibilities

Word renderer owns:

- native DOCX document creation;
- style creation/mapping;
- native headings and bookmarks;
- native or fallback TOC;
- native lists where possible;
- native tables using layout plan;
- images and captions using asset resolver;
- native footnotes;
- section breaks and orientation.

Word renderer should not run semantic classifiers. DOCX polish should become validation/repair, not the primary layout engine.

## 9. PDF Renderer Responsibilities

PDF renderer owns:

- paged output generation;
- backend selection and capability negotiation;
- paged-media CSS or equivalent settings;
- PDF metadata and backend sidecar;
- fidelity classification.

PDF renderer should consume the same render policy and layout plan as other renderers. ReportLab text fallback is readable-only and non-conformant for layout-sensitive delivery.

## 10. Backend Capability Model

Each renderer/backend declares capabilities:

```yaml
capabilities:
  css_paged_media: true
  table_header_repeat: true
  svg_images: partial
  native_footnotes: false
  mermaid_runtime: false
```

The pipeline uses this to decide whether output is conformant, review-grade, or non-conformant.
