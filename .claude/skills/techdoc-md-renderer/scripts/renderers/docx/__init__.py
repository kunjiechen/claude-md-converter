"""DOCX renderer adapter skeleton."""

from .docx_adapter import DocxRendererAdapter
from .comparison import compare_docx, collect_docx_metrics
from .readiness import evaluate_docx_adapter_readiness

__all__ = [
    "DocxRendererAdapter",
    "collect_docx_metrics",
    "compare_docx",
    "evaluate_docx_adapter_readiness",
]
