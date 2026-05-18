"""PDF backend registry and selection."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .backend_capability import PdfBackendCapability
from .chromium_backend import ChromiumBackend
from .reportlab_fallback import ReportLabFallbackBackend
from .weasy_backend import WeasyPrintBackend
from .wkhtml_backend import WkhtmltopdfBackend


class PdfBackendRegistry:
    def __init__(self, backends: Optional[Iterable] = None):
        self.backends = {backend.name: backend for backend in (backends or [
            WeasyPrintBackend(),
            ChromiumBackend(),
            WkhtmltopdfBackend(),
            ReportLabFallbackBackend(),
        ])}

    def capabilities(self) -> Dict[str, Dict]:
        return {name: backend.capability.to_dict() for name, backend in self.backends.items()}

    def available(self) -> List[str]:
        return [name for name, backend in self.backends.items() if backend.is_available()]

    def select(self, preferred: str = "weasyprint", fallback_order: Optional[List[str]] = None):
        order = [preferred] + [name for name in (fallback_order or []) if name != preferred]
        for name in order:
            backend = self.backends.get(name)
            if backend and backend.is_available():
                return backend
        return self.backends["reportlab"]


class PdfBackend:
    name = "base"
    capability = PdfBackendCapability(name="base", fidelity_level="non_conformant")

    def is_available(self) -> bool:
        return False

    def render(self, html: str, output_path, *, base_url: str):
        raise NotImplementedError
