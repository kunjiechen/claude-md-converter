# TechDoc Markdown Renderer Specification

This specification describes the behavior implemented in the current project. It is inferred from the parser, HTML renderer, Word/PDF exporters, analyzers, quality pipeline, styles, and regression samples. It describes actual behavior, including intentional conventions, fallbacks, and current limitations.

## 1. Rendering Pipeline Overview

The renderer uses a shared intermediate representation:

```text
Markdown
  -> normalize_markdown_text()
  -> markdown-it-py tokens
  -> custom dict AST
  -> semantic HTML fragments
  -> HTML / Word / PDF exporters
  -> postflight + polish + quality gate
```

The internal AST is a list of dictionaries. Common node types are `heading`, `paragraph`, `list`, `list_item`, `table`, `table_row`, `table_cell`, `code_block`, `blockquote`, `image`, `hr`, `math_block`, `math_inline`, `definition_list`, `footnote_block`, `pagebreak`, `table_marker`, and `prose_marker`.

HTML is the canonical rendering layer. Word is produced by rendering the AST to semantic HTML, parsing that HTML with BeautifulSoup, then building native DOCX objects with python-docx. PDF is produced from the same HTML and CSS, preferably with WeasyPrint. This is intentional: common semantics are centralized in `HtmlRenderer`, while Word-specific layout is handled after HTML by dedicated builders.

The quality pipeline is:

```text
preflight -> auto_fix -> convert -> postflight -> retry -> polish -> artifact validation -> quality gate
```

Preflight operates on Markdown source. Postflight checks generated artifacts for crash-level defects. Polisher changes outputs in place, mainly DOCX. Quality reports aggregate structural validation and delivery status.

## 2. Markdown Support Matrix

| Feature | Support Level | Implementation | Constraints |
|---|---:|---|---|
| ATX headings `#`-`######` | Full | markdown-it heading tokens -> `heading` AST -> numbered HTML/Word headings | Manual numeric prefixes are stripped before output numbering. `目录` and revision headings are excluded from numbering. |
| Paragraphs | Full | `paragraph` AST with inline segments | Top-level only participates in compact paragraph grouping. |
| Emphasis / strong | Full | inline tokens -> `em` / `strong` HTML -> Word runs | Nested formatting is partially supported; Word applies formatting to the last generated run for nested cases. |
| Strikethrough | Full | markdown-it `strikethrough` enabled -> `<del>` | Word maps to run strike. |
| Highlight `==text==` | Custom | Regex preprocessing to `<mark>text</mark>` outside fenced code | Requires non-space content at both ends. |
| Underline | HTML-only syntax | `<ins>` or `<u>` parsed by inline HTML handler | Markdown native underline is not supported. |
| Inline code | Full | `code_inline` -> `<code class="code-inline">` | Word uses Courier New 10pt with gray shading. |
| Links | Basic | markdown-it links -> `<a href>` / Word hyperlink | Link text formatting inside links is flattened to text/code content. Empty links are auto-fixed to `#` by preflight. |
| Images | Partial | Markdown image paragraph becomes `image` node; inline image becomes `<img class="inline-image">` or placeholder in Word | A paragraph containing any image is reduced to the first image node. Mixed text plus image in normal paragraph is lossy. |
| Tables | Strong | markdown-it tables and raw HTML tables -> table AST -> classified semantic table | Markdown pipe tables and full raw `<table>...</table>` blocks supported. Complex HTML cell content is preserved as `raw_html` for HTML/Word table cells. |
| Raw HTML table | Partial | BeautifulSoup extracts rows/cells, colspan/rowspan/raw_html | Only table blocks are converted. Other block HTML is ignored unless fallback text appears later in Word. |
| Raw inline HTML | Partial | Parses `kbd`, `sub`, `sup`, `mark`, `del`, `ins`, `u`, `em`, `strong`, `code`, `br` | Generic inline HTML is dropped or reduced. Parser is regex-based and fragile for nested/attribute-heavy HTML. |
| Lists | Full | Ordered/unordered lists with nested list nodes | Word uses manual bullets/numbers, not native list fields. Ordered list marker is `1、`. |
| Task lists | Custom partial | Detects `[x]`, `[X]`, `[ ]` at list item start | Not a markdown-it task plugin. Only first paragraph in list item is detected. |
| Blockquotes | Full | Recursive blockquote AST -> HTML blockquote -> Word indented paragraphs | Word adds left border and indent. |
| Fenced code blocks | Full | `fence` -> `code_block` with language info | Word does not preserve a code block container; it converts lines to either `规范` or `正文2`. |
| Indented code blocks | Full | `code_block` -> `code_block` AST, no language | Preflight warns only fenced blocks without language. |
| Mermaid | Strong for flowcharts, partial for other diagrams | FlowchartProcessor detects mermaid keywords. HTML uses browser rendering by default. Word/PDF use server prerender chain. | Python painter only supports `graph`/`flowchart`; sequence/gantt/pie have custom renderer; class/state/journey fall back to Kroki/mmdc or raw `<pre>`. |
| PlantUML | Partial | Detected by `@startuml` / `@startgantt`, rendered via plantuml CLI or Kroki | No native Python renderer. |
| LaTeX math | Partial | `texmath_plugin`; block -> `\[...\]`, inline -> `\(...\)` | No MathJax injection is implemented in HTML. Word renders plain italic Cambria Math text, not real OMML equations. |
| Footnotes | Partial/strong in Word | footnote plugin; Word injects native footnotes | HTML renders footnote list. Some footnote formatting is flattened. |
| Definition lists | Basic | deflist plugin -> `<dl class="definition-list">` | Definitions are plain text only; nested blocks are not preserved. |
| Horizontal rule | Full | `hr` -> styled rule | `<!-- pagebreak -->` is a separate custom control. |
| Hard page break | Custom | `<!-- pagebreak -->` -> `[PAGEBREAK]` -> `pagebreak` AST -> `<hr class="pagebreak">` | Only this exact comment form is recognized. |
| Manual TOC | Special | TOC table or paragraph range is detected and skipped; generated TOC replaces it | Paragraph TOC requires a `目录` paragraph followed by at least 3 `](#...)` link paragraphs. |
| Raw HTML blocks other than table/control comments | Unsupported | ignored by parser | Content may disappear. |

