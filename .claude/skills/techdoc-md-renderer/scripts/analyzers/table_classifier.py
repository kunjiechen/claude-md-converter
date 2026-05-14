"""Rule-based table scene classifier and layout advisor.

The converter keeps HTML as the shared rendering layer, but tables need
Word-native layout decisions. This module provides a deterministic first pass:
it classifies common technical-document tables and returns a layout hint that
Word/PDF/HTML exporters can consume. AI assistance can be layered on top later
for low-confidence cases without making the baseline conversion nondeterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, List, Optional, Sequence


CONTENT_WIDTH_DXA = 9000
LANDSCAPE_CONTENT_WIDTH_DXA = 13200


@dataclass
class TableLayout:
    """Layout hints for a classified table."""

    widths: List[int] = field(default_factory=list)
    repeat_header: bool = True
    fixed_layout: bool = True
    landscape: bool = False
    font_size_pt: Optional[float] = None
    code_columns: List[int] = field(default_factory=list)
    center_columns: List[int] = field(default_factory=list)
    total_width_dxa: int = CONTENT_WIDTH_DXA


@dataclass
class TableAnalysis:
    """Table classification result."""

    kind: str
    confidence: float
    layout: TableLayout
    issues: List[str] = field(default_factory=list)


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&lt;|<", "<", text)
    text = re.sub(r"&gt;|>", ">", text)
    text = re.sub(r"[\s_/\\\-]+", "", text)
    return text


def _visible(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _scale_widths(weights: Sequence[float], total: int = CONTENT_WIDTH_DXA) -> List[int]:
    if not weights:
        return []
    s = sum(weights)
    if s <= 0:
        return [total // len(weights)] * len(weights)
    widths = [max(500, int(total * w / s)) for w in weights]
    diff = total - sum(widths)
    widths[-1] += diff
    return widths


class TableClassifier:
    """Classify technical-document table scenes using deterministic rules."""

    REVISION = {"版次", "修订内容", "修订日期", "修订人", "备注", "version", "date"}
    GLOSSARY = {"定义与缩写", "定义", "缩写", "描述", "术语", "description"}
    INTERFACE = {"元素名字字段", "元素名称", "字段", "示例", "基本结构", "描述"}
    BNF = {"symbol", "meaning", "example", "explanation"}
    REGISTER = {"address", "addr", "offset", "register", "reg", "bits", "bit", "field", "access", "reset", "description"}
    BITFIELD = {"bits", "bit", "field", "name", "access", "reset", "description"}
    PARAMETER = {"name", "parameter", "参数", "type", "类型", "range", "范围", "default", "默认值", "description", "描述"}
    ERROR_CODE = {"code", "error", "错误码", "name", "meaning", "action", "处理", "description"}

    @classmethod
    def classify(cls, rows: Sequence[Sequence[str]], explicit_kind: Optional[str] = None) -> TableAnalysis:
        rows = [list(r) for r in rows if any(_visible(c) for c in r)]
        if not rows:
            return cls._generic(0)

        col_count = max(len(r) for r in rows)
        header = cls._header(rows)
        header_norm = [_norm(c) for c in header]
        all_text = " ".join(_visible(c) for r in rows[:8] for c in r)
        issues: List[str] = []

        if col_count > 6:
            issues.append(f"{col_count} columns; consider landscape or compact table style")
        if any(len(_visible(c)) > 160 for r in rows for c in r):
            issues.append("contains very long cells; preserve line breaks and fixed widths")

        if explicit_kind:
            explicit = cls._explicit_result(explicit_kind, col_count, issues)
            if explicit:
                if explicit.kind in ('register', 'bitfield', 'reference'):
                    landscape, fs = cls._wide_table_layout(rows, col_count)
                    explicit.layout.landscape = landscape
                    if fs and not explicit.layout.font_size_pt:
                        explicit.layout.font_size_pt = fs
                return explicit

        # Strong header-based classifications.
        if cls._hits(header_norm, cls.REVISION) >= 3 or cls._looks_revision(rows):
            return cls._result("revision", 0.95, col_count, [0.06, 0.40, 0.14, 0.10, 0.24, 0.06], issues)
        if cls._hits(header_norm, cls.REGISTER) >= 4 or cls._looks_register(rows):
            landscape, fs = cls._wide_table_layout(rows, col_count)
            return cls._result("register", 0.92, col_count, [0.10, 0.11, 0.18, 0.09, 0.10, 0.42], issues,
                               landscape=landscape, font_size=fs or 8.5, code_cols=[0, 1, 2, 3, 4])
        if cls._hits(header_norm, cls.BITFIELD) >= 4 or cls._looks_bitfield(rows):
            landscape, fs = cls._wide_table_layout(rows, col_count)
            return cls._result("bitfield", 0.90, col_count, [0.12, 0.22, 0.10, 0.10, 0.46], issues,
                               landscape=landscape, font_size=fs or (8.5 if col_count >= 7 else 9), code_cols=[0, 1, 2, 3])
        if cls._hits(header_norm, cls.BNF) >= 3:
            return cls._result("bnf", 0.94, col_count, [0.17, 0.22, 0.34, 0.27], issues, code_cols=[0, 2])
        if cls._hits(header_norm, cls.INTERFACE) >= 3:
            return cls._result("interface", 0.88, col_count, [0.24, 0.52, 0.24], issues, code_cols=[1, 2])
        if cls._hits(header_norm, cls.PARAMETER) >= 3:
            return cls._result("parameter", 0.86, col_count, [0.22, 0.14, 0.14, 0.14, 0.36], issues, code_cols=[0, 1])
        if cls._hits(header_norm, cls.ERROR_CODE) >= 3:
            return cls._result("error_code", 0.86, col_count, [0.14, 0.22, 0.40, 0.24], issues, code_cols=[0])
        if col_count == 2 and (cls._hits(header_norm, cls.GLOSSARY) >= 1 or cls._looks_glossary(rows)):
            return cls._result("glossary", 0.82, col_count, [0.22, 0.78], issues, code_cols=[0])

        # Common reference tables: short code columns plus long-name columns.
        if cls._looks_reference_table(rows):
            landscape, fs = cls._wide_table_layout(rows, col_count)
            return cls._result("reference", 0.78, col_count, [0.16, 0.26, 0.28, 0.30], issues,
                               code_cols=[0, 1], landscape=landscape, font_size=fs or (8.5 if col_count >= 7 else None))

        return cls._generic(col_count, issues)

    @staticmethod
    def rows_from_ast(table_node: dict) -> List[List[str]]:
        rows = []
        for row in table_node.get("children", []):
            rows.append([
                cell.get("content", "") or ""
                for cell in row.get("children", [])
            ])
        return rows

    @staticmethod
    def rows_from_html_table(tag) -> List[List[str]]:
        rows = []
        for tr in tag.find_all("tr"):
            cells = tr.find_all(["th", "td"], recursive=False)
            if cells:
                rows.append([c.get_text(" ", strip=True) for c in cells])
        return rows

    @staticmethod
    def _header(rows: Sequence[Sequence[str]]) -> Sequence[str]:
        return rows[0] if rows else []

    @staticmethod
    def _hits(values: Iterable[str], keywords: set[str]) -> int:
        hits = 0
        for value in values:
            for kw in keywords:
                if _norm(kw) and _norm(kw) in value:
                    hits += 1
                    break
        return hits

    @staticmethod
    def _looks_revision(rows: Sequence[Sequence[str]]) -> bool:
        first_col = [_visible(r[0]) for r in rows[1:6] if r]
        version_hits = sum(1 for v in first_col if re.match(r"^[A-Za-z]/\d+|^V\d+", v))
        text = " ".join(_visible(c) for r in rows[:2] for c in r)
        return version_hits >= 2 or ("修订" in text and ("日期" in text or "版" in text))

    @staticmethod
    def _looks_register(rows: Sequence[Sequence[str]]) -> bool:
        sample = [c for r in rows[1:12] for c in r]
        addr_hits = sum(1 for c in sample if re.search(r"\b0x[0-9a-fA-F]+\b", c))
        access_hits = sum(1 for c in sample if re.fullmatch(r"\s*(RO|RW|WO|W1C|RC|R/W|R|W)\s*", c, re.I))
        bit_hits = sum(1 for c in sample if re.search(r"\[[0-9]+:[0-9]+\]|\bbit\s*[0-9]+|\b[0-9]+:[0-9]+\b", c, re.I))
        return addr_hits >= 2 and (access_hits >= 2 or bit_hits >= 2)

    @staticmethod
    def _looks_bitfield(rows: Sequence[Sequence[str]]) -> bool:
        sample = [c for r in rows[1:12] for c in r]
        bit_hits = sum(1 for c in sample if re.search(r"\[[0-9]+:[0-9]+\]|\bbit\s*[0-9]+|\b[0-9]+:[0-9]+\b", c, re.I))
        access_hits = sum(1 for c in sample if re.fullmatch(r"\s*(RO|RW|WO|W1C|RC|R/W|R|W)\s*", c, re.I))
        return bit_hits >= 3 and access_hits >= 1

    @staticmethod
    def _looks_glossary(rows: Sequence[Sequence[str]]) -> bool:
        if not rows or max(len(r) for r in rows) != 2:
            return False
        left = [_visible(r[0]) for r in rows[1:10] if len(r) > 1]
        right = [_visible(r[1]) for r in rows[1:10] if len(r) > 1]
        return bool(left and right) and sum(len(x) <= 30 for x in left) >= len(left) * 0.7

    @staticmethod
    def _looks_reference_table(rows: Sequence[Sequence[str]]) -> bool:
        if not rows:
            return False
        col_count = max(len(r) for r in rows)
        if col_count not in (3, 4, 7):
            return False
        short_cols = 0
        for ci in range(min(col_count, 4)):
            vals = [_visible(r[ci]) for r in rows[1:12] if ci < len(r) and _visible(r[ci])]
            if vals and sum(len(v) <= 18 for v in vals) >= len(vals) * 0.75:
                short_cols += 1
        return short_cols >= 2

    @classmethod
    def _generic(cls, col_count: int, issues: Optional[List[str]] = None) -> TableAnalysis:
        if col_count <= 0:
            widths: List[int] = []
        else:
            widths = _scale_widths([1] * col_count)
        return TableAnalysis("generic", 0.50, TableLayout(widths=widths), issues or [])

    @classmethod
    def _explicit_result(cls, kind: str, col_count: int, issues: List[str]) -> Optional[TableAnalysis]:
        kind = kind.strip().lower().replace("-", "_")
        strategies = {
            "revision": ([0.06, 0.40, 0.14, 0.10, 0.24, 0.06], {}),
            "glossary": ([0.22, 0.78], {"code_cols": [0]}),
            "interface": ([0.24, 0.52, 0.24], {"code_cols": [1, 2]}),
            "bnf": ([0.17, 0.22, 0.34, 0.27], {"code_cols": [0, 2]}),
            "register": ([0.10, 0.11, 0.18, 0.09, 0.10, 0.42], {"landscape": col_count >= 7, "font_size": 8.5, "code_cols": [0, 1, 2, 3, 4]}),
            "bitfield": ([0.12, 0.22, 0.10, 0.10, 0.46], {"landscape": col_count >= 7, "font_size": 8.5, "code_cols": [0, 1, 2, 3]}),
            "parameter": ([0.22, 0.14, 0.14, 0.14, 0.36], {"code_cols": [0, 1]}),
            "error_code": ([0.14, 0.22, 0.40, 0.24], {"code_cols": [0]}),
            "reference": ([0.16, 0.26, 0.28, 0.30], {"code_cols": [0, 1], "landscape": col_count >= 7, "font_size": 8.5 if col_count >= 7 else None}),
        }
        if kind not in strategies:
            return None
        weights, kwargs = strategies[kind]
        return cls._result(kind, 1.0, col_count, weights, issues, **kwargs)

    @classmethod
    def _result(
        cls,
        kind: str,
        confidence: float,
        col_count: int,
        weights: Sequence[float],
        issues: List[str],
        *,
        landscape: bool = False,
        font_size: Optional[float] = None,
        code_cols: Sequence[int] = (),
    ) -> TableAnalysis:
        if col_count != len(weights):
            weights = cls._adapt_weights(weights, col_count)
        total_width = LANDSCAPE_CONTENT_WIDTH_DXA if landscape else CONTENT_WIDTH_DXA
        layout = TableLayout(
            widths=_scale_widths(weights, total_width),
            repeat_header=True,
            fixed_layout=True,
            landscape=landscape,
            font_size_pt=font_size,
            code_columns=cls._code_columns(kind, col_count, code_cols),
            center_columns=cls._center_columns(kind, col_count),
            total_width_dxa=total_width,
        )
        return TableAnalysis(kind, confidence, layout, issues)

    @staticmethod
    def _adapt_weights(weights: Sequence[float], col_count: int) -> Sequence[float]:
        if col_count <= 0:
            return []
        if col_count < len(weights):
            return weights[:col_count]
        extra = col_count - len(weights)
        return list(weights[:-1]) + [0.12] * extra + [weights[-1]]

    @staticmethod
    def _center_columns(kind: str, col_count: int) -> List[int]:
        if kind == "revision":
            return [0, 2, 3, 4]
        if kind in ("register", "bitfield"):
            return [0, 1, 3, 4]
        if kind == "bnf":
            return [0]
        if col_count >= 7:
            return list(range(max(0, col_count - 2)))
        return []

    @staticmethod
    def _code_columns(kind: str, col_count: int, code_cols: Sequence[int]) -> List[int]:
        cols = [c for c in code_cols if c < col_count]
        if kind in ("register", "bitfield", "reference") and col_count > 1:
            cols = [c for c in cols if c != col_count - 1]
        return cols

    @classmethod
    def _wide_table_layout(cls, rows: Sequence[Sequence[str]], col_count: int) -> tuple:
        """Decide landscape + font-size only when columns are wide enough to need it.

        Many 7+ column tables have mostly 2-char cells (e.g. version/bit columns)
        and fit comfortably in portrait. Only tables whose estimated content width
        exceeds the portrait content area should switch to landscape.
        """
        if col_count < 7:
            return False, None

        col_max_lens = cls._estimate_column_content_widths(rows, col_count)
        total_est = sum(col_max_lens)
        # ~9000 dxa portrait content; allow ~85% before landscape
        if total_est > CONTENT_WIDTH_DXA * 0.85:
            return True, 8.5
        return False, None

    @staticmethod
    def _estimate_column_content_widths(rows: Sequence[Sequence[str]], col_count: int) -> List[float]:
        """Estimate per-column rendering width (dxa) from row content.

        CJK chars ~240dxa, ASCII ~120dxa at 10pt. Returns max width per column.
        """
        widths = [0.0] * col_count
        for row in rows:
            for ci in range(min(col_count, len(row))):
                text = _visible(row[ci])
                w = 0.0
                for c in text:
                    if '一' <= c <= '鿿' or '　' <= c <= '〿':
                        w += 240
                    elif '぀' <= c <= 'ヿ':
                        w += 220
                    else:
                        w += 120
                if w > widths[ci]:
                    widths[ci] = w
        return widths


def classify_table(rows: Sequence[Sequence[str]]) -> TableAnalysis:
    """Convenience wrapper for rule-based table classification."""

    return TableClassifier.classify(rows)
