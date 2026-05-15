"""Document and table analysis helpers."""

from .table_classifier import (
    TableAnalysis,
    TableLayout,
    TableClassifier,
    classify_table,
)
from .markdown_normalizer import NormalizeIssue, NormalizeReport, normalize_markdown_text
from .paragraph_classifier import (
    ParagraphAnalysis,
    ParagraphClassifier,
    ParagraphInfo,
    ParagraphIssue,
    ParagraphRun,
)
from .document_classifier import DocumentAnalysis, DocumentClassifier
from .artifact_validator import ArtifactIssue, ArtifactValidationReport, ArtifactValidator
from .visual_validator import VisualIssue, VisualValidationReport, VisualValidator
from .quality_gate import QualityGateResult, evaluate_quality_report

__all__ = [
    "TableAnalysis",
    "TableLayout",
    "TableClassifier",
    "classify_table",
    "NormalizeIssue",
    "NormalizeReport",
    "normalize_markdown_text",
    "ParagraphAnalysis",
    "ParagraphClassifier",
    "ParagraphInfo",
    "ParagraphIssue",
    "ParagraphRun",
    "DocumentAnalysis",
    "DocumentClassifier",
    "ArtifactIssue",
    "ArtifactValidationReport",
    "ArtifactValidator",
    "VisualIssue",
    "VisualValidationReport",
    "VisualValidator",
    "QualityGateResult",
    "evaluate_quality_report",
]
