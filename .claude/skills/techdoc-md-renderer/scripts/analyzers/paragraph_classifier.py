"""Paragraph/prose layout analysis.

Markdown cannot distinguish a true paragraph from a visually separated single
sentence exported by Word/PDF. This analyzer keeps source text unchanged while
adding conservative layout hints for renderers and quality reports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional


SHORT_CJK_LIMIT = 42
SHORT_LATIN_LIMIT = 90
COMPACT_MIN_RUN = 2
COMPACT_MAX_RUN = 8


@dataclass
class ParagraphInfo:
    index: int
    kind: str
    length: int
    sentence_count: int
    group: Optional[int] = None
    line: Optional[int] = None
    explicit_policy: str = ""


@dataclass
class ParagraphRun:
    group: int
    start_index: int
    count: int
    total_length: int
    suggested_policy: str = "compact"


@dataclass
class ParagraphIssue:
    severity: str
    category: str
    message: str
    recommendation: str = ""


@dataclass
class ParagraphAnalysis:
    total: int = 0
    short_count: int = 0
    compact_run_count: int = 0
    average_length: float = 0.0
    paragraphs: List[ParagraphInfo] = field(default_factory=list)
    runs: List[ParagraphRun] = field(default_factory=list)
    issues: List[ParagraphIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "short_count": self.short_count,
            "compact_run_count": self.compact_run_count,
            "average_length": self.average_length,
            "paragraphs": [asdict(p) for p in self.paragraphs],
            "runs": [asdict(r) for r in self.runs],
            "issues": [asdict(i) for i in self.issues],
        }


class ParagraphClassifier:
    """Analyze and annotate prose paragraphs in an AST."""

    NOTE_PREFIX = re.compile(r"^(注意|注|例如|示例|参考|说明|备注)[：:]")
    CLAUSE_PREFIX = re.compile(r"^([（(]?[0-9一二三四五六七八九十]+[）).、]|[a-zA-Z][).、])")
    SENTENCE_END = re.compile(r"[。！？；.!?;：:]$")
    CJK_RE = re.compile(r"[\u4e00-\u9fff]")

    @classmethod
    def annotate(cls, ast: List[Dict[str, Any]]) -> ParagraphAnalysis:
        """Annotate paragraph nodes in-place and return a source prose report."""

        analysis = cls.analyze(ast)
        by_index = {p.index: p for p in analysis.paragraphs}
        para_idx = 0
        for node in cls._walk_top_level(ast):
            if node.get("type") != "paragraph":
                continue
            if not cls._plain_text(node):
                continue
            info = by_index.get(para_idx)
            attrs = node.setdefault("attributes", {})
            if info:
                attrs["prose_kind"] = info.kind
                if info.group is not None:
                    attrs["prose_group"] = info.group
            para_idx += 1
        return analysis

    @classmethod
    def analyze(cls, ast: List[Dict[str, Any]]) -> ParagraphAnalysis:
        paragraphs: List[ParagraphInfo] = []
        para_idx = 0
        active_policy = ""
        for node in cls._walk_top_level(ast):
            if node.get("type") == "prose_marker":
                active_policy = "" if node.get("attributes", {}).get("end") else (node.get("content") or "")
                continue
            if node.get("type") != "paragraph":
                active_policy = "" if active_policy not in ("compact", "preserve") else active_policy
                continue
            text = cls._plain_text(node)
            if not text:
                continue
            kind = cls._classify_text(text)
            if active_policy == "compact" and kind == "body":
                kind = "short"
            elif active_policy == "preserve":
                kind = "body"
            paragraphs.append(ParagraphInfo(
                index=para_idx,
                kind=kind,
                length=cls._visual_length(text),
                sentence_count=cls._sentence_count(text),
                explicit_policy=active_policy,
            ))
            para_idx += 1

        cls._mark_compact_runs(paragraphs)
        cls._apply_explicit_groups(paragraphs)
        total_len = sum(p.length for p in paragraphs)
        runs = cls._runs_from_paragraphs(paragraphs)
        issues = cls._issues(paragraphs, runs)
        return ParagraphAnalysis(
            total=len(paragraphs),
            short_count=sum(1 for p in paragraphs if p.kind in ("short", "compact", "note", "clause")),
            compact_run_count=len(runs),
            average_length=round(total_len / len(paragraphs), 1) if paragraphs else 0.0,
            paragraphs=paragraphs,
            runs=runs,
            issues=issues,
        )

    @classmethod
    def _walk_top_level(cls, ast: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Only top-level prose participates in compact grouping. Lists, tables
        # and quotes have their own spacing semantics.
        return ast

    @classmethod
    def _classify_text(cls, text: str) -> str:
        stripped = text.strip()
        if cls.NOTE_PREFIX.match(stripped):
            return "note"
        if cls.CLAUSE_PREFIX.match(stripped) and cls._is_short(stripped):
            return "clause"
        if cls._is_short(stripped):
            return "short"
        return "body"

    @classmethod
    def _mark_compact_runs(cls, paragraphs: List[ParagraphInfo]) -> None:
        group_id = 1
        i = 0
        while i < len(paragraphs):
            p = paragraphs[i]
            if not cls._compact_candidate(p):
                i += 1
                continue
            j = i
            while j < len(paragraphs) and cls._compact_candidate(paragraphs[j]):
                j += 1
            run_len = j - i
            if COMPACT_MIN_RUN <= run_len <= COMPACT_MAX_RUN:
                for item in paragraphs[i:j]:
                    if item.kind == "short":
                        item.kind = "compact"
                    item.group = group_id
                group_id += 1
            elif run_len > COMPACT_MAX_RUN:
                for item in paragraphs[i:j]:
                    item.group = group_id
                group_id += 1
            i = j

    @classmethod
    def _apply_explicit_groups(cls, paragraphs: List[ParagraphInfo]) -> None:
        if not paragraphs:
            return
        next_group = max((p.group or 0 for p in paragraphs), default=0) + 1
        i = 0
        while i < len(paragraphs):
            policy = paragraphs[i].explicit_policy
            if policy != "compact":
                i += 1
                continue
            j = i
            while j < len(paragraphs) and paragraphs[j].explicit_policy == "compact":
                paragraphs[j].kind = "compact" if paragraphs[j].kind == "short" else paragraphs[j].kind
                paragraphs[j].group = next_group
                j += 1
            next_group += 1
            i = j

    @classmethod
    def _compact_candidate(cls, p: ParagraphInfo) -> bool:
        return p.kind in ("short", "note", "clause") and p.sentence_count <= 2

    @classmethod
    def _runs_from_paragraphs(cls, paragraphs: List[ParagraphInfo]) -> List[ParagraphRun]:
        runs: List[ParagraphRun] = []
        seen = set()
        for p in paragraphs:
            if p.group is None or p.group in seen:
                continue
            group_items = [x for x in paragraphs if x.group == p.group]
            seen.add(p.group)
            runs.append(ParagraphRun(
                group=p.group,
                start_index=group_items[0].index,
                count=len(group_items),
                total_length=sum(x.length for x in group_items),
                suggested_policy="compact" if len(group_items) <= COMPACT_MAX_RUN else "review",
            ))
        return runs

    @classmethod
    def _issues(cls, paragraphs: List[ParagraphInfo], runs: List[ParagraphRun]) -> List[ParagraphIssue]:
        issues: List[ParagraphIssue] = []
        long_runs = [r for r in runs if r.count > COMPACT_MAX_RUN]
        if long_runs:
            issues.append(ParagraphIssue(
                severity="warning",
                category="prose",
                message=f"{len(long_runs)} long short-paragraph run(s) may look sparse",
                recommendation="复核是否应改为列表、合并正文，或使用 <!-- prose: compact --> 明确版式。",
            ))
        if paragraphs and (sum(1 for p in paragraphs if p.kind in ("short", "compact")) / len(paragraphs)) >= 0.6 and len(paragraphs) >= 8:
            issues.append(ParagraphIssue(
                severity="warning",
                category="prose",
                message="most prose paragraphs are single-sentence short paragraphs",
                recommendation="短段落占比较高，建议使用紧凑正文策略或在源 Markdown 中合并自然段。",
            ))
        return issues

    @classmethod
    def _plain_text(cls, node: Dict[str, Any]) -> str:
        children = node.get("children") or []
        if not children:
            return re.sub(r"\s+", " ", node.get("content", "") or "").strip()
        parts = []
        for child in children:
            if child.get("type") in ("softbreak", "hardbreak"):
                parts.append(" ")
            else:
                parts.append(child.get("content", "") or "")
        return re.sub(r"\s+", " ", "".join(parts)).strip()

    @classmethod
    def _visual_length(cls, text: str) -> int:
        return len(re.sub(r"\s+", "", text))

    @classmethod
    def _is_short(cls, text: str) -> bool:
        length = cls._visual_length(text)
        if cls.CJK_RE.search(text):
            return length <= SHORT_CJK_LIMIT
        return length <= SHORT_LATIN_LIMIT

    @classmethod
    def _sentence_count(cls, text: str) -> int:
        matches = re.findall(r"[。！？；.!?;]", text)
        return max(1, len(matches))