## 3. Table Rendering Rules

Tables are classified before final layout. Explicit markers override detection:

```markdown
<!-- table: register -->
| Offset | Bits | Field | Access | Reset | Description |
```

Supported table kinds are `revision`, `glossary`, `interface`, `bnf`, `register`, `bitfield`, `parameter`, `error_code`, `reference`, and `generic`.

### Header Detection

The HTML renderer does not blindly trust markdown-it's first-row table header. If there are at least two rows, it re-checks whether the first row looks like labels:

- first-row average length must be short enough relative to following row medians;
- first row must not contain data-like characters such as pipes, brackets, angle brackets, pure operators/numbers, or numeric prefixes;
- at least half of non-empty first-row cells must contain word/CJK characters.

This is intentional because converted Word/PDF Markdown often puts data rows before delimiter-looking rows.

### Classification and Widths

All widths are DXA. Portrait content width is `9000`; landscape content width is `13200`.

| Kind | Default Weights | Special Rules |
|---|---|---|
| revision | `0.06, 0.40, 0.14, 0.10, 0.24, 0.06` | Revision table is normalized to six columns: 版次, 修订人, 修订原因, 修订内容, 修订日期, 备注. |
| register | `0.10, 0.11, 0.18, 0.09, 0.10, 0.42` | Code columns 0-4, center columns 0,1,3,4, default 8.5pt. Landscape only if estimated width exceeds 85% of portrait width. |
| bitfield | `0.12, 0.22, 0.10, 0.10, 0.46` | Code columns 0-3, center columns 0,1,3,4, 8.5-9pt depending width. |
| bnf | `0.17, 0.22, 0.34, 0.27` | Code columns 0 and 2; center column 0. |
| interface | `0.24, 0.52, 0.24` | Code columns 1 and 2. |
| parameter | `0.22, 0.14, 0.14, 0.14, 0.36` | Code columns 0 and 1. |
| error_code | `0.14, 0.22, 0.40, 0.24` | Code column 0. |
| glossary | `0.22, 0.78` | Code column 0. |
| reference | `0.16, 0.26, 0.28, 0.30` | Code columns 0 and 1; 7-column wide variants may use landscape and 8.5pt. |
| generic | equal columns | Confidence 0.50. |

When the actual column count differs from the weights, extra columns are inserted before the last wide column at weight `0.12`; fewer columns truncate weights.

### Word Table Rules

Word tables are native DOCX tables:

- `table.autofit = False`.
- Layout type is fixed.
- Default border is single gray `808080`, `w:sz=4` (0.5pt).
- Header fill is `D9D9D9`.
- Cell margins are top/bottom `40` dxa and left/right `60` dxa.
- Cells are vertically centered.
- Header rows are repeated with `w:tblHeader=true`.
- Header text is bold and centered.
- Table paragraphs use zero indent, zero before/after spacing, 240 line height.
- Code columns use Consolas.
- Long code-like cells over 120 characters are visibly wrapped at semantic breakpoints or every 48 characters.
- Colspan and rowspan from raw HTML tables are mapped to `gridSpan` and `vMerge`.
- Images inside table cells are inserted at about 1 inch wide; remote images are cached when `requests` is available.

After conversion, the DOCX polisher recalculates column widths from actual text:

- CJK char width estimate: `240` dxa.
- Japanese kana estimate: `220` dxa.
- Other characters: `120` dxa.
- Minimum column width: `600` dxa.
- Practical width padding ratio: `1.12`.
- Header cells get extra non-wrapping protection with about `180` dxa margin.
- 2-column tables cap any single column at 78% and edge columns at minimum 18%.
- 3-column tables cap any single column at 68% and edge columns at minimum 12%.
- Consecutive tables with the same column count and only empty paragraphs between them are harmonized to aligned column grids.

### HTML/PDF Table Rules

HTML tables use:

- `width: 100%`
- `border-collapse: collapse`
- table font: Microsoft YaHei / 微软雅黑
- font size: 10pt
- border: 0.5px solid `#808080`
- header background: `#D9D9D9`
- padding: `4px 8px`
- data attributes: `data-table-kind` and `data-table-confidence`

PDF print CSS changes table pagination to allow breaks inside large tables:

- table `page-break-inside: auto`
- `thead { display: table-header-group }`
- `tfoot { display: table-footer-group }`
- rows are allowed to break if backend supports it.

The HTML polisher attempts to wrap data/revision tables in `div.table-wrapper`, but the current implementation only writes the file if another HTML modification occurred. This is accidental technical debt.

## 4. PDF Rendering Rules

PDF output is HTML + CSS rendered through a backend chain:

1. WeasyPrint.
2. Chromium/Edge headless print.
3. wkhtmltopdf.
4. LibreOffice HTML to PDF.
5. ReportLab text-only fallback.

PDF page CSS:

- `@page size: A4`
- margin: `2.5cm`
- page number at bottom center, 9pt, body font
- first page has no page number
- body max-width disabled and padding removed
- headings h1-h4 avoid page break after
- cover, TOC, and revision sections force page break after
- explicit pagebreak `<hr class="pagebreak">` becomes a hidden forced page break
- figures, images, flowcharts, and code blocks avoid internal page breaks

PDF uses server-mode diagram rendering. If diagram prerendering fails, raw `<pre class="mermaid">` may enter the PDF HTML. No Mermaid JS is injected for PDF.

The ReportLab fallback is intentionally low fidelity: it extracts text from headings, paragraphs, list items, and table cells, uses A4, STSong-Light for Chinese, 10pt body text, and does not preserve table geometry, images, CSS, or diagrams. A `.pdf.backend.json` sidecar records backend, degradation status, and warnings.

## 5. Word Rendering Rules

Word export also goes through HTML. It uses a DOCX template if found:

1. explicit `template` option;
2. first `.docx` in `templates/`;
3. built-in `default_template.docx`.

When a template is used, body content is cleared but styles, page setup, headers, and the first template table are preserved. Header placeholders for department, document number, version, company, title, and dates are replaced.

### Section Furniture

Word always inserts:

- a native TOC field at the beginning;
- TOC instruction: `TOC \o "1-2" \h \z \u`;
- `updateFields=true` so Word updates fields on open;
- a page break after the TOC;
- a revision section after TOC and before body;
- a page break after the revision section.

If the Markdown has a revision table, it is normalized and rendered. If not, a default revision table is generated, with one row only when version or date exists. If a template has a revision table and Markdown has no revision table, the template table is reused.

### Styles

Custom paragraph styles are created if missing:

| Style | Rule |
|---|---|
| 正文2 | default body style, inherits Normal |
| 正文3 | note/auxiliary text, first-line indent 0.74cm |
| 短正文 | short single-sentence body, 3pt after, 1.15 line spacing |
| 紧凑正文 | compact prose group, 2pt after, 1.1 line spacing |
| 小标题 | bold paragraph subheading |
| 规范 | Consolas 10.5pt, first-line indent 0.74cm |
| 公式 | bold, centered |

