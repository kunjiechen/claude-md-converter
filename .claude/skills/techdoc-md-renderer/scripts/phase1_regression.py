"""Phase 1 regression entry for no-silent-content-loss checks.

This runner is intentionally small: it parses Markdown samples with the legacy
parser, collects diagnostics, and asserts that known content-loss hazards are
represented instead of silently dropped. It does not invoke HTML/DOCX/PDF
renderers, so it is safe to run early in migration.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

from content_loss_checker import check_ast
from parser import MarkdownParser


@dataclass
class Phase1Item:
    input_path: str
    passed: bool
    diagnostics: List[Dict] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)


@dataclass
class Phase1Report:
    input_dir: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    items: List[Phase1Item] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


def run(input_dir: str, output_path: str | None = None) -> Phase1Report:
    root = Path(input_dir)
    parser = MarkdownParser()
    report = Phase1Report(input_dir=str(root))
    md_files = sorted(
        p for p in root.rglob("*")
        if p.suffix.lower() in (".md", ".markdown") and p.name.lower() not in {"readme.md", "readme.markdown"}
    )
    for path in md_files:
        ast = parser.parse_file(str(path))
        loss_report = check_ast(ast)
        checks = {
            "mixed_image_paragraph_preserved": _has_mixed_image_paragraph(ast) if path.name == "no_silent_content_loss.md" else True,
            "raw_html_diagnosed": _has_raw_html_diagnostic(ast) if path.name == "no_silent_content_loss.md" else True,
            "single_image_still_block": _has_single_image_block(ast) if path.name == "no_silent_content_loss.md" else True,
        }
        passed = all(checks.values()) and not loss_report.has_critical
        report.items.append(Phase1Item(
            input_path=str(path),
            passed=passed,
            diagnostics=loss_report.diagnostics,
            checks=checks,
        ))
    report.total = len(report.items)
    report.passed = sum(1 for i in report.items if i.passed)
    report.failed = report.total - report.passed
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _walk(ast: List[Dict]):
    for node in ast:
        yield node
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                yield from _walk([child])


def _has_mixed_image_paragraph(ast: List[Dict]) -> bool:
    for node in _walk(ast):
        if node.get("type") != "paragraph":
            continue
        children = node.get("children") or []
        has_image = any(c.get("type") == "image" for c in children if isinstance(c, dict))
        has_text = any(c.get("type") == "text" and c.get("content", "").strip() for c in children if isinstance(c, dict))
        if has_image and has_text and "完成接口连接" in node.get("content", ""):
            return True
    return False


def _has_raw_html_diagnostic(ast: List[Dict]) -> bool:
    for node in _walk(ast):
        if node.get("type") != "raw_html":
            continue
        diagnostics = (node.get("attributes") or {}).get("diagnostics") or []
        if any(d.get("code") == "unsupported_raw_html_block" for d in diagnostics):
            return True
    return False


def _has_single_image_block(ast: List[Dict]) -> bool:
    return any(
        node.get("type") == "image"
        and (node.get("attributes") or {}).get("alt") == "单图"
        for node in _walk(ast)
    )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Run Phase 1 no-silent-content-loss regression checks.")
    ap.add_argument("input_dir", nargs="?", default=str(Path(__file__).parent.parent / "samples" / "regression"))
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    report = run(args.input_dir, args.output or None)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
