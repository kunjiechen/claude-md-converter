# Rule Refactoring Report

This report refactors every rule previously classified as `BAD`, `FRAGILE`, or `CRITICAL TECH DEBT`.

## 1. Custom Dict AST as IR

- Original rule: renderers consume untyped dict nodes with ad hoc keys.
- Problem: unstable contracts, hidden coupling, and no schema validation.
- Better rule: convert parser output into a typed normalized document model.
- Rule type: constraint-based.
- Constraint: every block/inline node has a defined schema and unsupported content is represented explicitly.
- Fallback: unknown parser token becomes `UnsupportedBlock` or `UnsupportedInline` with diagnostic.

## 2. HTML as Canonical IR for All Renderers

- Original rule: Word and PDF derive from semantic HTML.
- Problem: HTML classes carry semantics, styling, and renderer hints at once.
- Better rule: HTML may remain a convenient renderer input, but the canonical IR should be the normalized document model plus layout plan.
- Rule type: policy-based.
- Fallback: during migration, keep HTML intermediate but attach `RenderPolicy` and `LayoutPlan` before renderer execution.

## 3. Generated TOC Replaces Source TOC

- Original rule: detect Chinese `目录` table/paragraph ranges and skip them.
- Problem: locale-specific, pattern-specific, can remove author content incorrectly.
- Better rule: TOC generation is a document-profile policy; source TOC detection only removes content when confidence is high.
- Rule type: policy-based.
- Fallback: preserve source TOC and emit duplicate-TOC warning.

## 4. Always Insert Revision Section

- Original rule: every output gets revision history.
- Problem: formal-company assumption leaks into all documents.
- Better rule: revision history is controlled by document profile.
- Rule type: policy-based.
- Fallback: if required and missing, generate minimal revision section only from available metadata; otherwise warn.

## 5. Table Header Inference Heuristic

- Original rule: text length and content patterns decide whether first row is a header.
- Problem: unstable thresholds and weak explainability.
- Better rule: preserve parser header evidence, run `HeaderAnalysis`, and expose confidence/evidence.
- Rule type: constraint-based.
- Fallback: keep parser header and mark low-confidence review.

## 6. Static Table Width Weights

- Original rule: each table kind has fixed fractional widths.
- Problem: does not scale to page size, font, language, or unusual content.
- Better rule: table kind defines column roles; layout engine computes widths from content box and role constraints.
- Rule type: constraint-based.
- Fallback: approximate metrics when exact metrics are unavailable; emit overflow review if constraints cannot be satisfied.

## 7. Hardcoded Page Widths `9000` and `13200` DXA

- Original rule: portrait and landscape content widths are fixed constants.
- Problem: invalid for other page sizes, margins, templates, and sections.
- Better rule: derive content box from page profile or actual DOCX section geometry.
- Rule type: constraint-based.
- Fallback: if geometry cannot be read, use active page profile default and emit diagnostic.

## 8. Landscape Switch Threshold

- Original rule: switch when `col_count >= 7 and estimated_width > 0.85 * 9000`.
- Problem: hardcoded A4/10pt assumption and column-count bias.
- Better rule: switch after layout planning determines overflow remains after wrapping/compact-font steps.
- Rule type: policy-based.
- Fallback: if landscape is disallowed, keep portrait and emit overflow warning.

## 9. Character Width Estimates

- Original rule: CJK 240 dxa, kana 220, other 120.
- Problem: ignores actual fonts, sizes, bold, code font, and renderer differences.
- Better rule: use font metrics provider; approximation only fallback.
- Rule type: constraint-based.
- Fallback: configured approximate metrics per typography profile.

## 10. DOCX Post-Polish as Primary Layout

- Original rule: DOCX table widths are recomputed after rendering.
- Problem: layout is invented after output, making behavior hard to predict.
- Better rule: compute `LayoutPlan` before rendering and have DOCX adapter apply it.
- Rule type: constraint-based.
- Fallback: keep polisher as validation/repair phase and report repairs as diagnostics.

## 11. HTML Table Wrapper Mutation Bug

