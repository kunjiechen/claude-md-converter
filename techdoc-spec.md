# TechDoc Rendering Specification

Status: formalized target specification based on the current implementation, rule extraction report, and rule quality review. Items marked `planned` are not implemented yet and must not be treated as current behavior.

## 1. Scope

TechDoc renders Markdown technical documents for automotive electronics, embedded systems, chip manuals, register maps, interface specifications, and formal Chinese technical standards.

The target architecture is:

```text
Markdown
  -> Parser AST
  -> Normalized Document Model
  -> Render Policy
  -> HTML Renderer
  -> Word Renderer
  -> PDF Renderer
```

Current implementation note: the project currently uses `markdown-it-py -> dict AST -> semantic HTML -> HTML/DOCX/PDF`. The normalized document model and explicit render policy are planned refactors.

## 2. Core Principles

1. No silent content loss.
2. Semantic rules must be renderer-independent.
3. Layout rules must be constraint-based where possible.
4. Domain conventions must live in named document profiles.
5. Renderer-specific units such as DXA, EMU, CSS px, and Word style names must be adapter concerns.
6. Every heuristic must expose confidence and reason codes.
7. Fallback output must declare fidelity level: `conformant`, `review`, or `non_conformant`.

## 3. Markdown Support Matrix

| Feature | Status | Current Behavior | Target Rule |
|---|---|---|---|
| ATX headings | supported | Parsed into `heading`; manual numeric prefixes stripped during rendering; auto numbering applied except TOC/revision headings. | Heading numbering is controlled by document profile. Source numbering is stripped only when profile enables it. |
| Paragraphs | supported | Paragraphs may contain inline segments, but image paragraphs are promoted to the first image. | Paragraphs preserve all inline children. Mixed image/text is supported or diagnosed by policy. |
| Bold/italic/strikethrough | supported | Inline tokens become HTML and Word runs. | Preserve nested inline semantics in the document model. |
| Highlight `==text==` | supported custom | Regex preprocess outside fenced code. | Implement as a Markdown extension rule or explicit inline normalization step. |
| Underline | partial | Supported through raw inline HTML `<u>`/`<ins>`. | Keep as raw inline semantic `underline`; unsupported forms are preserved as text with warning. |
| Inline code | supported | HTML `code-inline`; Word Courier New shaded run. | Semantic `InlineCode`; renderer maps style. |
| Links | supported | Link text flattened in some cases. Empty links auto-fixed to `#`. | Preserve rich inline link children; empty links emit warning and configurable fix. |
| Images | partial | Block image figure; inline image support is weak; mixed paragraph content can be lost. | Preserve block and inline images through an asset resolver. |
| Pipe tables | supported | Parsed and classified; layout handled by HTML/DOCX builders and polisher. | Table semantic model with column roles and layout plan. |
| Raw HTML table | supported partial | BeautifulSoup extracts rows, cells, colspan, rowspan, and raw cell HTML. | Normalize to typed table model; preserve supported inline/block content. |
| Raw HTML blocks | unsupported current | Non-table blocks are ignored. | Policy: preserve sanitized HTML, text fallback, or reject with diagnostic. |
| Lists | supported | Nested lists; Word uses manual prefixes. | Prefer native list semantics per renderer; manual prefixes only fallback. |
| Task lists | supported custom partial | `[x]`, `[X]`, `[ ]` at list item start. | Normalize to `TaskListItem(checked)`. |
| Blockquotes | supported | Recursive blockquotes; Word indented with left border. | Semantic quote block with renderer-specific styling. |
| Fenced code blocks | supported | HTML code block; Word converts lines to body/spec paragraphs. | Preserve code block identity by default. Grammar/spec rendering requires explicit policy or high-confidence semantic tag. |
| Indented code blocks | supported | Code block without language. | Same as fenced code, with unknown language. |
| Mermaid | supported partial | HTML browser mode; Word/PDF server prerender fallback chain. | Diagram node with required fidelity policy per target. |
| PlantUML | supported partial | CLI/Kroki fallback only. | Diagram node with backend capability contract. |
| Math | partial | texmath parsed; HTML emits delimiters; Word emits italic Cambria Math text, not OMML. | Mark as `planned` for true math rendering. Current output is text fallback. |
| Footnotes | supported partial | HTML footnote list; Word native footnotes. | Semantic footnotes; renderer maps native if available. |
| Definition lists | supported basic | Plain text terms/descriptions. | Preserve inline content; nested blocks planned. |
| Horizontal rule | supported | Styled rule. | Semantic thematic break. |
| Hard page break | supported custom | `<!-- pagebreak -->` becomes pagebreak. | Semantic `PageBreak`; renderer maps target. |
| Manual TOC | supported special | Chinese `目录` table/paragraph range detected and skipped. | Source TOC detection is optional; generated TOC is profile-controlled. |

