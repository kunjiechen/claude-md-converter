"""Quality report generation for Markdown conversion."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import html
import json
from typing import Any, Dict, List, Optional

from parser import MarkdownParser
from preflight import PreflightChecker
from postflight import PostflightChecker
from .document_classifier import DocumentClassifier
from .markdown_normalizer import NormalizeReport, normalize_markdown_text
from .table_classifier import TableClassifier
from .suggester import (
    SUGGESTION_CONFIDENCE_THRESHOLD,
    TableSuggestionReport,
    suggest_table_kind,
)
from .artifact_validator import ArtifactValidator
from .quality_gate import evaluate_quality_report


def build_quality_report(input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """Analyze source and optional output file, returning a JSON-serializable report."""

    source = Path(input_path)
    text = source.read_text(encoding="utf-8", errors="ignore")

    norm_report = NormalizeReport()
    normalized = normalize_markdown_text(text, norm_report)
    parser = MarkdownParser()
    ast = parser.parse(normalized)

    table_reports: List[Dict[str, Any]] = []
    analyses = []
    table_idx = 0
    for node in ast:
        if node.get("type") != "table":
            continue
        table_idx += 1
        explicit = node.get("attributes", {}).get("table_kind", "")
        rows = TableClassifier.rows_from_ast(node)
        analysis = TableClassifier.classify(rows, explicit_kind=explicit)
        analyses.append(analysis)

        sr = suggest_table_kind(rows, analysis)
        sr.table_index = table_idx
        suggestions = (
            [asdict(s) for s in sr.suggestions]
            if sr.has_suggestions
            else []
        )

        table_reports.append({
            "index": table_idx,
            "kind": analysis.kind,
            "confidence": analysis.confidence,
            "rows": len(rows),
            "columns": max((len(r) for r in rows), default=0),
            "explicit_kind": explicit,
            "layout": asdict(analysis.layout),
            "issues": analysis.issues,
            "suggestions": suggestions,
            "low_confidence": analysis.confidence < SUGGESTION_CONFIDENCE_THRESHOLD,
        })

    doc_analysis = DocumentClassifier.classify(ast, analyses)

    preflight = PreflightChecker()
    pre = preflight.check(str(source))
    post_payload = None
    artifact_payload = None
    if output_path and Path(output_path).exists():
        postflight = PostflightChecker()
        post = postflight.check(output_path)
        post_payload = {
            "format": post.format,
            "critical_count": post.critical_count,
            "warning_count": post.warning_count,
            "issues": [asdict(i) for i in post.issues],
        }
        artifact_payload = ArtifactValidator().validate(output_path).to_dict()

    report = {
        "input": str(source),
        "output": output_path,
        "document": asdict(doc_analysis),
        "normalization": {
            "modified": norm_report.modified,
            "issues": [asdict(i) for i in norm_report.issues],
        },
        "tables": table_reports,
        "preflight": {
            "errors": pre.errors,
            "warnings": pre.warnings,
            "fixable_count": pre.fixable_count,
            "issues": [_preflight_issue_dict(i) for i in pre.issues],
        },
        "postflight": post_payload,
        "artifact_validation": artifact_payload,
    }
    report["quality_gate"] = evaluate_quality_report(report).to_dict()
    return report


def write_quality_report(input_path: str, output_path: str, report_path: Optional[str] = None,
                         report: Optional[Dict[str, Any]] = None) -> str:
    """Write a quality report next to the output file unless a path is provided."""

    target = Path(report_path) if report_path else Path(output_path).with_suffix(Path(output_path).suffix + ".quality.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report or build_quality_report(input_path, output_path)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def write_quality_html_report(input_path: str, output_path: str, report_path: Optional[str] = None,
                              report: Optional[Dict[str, Any]] = None) -> str:
    """Write a human-readable HTML quality report."""

    target = Path(report_path) if report_path else Path(output_path).with_suffix(Path(output_path).suffix + ".quality.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report or build_quality_report(input_path, output_path)
    target.write_text(render_quality_report_html(payload), encoding="utf-8")
    return str(target)


def render_quality_report_html(report: Dict[str, Any]) -> str:
    """Render a compact standalone HTML report."""

    doc = report.get("document", {})
    tables = report.get("tables", [])
    pre = report.get("preflight", {})
    post = report.get("postflight") or {}
    artifact = report.get("artifact_validation") or {}
    norm = report.get("normalization", {})
    gate = report.get("quality_gate") or {}

    rows = []
    for t in tables:
        layout = t.get("layout", {})
        badges = []
        if layout.get("landscape"):
            badges.append("landscape")
        if layout.get("font_size_pt"):
            badges.append(f"{layout.get('font_size_pt')}pt")
        if t.get("explicit_kind"):
            badges.append("explicit")
        if t.get("low_confidence"):
            badges.append("low confidence")
        issues = "<br>".join(_e(i) for i in t.get("issues", [])) or "-"

        sug_html = ""
        sugs = t.get("suggestions", [])
        if sugs:
            sug_parts = []
            for s in sugs:
                sug_parts.append(
                    f"<div style='margin-bottom:4px'>"
                    f"<span class='kind'>{_e(s.get('kind_hint'))}</span> "
                    f"<span style='color:#5f6368'>({s.get('confidence')})</span>"
                    f" — {_e(s.get('reasoning'))}"
                    f"<br><code>{_e(s.get('action'))}</code>"
                    f"</div>"
                )
            sug_html = "".join(sug_parts)
        elif t.get("low_confidence"):
            sug_html = "<span style='color:#5f6368'>未能生成替代建议（数据行不足）</span>"

        rows.append(
            "<tr>"
            f"<td>{t.get('index')}</td>"
            f"<td><span class='kind'>{_e(t.get('kind'))}</span></td>"
            f"<td>{t.get('confidence')}</td>"
            f"<td>{t.get('rows')} x {t.get('columns')}</td>"
            f"<td>{_e(', '.join(str(b) for b in badges) or '-')}</td>"
            f"<td>{issues}</td>"
            f"<td>{sug_html or '-'}</td>"
            "</tr>"
        )

    pre_issues = _issue_list(pre.get("issues", [])[:20])
    post_issues = _issue_list(post.get("issues", [])[:20])
    recs = "".join(f"<li>{_e(r)}</li>" for r in doc.get("recommendations", [])) or "<li>-</li>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quality Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #202124; }}
h1 {{ font-size: 22px; margin: 0 0 12px; }}
h2 {{ font-size: 16px; margin-top: 24px; border-bottom: 1px solid #dadce0; padding-bottom: 6px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
.metric {{ border: 1px solid #dadce0; border-radius: 6px; padding: 12px; background: #fafafa; }}
.label {{ color: #5f6368; font-size: 12px; }}
.value {{ font-size: 18px; font-weight: 600; margin-top: 4px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #dadce0; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f1f3f4; text-align: left; }}
.kind {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
.ok {{ color: #137333; }}
.warn {{ color: #b06000; }}
.bad {{ color: #b3261e; }}
code {{ background: #f1f3f4; padding: 1px 4px; border-radius: 4px; }}
</style>
</head>
<body>
<h1>Quality Report</h1>
<div class="grid">
	  <div class="metric"><div class="label">Document Type</div><div class="value">{_e(doc.get('document_type'))}</div></div>
	  <div class="metric"><div class="label">Confidence</div><div class="value">{doc.get('confidence')}</div></div>
	  <div class="metric"><div class="label">Tables</div><div class="value">{len(tables)}</div></div>
	  <div class="metric"><div class="label">Quality Gate</div><div class="value {_gate_class(gate.get('status'))}">{_e(gate.get('status', '-'))} / {gate.get('score', 0)}</div></div>
	  <div class="metric"><div class="label">Review Level</div><div class="value">{_e(gate.get('review_level', '-'))}</div></div>
	</div>

	<h2>Quality Gate</h2>
	<p>Deliverable: <strong>{_e(gate.get('deliverable'))}</strong></p>
	<p>Review Summary: <strong>{_e(gate.get('review_summary', '-'))}</strong></p>
	{_quality_gate_list(gate)}

	<h2>Recommendations</h2>
<ul>{recs}</ul>

<h2>Normalization</h2>
<p>Merged table fragments: <strong>{norm.get('modified', 0)}</strong></p>

<h2>Tables</h2>
<table>
<thead><tr><th>#</th><th>Kind</th><th>Confidence</th><th>Size</th><th>Layout</th><th>Issues</th><th>Suggestions</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>

<h2>Preflight</h2>
<p>{pre.get('errors', 0)} errors / {pre.get('warnings', 0)} warnings / {pre.get('fixable_count', 0)} fixable</p>
{pre_issues}

	<h2>Postflight</h2>
	<p>{post.get('critical_count', 0)} critical / {post.get('warning_count', 0)} warnings</p>
	{post_issues}

	<h2>Artifact Validation</h2>
	<p>{artifact.get('critical_count', 0)} critical / {artifact.get('warning_count', 0)} warnings</p>
	{_issue_list(artifact.get('issues', [])[:20])}
	</body>
	</html>"""


