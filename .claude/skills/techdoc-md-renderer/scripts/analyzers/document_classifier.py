"""Rule-based document scene classifier.

The classifier is intentionally deterministic. It gives the conversion pipeline
document-level context such as standard specification, API spec, register doc,
or chip manual. The result is used for quality reports today and can later feed
layout defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .table_classifier import TableAnalysis


@dataclass
class DocumentAnalysis:
    document_type: str
    confidence: float
    signals: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class DocumentClassifier:
    """Classify a technical document from headings, text, and table scenes."""

    @classmethod
    def classify(cls, ast: Sequence[dict], table_analyses: Sequence[TableAnalysis]) -> DocumentAnalysis:
        headings = [n.get("content", "") for n in ast if n.get("type") == "heading"]
        text = " ".join(headings + [n.get("content", "") for n in ast if n.get("type") == "paragraph"])
        table_counts: Dict[str, int] = {}
        for analysis in table_analyses:
            table_counts[analysis.kind] = table_counts.get(analysis.kind, 0) + 1

        scores: Dict[str, float] = {
            "standard_spec": 0.0,
            "chip_manual": 0.0,
            "register_doc": 0.0,
            "api_spec": 0.0,
            "coding_standard": 0.0,
            "generic_techdoc": 0.25,
        }
        signals: Dict[str, List[str]] = {k: [] for k in scores}

        def add(kind: str, amount: float, signal: str):
            scores[kind] += amount
            signals[kind].append(signal)

        if any(k in text for k in ("文件修订履历", "修订履历", "适用范围", "支持/相关性文件")):
            add("standard_spec", 0.35, "standard document sections")
        if table_counts.get("revision"):
            add("standard_spec", 0.25, "revision table")
        if any(k in text for k in ("命名规范", "编码规则", "标准函数", "基本规范")):
            add("coding_standard", 0.25, "coding or naming standard wording")
            add("standard_spec", 0.10, "standard wording")

        if table_counts.get("register") or table_counts.get("bitfield"):
            add("register_doc", 0.45, "register or bitfield tables")
            add("chip_manual", 0.25, "hardware table scenes")
        if any(k.lower() in text.lower() for k in ("register", "address", "offset", "bit field", "reset", "access")):
            add("register_doc", 0.25, "register vocabulary")
        if any(k in text for k in ("芯片", "寄存器", "时序", "电气特性", "封装")):
            add("chip_manual", 0.30, "chip manual vocabulary")

        if table_counts.get("interface") or table_counts.get("parameter") or table_counts.get("error_code"):
            add("api_spec", 0.35, "interface/parameter/error-code tables")
        if any(k in text for k in ("接口", "参数", "返回值", "错误码", "函数")):
            add("api_spec", 0.20, "API vocabulary")

        best = max(scores, key=scores.get)
        confidence = min(0.98, max(0.35, scores[best]))
        recommendations = cls._recommend(best, table_counts)
        return DocumentAnalysis(best, round(confidence, 2), signals.get(best, []), recommendations)

    @staticmethod
    def _recommend(document_type: str, table_counts: Dict[str, int]) -> List[str]:
        recs: List[str] = []
        if document_type in ("standard_spec", "coding_standard"):
            recs.append("ensure TOC, revision history, headers, and related-file sections are present")
        if document_type in ("chip_manual", "register_doc"):
            recs.append("prefer explicit table markers for register/bitfield tables when headers are non-standard")
            recs.append("use landscape sections for wide register tables")
        if document_type == "api_spec":
            recs.append("escape interface placeholders such as <Id>/<pp> or mark them as inline code")
        if table_counts.get("generic", 0) > 2:
            recs.append("review generic tables and add explicit <!-- table: ... --> markers if needed")
        return recs