Paragraph classification priority:

1. formula pattern;
2. short single-`strong` paragraph -> `小标题`;
3. technical naming pattern with angle placeholders and underscores -> `规范`;
4. note prefixes `注意`, `注`, `例如`, `示例`, `参考`, `说明` under 120 chars -> `正文3`;
5. paragraph classes from prose analyzer override to `短正文` / `紧凑正文`;
6. default `正文2`.

Code blocks are not rendered as shaded blocks in Word. They are split into lines. If at least 40% of non-empty lines look like naming/spec grammar, all lines use `规范`; otherwise each line is classified as `规范` or `正文2`.

Lists use manual prefixes rather than Word numbering:

- unordered levels cycle through `●`, `◆`, `■`, `▸`;
- ordered lists use `1、`, `2、`;
- task items use `☑` or `☐`;
- left indent is `0.85cm + level * 0.65cm`;
- first-line hanging indent is `-0.6cm`;
- spacing before/after is 0.

Word post-polish:

- removes heading `pageBreakBefore` from styles and paragraphs;
- adds `keepNext` and `keepLines` to heading levels 1-3;
- limits images to 15cm wide;
- fills missing CJK/western run fonts;
- cleans trailing empty paragraphs.

## 6. Image Rendering Rules

HTML image blocks render as:

```html
<figure class="image">
  <img src="..." alt="...">
  <figcaption>alt text</figcaption>
</figure>
```

Images are centered and constrained to `max-width: 100%; height: auto`. Figures avoid page breaks.

Word image rules:

- block images are centered;
- data URI images are decoded to temp files;
- local files are used if path exists;
- HTTP(S) images are passed directly to python-docx after a best-effort size probe;
- physical size is computed from image DPI with a fallback of 96 DPI;
- initial maximum width is about 12cm (`12 * 360000` EMU);
- post-polish maximum width is 15cm;
- captions are centered as `图 {caption_text}`, 9pt gray;
- missing images are represented as italic `[图片: ...]`, which postflight treats as critical placeholder residue.

HTML exporter has `inline_images=True`; local images become data URIs. Remote and existing data URIs remain unchanged. Inline image resolution uses `_input_dir`, but the current code does not set `_renderer._input_dir` in the HTML exporter, so relative image inlining may fail unless the process cwd matches the image path. This is accidental.

SVG is not specially converted. HTML can reference or inline SVG as an image. Word relies on python-docx support and may fail or degrade to a placeholder.

## 7. Mermaid and Diagram Handling Rules

Diagram detection is content-based, not language-fence-based. Any code block containing these Mermaid markers is treated as a diagram: `graph`, `flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram`, `gantt`, `pie`, `journey`. PlantUML is detected by `@startuml` or `@startgantt`.

HTML export default mode is `browser` when `mermaid_render_mode=auto`. It outputs:

```html
<pre class="mermaid">...</pre>
```

and injects Mermaid CDN/init scripts.

Word and PDF default to server rendering. The fallback chain is:

1. Python Pillow renderer for Mermaid `graph`/`flowchart`;
2. Python non-flowchart renderer for sequence/gantt/pie;
3. Kroki API only if `use_kroki=True`;
4. local `mmdc` for Mermaid or local `plantuml` for PlantUML;
5. raw `<pre class="mermaid">` fallback.

Mermaid preflight fixes Chinese punctuation that commonly breaks parsing:

- `“”` -> `"`
- `：` -> `:`
- `；` -> `;` for sequence diagrams
- `（）` -> `()`

The built-in Python flowchart painter follows a G-C110-like black-and-white style, uses KaTi/HeiTi fallback fonts, white fill, black lines, minimum node size 120x50, padding 20, horizontal spacing 60, vertical spacing 50, and scales diagrams down to about 300px max height. It only understands a subset of Mermaid flowchart syntax.

## 8. AI Formatting Rules

No active LLM call exists in the implementation. “AI formatting” is currently deterministic heuristic formatting:

- table kind detection from headers/content;
- explicit table marker override;
- document type inference from headings and table kinds;
- low-confidence table suggestion layer with a future provider interface;
- compact prose grouping based on paragraph length and run length;
- technical naming/spec pattern detection for Word `规范` style;
- automatic TOC and revision section generation;
- automatic landscape sections for genuinely wide register/bitfield/reference tables;
- auto retry when postflight critical issues can be fixed from source;
- output polishing of table widths, image size, fonts, spacing, and heading pagination.