## 4. Document Structure Rules

Document furniture is profile-driven:

- `automotive_formal_spec`: TOC enabled, revision history required, heading numbering enabled.
- `chip_register_manual`: TOC enabled, register/bitfield table strategy enabled, revision history optional or required by profile.
- `lightweight_tech_note`: TOC automatic, revision disabled by default.

Fallback:

- If required furniture is missing, generate it when enough metadata exists.
- If metadata is insufficient, emit a review diagnostic rather than inventing unverifiable values.

## 5. Table Rules

### 5.1 Semantic Classification

Supported table kinds:

- `revision`
- `register`
- `bitfield`
- `bnf`
- `interface`
- `parameter`
- `error_code`
- `glossary`
- `reference`
- `generic`

Classification inputs:

- explicit marker `<!-- table: kind -->`;
- headers;
- content patterns such as hex addresses, bit ranges, access modes, parameter types;
- surrounding section title, planned;
- document profile.

Rule:

- Explicit marker overrides automatic detection, but conflicting content emits a warning.
- Automatic classification must return `kind`, `confidence`, and `evidence`.
- Low-confidence tables remain `generic` and are reported for review.

### 5.2 Header Detection

Current heuristic header detection is fragile. Target rule:

- Preserve parser-reported header row as evidence.
- Use semantic classifier to validate header likelihood.
- Return `HeaderAnalysis(is_header, confidence, evidence)`.
- Do not drop or reinterpret rows without diagnostics.

Fallback:

- If confidence is low, keep parser header behavior and mark review.

### 5.3 Column Layout

Target table layout is role-based:

- classify columns into roles such as `address`, `bit_range`, `field_name`, `access`, `reset`, `description`, `symbol`, `example`, `type`, `default`.
- roles define alignment, font role, wrap policy, min width, and flex priority.
- actual widths are computed from page content box and measured or estimated text metrics.

Current hardcoded DXA widths are implementation details and must be removed from semantic rules.

Fallback:

- If metrics are unavailable, use configured approximate metrics for the active font profile.
- If still overflowing, apply wrap policy; then compact font; then landscape section if profile allows; then report overflow risk.

## 6. Image Rules

Images are resolved through an asset resolver:

- local paths are relative to the source document directory;
- data URIs are accepted;
- remote images are fetched only when policy permits;
- missing required images fail formal delivery;
- missing optional images emit review diagnostics.

Block image layout:

- maximum width is the available content box;
- aspect ratio is preserved;
- captions are generated from alt/title only when profile enables captions.

Inline image layout:

- preserve in paragraph flow if renderer supports it;
- otherwise substitute a structured placeholder and diagnostic.

Unsupported current behavior:

- robust SVG conversion for Word is not implemented.
- mixed text/image paragraphs are not safely preserved in current code.

## 7. Code Block Rules

Default:

- code blocks remain code blocks in all renderers.
- language info is preserved.
- unknown language is allowed but preflight may warn.

Grammar/spec blocks:

- may use a special style only if explicitly marked or classified with high confidence.
- the current 40% spec-line threshold is not a formal rule; it is a legacy heuristic.

Fallback:

- If Word code-block style is unavailable, use a monospace paragraph style while preserving block boundaries.
- Do not convert code blocks to ordinary body paragraphs unless policy explicitly requests `flatten_code_blocks`.

## 8. Mermaid and Diagram Rules

Diagram detection:

- prefer fenced language (`mermaid`, `plantuml`) when available;
- content detection remains fallback.

HTML:

- Mermaid browser rendering is conformant for HTML output.

Word/PDF:

- diagrams must be prerendered to images for formal delivery.
- raw Mermaid fallback in Word/PDF is `non_conformant` unless profile allows source-code diagrams.

Fallback chain:

1. local deterministic renderer if supported for diagram subtype;
2. configured remote renderer such as Kroki when network is allowed;
3. local CLI such as `mmdc` or `plantuml`;
4. diagnostic placeholder or non-conformant raw source, depending policy.

## 9. Word Rendering Rules

Word renderer responsibilities:

- consume normalized document model and render policy;
- create native DOCX headings, paragraphs, lists, tables, images, footnotes, and sections;
- map semantic styles to Word styles;
- apply layout plan, not invent table layout after rendering.

Profile defaults may map:

- `body` -> `正文2`
- `note` -> `正文3`
- `compact` -> `紧凑正文`
- `grammar` -> `规范`
- `code` -> planned `CodeBlock`

TOC:

- generated only when document profile enables it.
- Word field-based TOC is allowed but must emit a “field update required” warning unless updated by automation.

Revision history:

- generated only when profile requires or source provides it.

Fallback:

- If a requested Word style is unavailable, create it or use a declared fallback style.
- If native numbering is unavailable, manual list prefixes may be used with review diagnostic.

## 10. PDF Rendering Rules

PDF renderer responsibilities:

- render from document model or canonical HTML plus render policy;
- apply paged-media CSS or equivalent backend settings;
- declare backend and fidelity.

Backend fidelity:

- WeasyPrint: conformant target if available and render succeeds.
- Chromium/Edge: conformant or review depending CSS feature use.
- wkhtmltopdf: review due to modern CSS limitations.
- LibreOffice: review due to HTML/CSS fidelity risk.
- ReportLab text fallback: non-conformant for layout delivery; readable fallback only.

Page size and margins:

- derive from page profile.
- A4/2.5cm is the default for `automotive_formal_spec`, not a universal rule.

Fallback:

- If PDF backend downgrades, emit sidecar metadata and quality gate status.

## 11. Unsupported Syntax Rules

Unsupported content must never disappear silently.

Policy options:

- `preserve_sanitized`: keep safe HTML in HTML output; text fallback in Word/PDF.
- `text_fallback`: extract visible text and warn.
- `reject`: fail preflight for formal delivery.

Current unsupported or planned features:

- arbitrary raw HTML block fidelity in Word/PDF: planned;
- true OMML math in Word: planned;
- MathJax/KaTeX HTML injection: planned;
- full Mermaid grammar in native Python renderer: unsupported;
- robust SVG-to-DOCX conversion: planned;
- rich Markdown inside pipe table cells: unsupported unless represented as raw HTML table.

## 12. Error Recovery Rules

Preflight:

- detects missing assets, empty links, wide tables, split tables, Mermaid punctuation, heading gaps, duplicate headings, excessive blank lines.
- source mutation must be controlled by policy: `dry_run`, `patch`, or `in_place_with_backup`.

Postflight:

- checks placeholders, missing HTML images, raw Mermaid in Word/PDF, table overflow risk, PDF too small.

Recovery:

- retry only when the fix is deterministic and reversible.
- renderer fallback must be recorded with fidelity.
- final quality gate decides `pass`, `review`, or `fail`.

## 13. Current Implementation Gaps

The following are target-spec requirements not fully implemented:

- typed normalized document model;
- central asset resolver;
- renderer-independent layout planner;
- reason-code diagnostics for classifiers;
- native Word code block preservation;
- robust mixed inline image preservation;
- configurable document profiles;
- deriving page geometry instead of hardcoded DXA values.