- Original rule: HTML polisher wraps tables but may not write the mutation.
- Problem: overflow fix can silently fail.
- Better rule: every mutation returns a dirty patch and is persisted atomically.
- Rule type: constraint-based.
- Fallback: postflight detects missing wrapper and fails/reviews according to profile.

## 12. Manual Word List Prefixes

- Original rule: Word lists use manual bullets/numbers.
- Problem: poor semantics, accessibility, nesting, and editability.
- Better rule: use native Word numbering by default.
- Rule type: policy-based.
- Fallback: manual prefixes only when native numbering fails, with review diagnostic.

## 13. Code Blocks Flattened to Word Paragraphs

- Original rule: Word splits code blocks into `规范` or `正文2` paragraphs.
- Problem: destroys code block identity and harms software documents.
- Better rule: preserve `CodeBlock`; grammar/spec restyle requires explicit marker or high confidence.
- Rule type: policy-based.
- Fallback: if code style is unavailable, use monospace paragraph style while preserving boundaries.

## 14. Code Spec 40% Threshold

- Original rule: if 40% of lines look like spec grammar, entire block becomes `规范`.
- Problem: magic threshold and false positives.
- Better rule: explicit `<!-- code: grammar -->` marker; heuristic can suggest but not force full restyle unless high confidence.
- Rule type: policy-based.
- Fallback: preserve as code and emit suggestion.

## 15. Compact Paragraph Thresholds

- Original rule: CJK <=42, Latin <=90, run length 2-8.
- Problem: useful but arbitrary; can alter author rhythm.
- Better rule: profile-tunable prose compacting with reason codes.
- Rule type: policy-based.
- Fallback: preserve normal paragraphs when confidence is low or profile disables compacting.

## 16. Raw HTML Blocks Ignored

- Original rule: only raw HTML tables/control comments survive.
- Problem: silent content loss.
- Better rule: raw HTML policy: preserve sanitized, text fallback, or reject.
- Rule type: policy-based.
- Fallback: extract visible text and emit unsupported-content diagnostic.

## 17. Image Paragraph Content Loss

- Original rule: paragraph with any image becomes first image node.
- Problem: critical content loss.
- Better rule: preserve images as inline nodes within paragraphs; promote to figure only when paragraph contains a single image and optional caption.
- Rule type: constraint-based.
- Fallback: if renderer cannot inline image, emit placeholder and diagnostic while preserving surrounding text.

## 18. Conflicting Image Max Widths

- Original rule: initial Word max width about 12cm; polish max width 15cm.
- Problem: contradictory phases.
- Better rule: image max width equals content box or configured fraction of content box.
- Rule type: constraint-based.
- Fallback: use page profile content width if actual section geometry is unavailable.

## 19. Relative Image Inlining Path

- Original rule: inlining depends on renderer `_input_dir`, which is not reliably set.
- Problem: relative images may not inline.
- Better rule: central `AssetResolver` with explicit source base dir.
- Rule type: constraint-based.
- Fallback: leave URI unresolved and emit warning; formal delivery fails if asset is required.

## 20. Raw Mermaid Fallback in Word/PDF

- Original rule: prerender failure may leave raw `<pre class="mermaid">`.
- Problem: formal paged output can contain source code instead of diagram.
- Better rule: paged outputs require rendered diagrams for conformant delivery.
- Rule type: policy-based.
- Fallback: placeholder or raw source marked `non_conformant`; quality gate decides review/fail.

## 21. Python Flowchart Painter Constants

- Original rule: fixed node size, spacing, max height.
- Problem: not profile-aware and not scalable to complex diagrams.
- Better rule: diagram style profile controls shape metrics and scaling.
- Rule type: policy-based.
- Fallback: fit-to-content scaling with min readable font size; emit diagram-overflow diagnostic.

## 22. Preflight Mutates Source

- Original rule: pipeline auto-fix can modify Markdown in place.
- Problem: risky for controlled documents.
- Better rule: source fix mode is explicit: `dry_run`, `patch`, or `in_place_with_backup`.
- Rule type: policy-based.
- Fallback: default to patch mode and require explicit opt-in for in-place modification.
