"""Real document fidelity validation utilities."""

from .benchmark import (
    FidelityBenchmarkResult,
    RealDocumentCase,
    ValidationDashboard,
    build_quality_dashboard,
    default_real_document_corpus,
    run_validation_case,
    run_validation_corpus,
)

__all__ = [
    "FidelityBenchmarkResult",
    "RealDocumentCase",
    "ValidationDashboard",
    "build_quality_dashboard",
    "default_real_document_corpus",
    "run_validation_case",
    "run_validation_corpus",
]
