"""Document profile semantic analysis."""

from __future__ import annotations

from typing import Dict, List

from diagnostics import make_diagnostic
from core.model import Document, Heading, Paragraph, Table
from .results import AnalysisResult, Evidence
from .rules import PROFILE_MIN_CONFIDENCE
from .utils import plain_inline_text, walk_blocks


class DocumentProfileAnalyzer:
    PROFILES = {
        "automotive_formal_spec",
        "chip_register_manual",
        "lightweight_tech_note",
        "unknown",
    }

    @classmethod
    def analyze(cls, document: Document, table_results: List[AnalysisResult]) -> AnalysisResult:
        headings = [b.text or plain_inline_text(b.children) for b in walk_blocks(document) if isinstance(b, Heading)]
        paragraphs = [plain_inline_text(b.children) or b.text for b in walk_blocks(document) if isinstance(b, Paragraph)]
        table_counts: Dict[str, int] = {}
        for item in table_results:
            table_counts[item.kind] = table_counts.get(item.kind, 0) + 1
        text = " ".join(headings + paragraphs)
        block_count = sum(1 for _ in walk_blocks(document))
        scores = {
            "automotive_formal_spec": 0.0,
            "chip_register_manual": 0.0,
            "lightweight_tech_note": 0.25,
        }
        signals: Dict[str, List[str]] = {k: [] for k in scores}

        def add(profile: str, amount: float, signal: str) -> None:
            scores[profile] += amount
            signals[profile].append(signal)

        if any(k in text for k in ("修订履历", "修订记录", "适用范围", "参考文件", "术语和缩略语")):
            add("automotive_formal_spec", 0.32, "formal-spec section vocabulary")
        if any(k in text for k in ("命名规范", "模块命名规则", "软件命名", "接口命名", "域定义")):
            add("automotive_formal_spec", 0.28, "formal naming-spec vocabulary")
        if {"目的", "适用范围"}.issubset({h.strip() for h in headings}):
            add("automotive_formal_spec", 0.18, "formal spec opening sections")
        if table_counts.get("revision"):
            add("automotive_formal_spec", 0.25, "revision table")
        if any(k in text for k in ("汽车", "ECU", "CAN", "LIN", "诊断", "AUTOSAR")):
            add("automotive_formal_spec", 0.22, "automotive vocabulary")
        if table_counts.get("register") or table_counts.get("bitfield"):
            add("chip_register_manual", 0.45, "register or bitfield tables")
        if any(k.lower() in text.lower() for k in ("register", "offset", "bit field", "reset", "access")):
            add("chip_register_manual", 0.24, "register vocabulary")
        if any(k in text for k in ("芯片", "寄存器", "位域", "时序", "电气特性")):
            add("chip_register_manual", 0.28, "chip manual vocabulary")
        if block_count <= 12 and not table_counts.get("register") and not table_counts.get("bitfield"):
            add("lightweight_tech_note", 0.20, "short document without hardware tables")

        best = max(scores, key=scores.get)
        confidence = min(0.98, scores[best])
        diagnostics = []
        fallback = "profile_specific_policy"
        if confidence < PROFILE_MIN_CONFIDENCE:
            diagnostics.append(make_diagnostic(
                "low_confidence_document_profile",
                "Document profile confidence is low; profile was downgraded to unknown.",
                severity="warning",
                category="semantic",
                fallback="unknown_profile_review",
                evidence=[f"candidate={best}", f"confidence={confidence}", f"block_count={block_count}"],
            ))
            return AnalysisResult(
                kind="unknown",
                confidence=confidence,
                evidence=[
                    Evidence("candidate_profile", "best profile before downgrade", best),
                    Evidence("signals", "signals for candidate profile", signals.get(best, [])),
                    Evidence("table_counts", "table semantic kinds", table_counts),
                ],
                diagnostics=diagnostics,
                fallback_policy="unknown_profile_review",
                attributes={"block_count": block_count, "heading_count": len(headings)},
            )

        return AnalysisResult(
            kind=best,
            confidence=confidence,
            evidence=[
                Evidence("signals", "profile signals", signals.get(best, [])),
                Evidence("table_counts", "table semantic kinds", table_counts),
                Evidence("heading_count", "heading count", len(headings)),
            ],
            diagnostics=diagnostics,
            fallback_policy=fallback,
            attributes={"block_count": block_count, "heading_count": len(headings)},
        )