def _preflight_issue_dict(issue) -> Dict[str, Any]:
    return {
        "line": issue.line,
        "severity": issue.severity,
        "category": issue.category,
        "message": issue.message,
        "fixable": issue.fixable,
    }


def _issue_list(issues: List[Dict[str, Any]]) -> str:
    if not issues:
        return "<p class='ok'>No issues.</p>"
    items = []
    for issue in issues:
        loc = issue.get("location") or (f"L{issue.get('line')}" if issue.get("line") else "")
        sev = issue.get("severity", "")
        msg = issue.get("message", "")
        items.append(f"<li><strong>{_e(sev)}</strong> {_e(loc)} {_e(msg)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _quality_gate_list(gate: Dict[str, Any]) -> str:
    reasons = gate.get("reasons") or []
    recs = gate.get("recommendations") or []
    categories = gate.get("review_categories") or {}
    parts = []
    if categories:
        parts.append("<p><strong>Review Categories</strong></p>")
        parts.append("<table><thead><tr><th>Category</th><th>Reasons</th></tr></thead><tbody>")
        for category, items in categories.items():
            parts.append(
                "<tr>"
                f"<td><span class='kind'>{_e(category)}</span></td>"
                f"<td>{'<br>'.join(_e(i) for i in items)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
    if reasons:
        parts.append("<p><strong>Reasons</strong></p>")
        parts.append("<ul>" + "".join(f"<li>{_e(r)}</li>" for r in reasons) + "</ul>")
    if recs:
        parts.append("<p><strong>Actions</strong></p>")
        parts.append("<ul>" + "".join(f"<li>{_e(r)}</li>" for r in recs) + "</ul>")
    return "".join(parts) or "<p class='ok'>Quality gate passed.</p>"


def _gate_class(status: Any) -> str:
    if status == "pass":
        return "ok"
    if status == "fail":
        return "bad"
    return "warn"


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))
