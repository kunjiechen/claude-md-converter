"""Shared semantic analysis result structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Evidence:
    code: str
    message: str
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Confidence:
    """Normalized confidence value and review band."""

    value: float
    band: str

    @classmethod
    def from_value(cls, value: float) -> "Confidence":
        if value >= 0.85:
            band = "strong"
        elif value >= 0.70:
            band = "review"
        else:
            band = "low"
        return cls(round(float(value), 3), band)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    kind: str
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    fallback_policy: str = "none"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "confidence": round(float(self.confidence), 3),
            "confidence_detail": Confidence.from_value(self.confidence).to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "diagnostics": self.diagnostics,
            "fallback_policy": self.fallback_policy,
            "attributes": self.attributes,
        }


@dataclass
class SemanticAnalysisReport:
    document_profile: AnalysisResult
    tables: List[AnalysisResult] = field(default_factory=list)
    headers: List[AnalysisResult] = field(default_factory=list)
    paragraphs: List[AnalysisResult] = field(default_factory=list)
    assets: List[AnalysisResult] = field(default_factory=list)
    diagrams: List[AnalysisResult] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_profile": self.document_profile.to_dict(),
            "tables": [item.to_dict() for item in self.tables],
            "headers": [item.to_dict() for item in self.headers],
            "paragraphs": [item.to_dict() for item in self.paragraphs],
            "assets": [item.to_dict() for item in self.assets],
            "diagrams": [item.to_dict() for item in self.diagrams],
            "diagnostics": self.diagnostics,
        }
