"""PDF renderer adapter."""

from .pdf_adapter import PdfRendererAdapter
from .backend_registry import PdfBackendRegistry
from .backend_capability import PdfBackendCapability

__all__ = ["PdfBackendCapability", "PdfBackendRegistry", "PdfRendererAdapter"]
