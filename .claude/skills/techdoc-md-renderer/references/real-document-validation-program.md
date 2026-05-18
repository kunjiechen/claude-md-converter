# Real Document Validation Program

This program validates renderer fidelity with real technical documents. It does
not change rollout defaults or delete legacy code.

## Validation Corpus Design

Corpus metadata lives at:

```text
.claude/skills/techdoc-md-renderer/validation/corpus/real-document-corpus.yaml
```

Seed categories:

- chip manuals
- register manuals
- AUTOSAR specs
- API references
- requirement specs
- test reports
- mixed Chinese/English formal documents

Active seed document:

- `g-c110-flowchart-spec-a0`
- source: `/Users/chenkunjie/Downloads/SBPAI/Proj/规范文档/G-C110 流程图编制规范_A0/out/G-C110 流程图编制规范_A0.md`
- profile: `requirement_spec`
- category: mixed Chinese formal spec
- features: TOC, revision table, HTML tables, raw HTML images, numbered headings

Planned corpus entries are listed as TODO paths until real files are added.

## Benchmark Methodology

For each real document and output format:

1. Render with legacy pipeline.
2. Render with V2 pipeline using explicit `pipeline="v2"`.
3. Capture `UnifiedRenderReport` for V2.
4. Extract artifact metrics.
5. Compare:
   - layout fidelity
   - semantic fidelity
   - pagination fidelity
   - image fidelity
   - table fidelity
   - TOC fidelity
   - revision fidelity

Generated reports are written under:

```text
.claude/skills/techdoc-md-renderer/validation/reports/
```

## G-C110 Initial Benchmark

Output report:

```text
.claude/skills/techdoc-md-renderer/validation/reports/g-c110/validation-dashboard.json
```

Updated after Raw HTML Image Normalization Sprint:

| Format | Legacy | V2 | Fallback | Fidelity notes |
| --- | --- | --- | --- | --- |
| HTML | success | success | 0% | tables preserved; raw HTML images normalized; review |
| DOCX | success | success | 0% | tables preserved; raw HTML images now inserted; review |
| PDF | success | success | 0% | backend-readable; table/image/pagination review |

Observed document metrics:

- 701 lines
- 41 headings
- 17 tables
- 49 raw image references
- 116 semantic/model diagnostics

Notable gaps:

- Source contains raw HTML image tags; these are now normalized into ImageRun/Figure semantics.
- HTML V2 image count improved to 45 rendered images.
- DOCX V2 image count improved from 0 to 45.
- TOC fidelity is review because page-synchronized TOC validation is not implemented.
- Revision fidelity is review pending stronger structural comparison.

## Regression Strategy

Every release should run:

- full unit tests
- Phase 1 no-silent-content-loss regression
- real document corpus benchmark
- V2 report validation
- backend-specific PDF checks where backends are available

Each degraded case must record:

- document case id
- profile
- renderer
- backend, if any
- fidelity level
- diagnostics summary
- recommendation

## Quality Dashboard

Dashboard fields:

- renderer pass rate
- fallback rate
- degraded rate
- profile coverage
- remaining legacy dependency
- backend instability
- known fidelity gaps
- rollout recommendation

Initial G-C110 dashboard:

- pass rate: HTML/DOCX/PDF all generated successfully
- fallback rate: 0%
- degraded rate: 0%
- profile coverage: `requirement_spec`
- recommendation:
  - HTML: review before rollout
  - DOCX: review before rollout
  - PDF: keep legacy default

## Renderer Risk Ranking

1. HTML: lowest risk, but raw HTML image handling needs validation.
2. DOCX: medium/high risk for formal specs with raw HTML images, TOC, revision, and pagebreak behavior.
3. PDF: highest rollout risk because fidelity is backend-sensitive and pagination is not deeply validated.

## Default Rollout Recommendation

Based on the first real document only:

- Do not promote `requirement_spec` DOCX/PDF to default V2.
- HTML V2 can remain a candidate, but requires image fidelity remediation or documented acceptance.
- Keep PDF legacy default until backend and pagination history are stable.
- Require at least 10 real documents per target profile before any default switch.

## Acceptance Criteria

Before V2 default rollout for a profile/format:

- at least 10 representative real documents;
- fallback rate below 1%;
- degraded rate below 5%;
- no silent content loss diagnostics;
- table count and key structural metrics match or have approved differences;
- image fidelity is pass or documented review;
- TOC/revision behavior has manual signoff for formal documents;
- PDF backend is pinned or backend variability is documented.
