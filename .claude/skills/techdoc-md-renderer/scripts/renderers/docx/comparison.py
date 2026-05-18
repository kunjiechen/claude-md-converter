"""Structure-level DOCX comparison for legacy-vs-adapter governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from docx import Document as ReadDocx

from diagnostics import make_diagnostic


@dataclass
class DocxMetrics:
    paragraph_count: int
    table_count: int
    image_count: int
    heading_count: int
    pagebreak_count: int
    has_toc_field: bool
    has_visible_toc: bool
    has_revision_table: bool
    text_length: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocxComparisonReport:
    legacy: DocxMetrics
    adapter: DocxMetrics
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    fidelity_classification: str = "review"
    semantic_equivalence: str = "review"
    structure_equivalence: str = "review"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "legacy": self.legacy.to_dict(),
            "adapter": self.adapter.to_dict(),
            "diagnostics": self.diagnostics,
            "fidelity_classification": self.fidelity_classification,
            "semantic_equivalence": self.semantic_equivalence,
            "structure_equivalence": self.structure_equivalence,
        }


def collect_docx_metrics(path: Path) -> DocxMetrics:
    doc = ReadDocx(str(path))
    body_xml = doc._element.body.xml
    text = "\n".join(p.text for p in doc.paragraphs)
    heading_count = sum(1 for p in doc.paragraphs if getattr(p.style, "name", "").startswith("Heading"))
    has_visible_toc = any(
        p.text.strip() == "目录" or getattr(p.style, "name", "").lower().startswith("toc ")
        for p in doc.paragraphs
    )
    has_revision = False
    for table in doc.tables:
        table_text = " ".join(cell.text for row in table.rows for cell in row.cells)
        if "修订" in table_text or "Revision" in table_text or "版次" in table_text:
            has_revision = True
            break
    return DocxMetrics(
        paragraph_count=len(doc.paragraphs),
        table_count=len(doc.tables),
        image_count=len(doc.inline_shapes),
        heading_count=heading_count,
        pagebreak_count=body_xml.count('w:type="page"'),
        has_toc_field="TOC" in body_xml,
        has_visible_toc=has_visible_toc,
        has_revision_table=has_revision,
        text_length=len(text.strip()),
    )


def compare_docx(legacy_path: Path, adapter_path: Path) -> DocxComparisonReport:
    legacy = collect_docx_metrics(legacy_path)
    adapter = collect_docx_metrics(adapter_path)
    diagnostics: List[Dict[str, Any]] = []

    def add(code: str, message: str, evidence: List[str], severity: str = "warning") -> None:
        diagnostics.append(make_diagnostic(
            code,
            message,
            severity=severity,
            category="compatibility",
            fallback="review_docx_adapter_output",
            evidence=evidence,
        ))

    if legacy.table_count != adapter.table_count:
        add("docx_adapter_layout_diff", "Table count differs between legacy and adapter DOCX.", [f"legacy={legacy.table_count}", f"adapter={adapter.table_count}"])
    if legacy.image_count != adapter.image_count:
        add("degraded_image_render", "Image count differs between legacy and adapter DOCX.", [f"legacy={legacy.image_count}", f"adapter={adapter.image_count}"])
    if legacy.heading_count != adapter.heading_count:
        add("docx_adapter_layout_diff", "Heading count differs between legacy and adapter DOCX.", [f"legacy={legacy.heading_count}", f"adapter={adapter.heading_count}"])
    if legacy.pagebreak_count != adapter.pagebreak_count:
        add("docx_adapter_layout_diff", "Page break count differs between legacy and adapter DOCX.", [f"legacy={legacy.pagebreak_count}", f"adapter={adapter.pagebreak_count}"])
    if (legacy.has_toc_field or legacy.has_visible_toc) != (adapter.has_toc_field or adapter.has_visible_toc):
        add("toc_missing", "TOC presence differs between legacy and adapter DOCX.", [f"legacy_field={legacy.has_toc_field}", f"legacy_visible={legacy.has_visible_toc}", f"adapter_field={adapter.has_toc_field}", f"adapter_visible={adapter.has_visible_toc}"])
    if legacy.has_revision_table != adapter.has_revision_table:
        add("docx_adapter_layout_diff", "Revision table presence differs between legacy and adapter DOCX.", [f"legacy={legacy.has_revision_table}", f"adapter={adapter.has_revision_table}"])

    semantic = "equivalent" if adapter.text_length > 0 and legacy.text_length > 0 else "non_conformant"
    structure = "equivalent" if not diagnostics else "review"
    fidelity = "conformant" if not diagnostics else "review"
    if semantic == "non_conformant":
        fidelity = "non_conformant"
    return DocxComparisonReport(
        legacy=legacy,
        adapter=adapter,
        diagnostics=diagnostics,
        fidelity_classification=fidelity,
        semantic_equivalence=semantic,
        structure_equivalence=structure,
    )