Accidental/fragile parts:

- the `suggester` module is heuristic only; comments mention AI as future extension;
- some HTML polisher changes are counted but not written unless other modifications set `modified=True`;
- table and paragraph heuristics are tuned for current regression cases, not formally proven.

## 9. Unsupported Features and Rendering Risks

Unsupported or unstable:

- arbitrary raw HTML blocks except full `<table>` blocks and control comments;
- nested complex Markdown inside table cells unless supplied as raw HTML table cell content;
- true mathematical equation rendering in Word/PDF;
- MathJax/KaTeX script injection for HTML math;
- full Mermaid grammar in the Python renderer;
- SVG-to-DOCX robust conversion;
- multi-image paragraphs and mixed text-image paragraphs;
- preserving rich formatting inside link text;
- CommonMark edge cases around nested inline HTML;
- native Word list numbering for regular lists;
- updating Word TOC page numbers without opening/updating fields in Word;
- robust responsive table wrappers in HTML due to current polisher write bug.

Operational risks:

- PDF output quality depends heavily on available backend.
- ReportLab fallback is readable but not layout equivalent.
- Remote images and Kroki require network.
- mmdc/PlantUML require local CLI installation.
- Word template headings may interact with generated numbering and field updates.
- Default revision section appears even when the source had no revision section, which is intentional for formal company documents but may surprise lightweight documentation users.

## 10. Technical Debt Analysis

| Area | Risk | Intentional or Accidental |
|---|---|---|
| HTML as IR | Good architectural choice, but Word fidelity requires many post-HTML special cases | Intentional |
| Dict AST | Lightweight but weakly typed and hard to validate | Technical debt |
| Inline HTML parsing | Regex-based, fragile for nesting/attributes | Technical debt |
| Image paragraph handling | Any paragraph with an image becomes only the first image | Accidental limitation |
| HTML polisher write flag | Wide table wrappers may not persist | Bug |
| HTML image inlining path | `_input_dir` not reliably set in renderer | Bug |
| Word code block rendering | Loses visual code block container | Intentional for spec grammar documents, limiting for software docs |
| Word list rendering | Manual bullets are stable visually but not semantically native | Intentional workaround |
| PDF fallback chain | Robust delivery but inconsistent fidelity | Intentional |
| TOC handling | Word TOC field requires user/application update | Known limitation |
| Revision auto-generation | Formal-doc convention baked into all formats | Intentional domain assumption |
| Table classifier thresholds | Hardcoded and domain-specific | Intentional but should be externalized |
| Flowchart output dir | Server-rendered diagrams write into `output/flowchart_N.png` | Technical debt / side effect |

## 11. Industry-Specific Document Conventions

The renderer is optimized for formal Chinese technical documentation in automotive electronics, embedded systems, chip manuals, and software interface specifications:

- G-C045-style formal document theme: black-and-white, Chinese office fonts, A4 margins, TOC, revision history.
- G-C110-like flowchart rendering: simple black/white standardized shapes.
- Revision履历 is treated as required document furniture.
- Register/bitfield tables receive special compact/landscape layout.
- BNF/interface/parameter/error-code tables receive code-column treatment.
- Technical placeholders such as `<module>` are considered semantic content and preflight warns when they may be parsed as HTML.
- Short single-sentence prose from converted office documents is compacted to avoid sparse Word/PDF output.

## 12. Hidden Assumptions and Implicit Constraints

- A4 portrait with 2.5cm margins is the baseline page model.
- Portrait content width is approximated as 9000 dxa; landscape as 13200 dxa.
- Chinese/CJK documents are the primary target.
- HTML output is self-contained in CSS, but Mermaid browser rendering uses CDN unless server mode is requested.
- DOCX output is the most polished target; HTML/PDF share CSS but receive less post-processing.
- Every formal document should have TOC and revision history.
- Heading numbering is generated from source heading hierarchy, not from source numbering text.
- h1-h3 are enough for HTML TOC; Word TOC is only h1-h2 by default.
- Tables wider than six columns are risky, but landscape is only selected after width estimation.
- Preflight may modify source files in place when auto-fix is used.

## 13. Recommended Formal Specification

The companion `render-rules.yaml` in this repository encodes these implemented rules for future tests, documentation, and conformance checks.
