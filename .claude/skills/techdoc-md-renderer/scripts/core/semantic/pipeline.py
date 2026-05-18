"""Semantic analysis pipeline for Phase 3."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.model import Document, Paragraph, Table
from .asset_analyzer import AssetAnalyzer
from .diagram_analyzer import DiagramAnalyzer
from .document_profile_analyzer import DocumentProfileAnalyzer
from .header_analyzer import HeaderAnalyzer
from .paragraph_analyzer import ParagraphAnalyzer
from .results import SemanticAnalysisReport
from .table_analyzer import TableAnalyzer
from .utils import walk_blocks


def analyze_document(document: Document, *, base_path: Optional[Path] = None, attach: bool = True) -> SemanticAnalysisReport:
    """Run semantic analyzers and optionally attach report to document metadata."""

    tables = []
    headers = []
    paragraphs = []
    table_index = 0
    paragraph_index = 0

    for block in walk_blocks(document):
        if isinstance(block, Table):
            tables.append(TableAnalyzer.analyze(block, table_index))
            headers.append(HeaderAnalyzer.analyze(block, table_index))
            table_index += 1
        elif isinstance(block, Paragraph):
            paragraphs.append(ParagraphAnalyzer.analyze(block, paragraph_index))
            paragraph_index += 1

    assets = AssetAnalyzer.analyze(document, base_path=base_path)
    diagrams = DiagramAnalyzer.analyze(document)
    profile = DocumentProfileAnalyzer.analyze(document, tables)
    diagnostics = _collect_model_diagnostics(document)
    for collection in (tables, headers, paragraphs, assets, diagrams, [profile]):
        for result in collection:
            diagnostics.extend(result.diagnostics)

    report = SemanticAnalysisReport(
        document_profile=profile,
        tables=tables,
        headers=headers,
        paragraphs=paragraphs,
        assets=assets,
        diagrams=diagrams,
        diagnostics=diagnostics,
    )
    if attach:
        document.metadata["semantic_analysis"] = report.to_dict()
    return report


def _collect_model_diagnostics(document: Document):
    diagnostics = list(document.diagnostics or [])
    for block in walk_blocks(document):
        diagnostics.extend(getattr(block, "diagnostics", []) or [])
        if isinstance(block, Table):
            for row in block.rows:
                diagnostics.extend(row.diagnostics or [])
                for cell in row.cells:
                    diagnostics.extend(cell.diagnostics or [])
    return diagnostics
