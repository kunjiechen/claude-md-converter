"""PDF backend capability declarations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class PdfBackendCapability:
    name: str
    fidelity_level: str
    paged_media: bool = False
    css_print: bool = False
    table_repeat_header: bool = False
    basic_svg: bool = False
    browser_quality: bool = False
    readable_fallback: bool = False
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
