"""Markdown source normalization before parsing.

This module fixes structural issues that are common in Markdown converted from
Word/PDF sources. It intentionally keeps the rules conservative: only clear
table-fragment patterns are normalized so ordinary prose is not rewritten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NormalizeIssue:
    line: int
    category: str
    message: str


@dataclass
class NormalizeReport:
    issues: List[NormalizeIssue] = field(default_factory=list)

    @property
    def modified(self) -> int:
        return len(self.issues)


# Converted Word/PDF Markdown frequently emits compact delimiter cells such as
# ":-" instead of the CommonMark-preferred "---". markdown-it accepts these in
# practice, so the normalizer must recognize them when merging split tables.
_DELIM_CELL_RE = re.compile(r"^\s*:?-{1,}:?\s*$")


def normalize_markdown_text(text: str, report: Optional[NormalizeReport] = None) -> str:
    """Normalize Markdown text before markdown-it parsing.

    Current rules:
    - Merge adjacent table blocks separated by blank lines when the following
      block repeats a Markdown delimiter row. This pattern appears when a single
      Word table is exported as several Markdown tables.
    """

    try:
        return _normalize_table_fragments(text, report)
    except Exception:
        # Normalization must never block conversion.
        return text


def _normalize_table_fragments(text: str, report: Optional[NormalizeReport] = None) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    blocks = _find_table_blocks(lines)
    if len(blocks) < 2:
        return text

    remove_lines: set[int] = set()
    remove_blank_ranges: list[tuple[int, int]] = []

    for idx in range(len(blocks) - 1):
        a_start, a_end = blocks[idx]
        b_start, b_end = blocks[idx + 1]
        gap = b_start - a_end - 1
        if gap < 0 or gap > 2:
            continue
        if not all(not lines[i].strip() for i in range(a_end + 1, b_start)):
            continue
        a_cols = _column_count(lines[a_start])
        b_cols = _column_count(lines[b_start])
        if a_cols < 2 or a_cols != b_cols:
            continue
        b_delim = _delimiter_row_index(lines, b_start, b_end)
        if b_delim is None:
            continue
        # The previous block must already be a Markdown table. Otherwise the
        # next block may be an intentionally separate table with its own header.
        if _delimiter_row_index(lines, a_start, a_end) is None:
            continue

        remove_blank_ranges.append((a_end + 1, b_start))
        remove_lines.add(b_delim)
        for row_idx in range(b_delim + 1, b_end + 1):
            if _is_empty_table_row(lines[row_idx]):
                remove_lines.add(row_idx)
        if report is not None:
            report.issues.append(NormalizeIssue(
                line=b_start + 1,
                category="table",
                message="merged a split Markdown table fragment",
            ))

    if not remove_lines and not remove_blank_ranges:
        return text

    for start, end in remove_blank_ranges:
        for i in range(start, end):
            remove_lines.add(i)

    new_lines = [line for i, line in enumerate(lines) if i not in remove_lines]
    trailing_newline = "\n" if text.endswith("\n") else ""
    return "\n".join(new_lines) + trailing_newline


def _find_table_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start = None
    in_code = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
        is_table = not in_code and _is_table_line(line)
        if is_table:
            if start is None:
                start = i
            end = i
        elif start is not None:
            blocks.append((start, end))
            start = None
    if start is not None:
        blocks.append((start, end))
    return blocks


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _column_count(line: str) -> int:
    return len(line.strip().strip("|").split("|"))


def _is_empty_table_row(line: str) -> bool:
    if not _is_table_line(line):
        return False
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(not c for c in cells)


def _delimiter_row_index(lines: list[str], start: int, end: int) -> Optional[int]:
    for i in range(start, min(end + 1, start + 3)):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if cells and all(_DELIM_CELL_RE.match(c) for c in cells):
            return i
    return None
