"""Quality gate evaluation for generated documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


STATUS_PASS = "pass"
STATUS_REVIEW = "review"
STATUS_FAIL = "fail"


@dataclass
class QualityGateResult:
    """Product-level delivery decision for a conversion result."""

    status: str
    score: int
    deliverable: bool
    reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    review_categories: Dict[str, List[str]] = field(default_factory=dict)
    review_level: str = "passed"
    review_summary: str = "质量门禁通过，可作为可阅读产物交付。"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_quality_report(report: Dict[str, Any]) -> QualityGateResult:
    """Evaluate a quality report into a delivery status.

    The gate is intentionally conservative: critical output issues or source
    errors fail the run; warnings and low-confidence table classification move
    the result into review instead of silently passing.
    """

    pre = report.get("preflight") or {}
    post = report.get("postflight") or {}
    artifact = report.get("artifact_validation") or {}
    tables = report.get("tables") or []
    norm = report.get("normalization") or {}

    pre_errors = int(pre.get("errors") or 0)
    pre_warnings = int(pre.get("warnings") or 0)
    post_critical = int(post.get("critical_count") or 0)
    post_warnings = int(post.get("warning_count") or 0)
    artifact_critical = int(artifact.get("critical_count") or 0)
    artifact_warnings = int(artifact.get("warning_count") or 0)
    low_conf_tables = [t for t in tables if t.get("low_confidence")]
    table_issue_count = sum(len(t.get("issues") or []) for t in tables)
    normalized_count = int(norm.get("modified") or 0)

    score = 100
    score -= pre_errors * 35
    score -= post_critical * 40
    score -= artifact_critical * 45
    score -= pre_warnings * 6
    score -= post_warnings * 8
    score -= artifact_warnings * 8
    score -= len(low_conf_tables) * 4
    score -= table_issue_count * 3
    score -= min(normalized_count, 5) * 2
    has_blocking_issue = bool(pre_errors or post_critical or artifact_critical)
    if not has_blocking_issue:
        score = max(score, 70)
    score = max(0, min(100, score))

    reasons: List[str] = []
    recommendations: List[str] = []
    review_categories: Dict[str, List[str]] = {
        "blocking": [],
        "source": [],
        "output": [],
        "visual": [],
        "table": [],
        "normalization": [],
        "confidence": [],
    }

    def add_reason(category: str, reason: str, recommendation: str = ""):
        reasons.append(reason)
        review_categories.setdefault(category, []).append(reason)
        if recommendation:
            recommendations.append(recommendation)

    if pre_errors:
        add_reason("blocking", f"preflight has {pre_errors} error(s)", "修复源 Markdown 中的阻断性问题后重新转换。")
    if post_critical:
        add_reason("blocking", f"postflight has {post_critical} critical issue(s)", "产物存在严重问题，不建议交付阅读。")
    if artifact_critical:
        add_reason("blocking", f"artifact validation has {artifact_critical} critical issue(s)", "最终产物结构校验失败，需要重新生成或修复转换器。")
    if post_warnings:
        add_reason("output", f"postflight has {post_warnings} warning(s)", "检查产物中的表格、图片、目录或流程图警告。")
    if artifact_warnings:
        visual_issues = [
            issue for issue in artifact.get("issues", [])
            if str(issue.get("category", "")).startswith("visual:")
        ]
        category = "visual" if visual_issues else "output"
        add_reason(category, f"artifact validation has {artifact_warnings} warning(s)", "检查最终 HTML/Word/PDF 产物是否为空白、缺样式、页数异常或内容不足。")
    if pre_warnings:
        add_reason("source", f"preflight has {pre_warnings} warning(s)", "检查源文件中的可疑语法或可能影响转换的写法。")
    if low_conf_tables:
        indexes = ", ".join(str(t.get("index")) for t in low_conf_tables[:8])
        add_reason("confidence", f"low-confidence table classification: {indexes}", "为低置信度表格添加显式标记，例如 <!-- table: register -->。")
    if table_issue_count:
        add_reason("table", f"table layout has {table_issue_count} issue hint(s)", "重点复查宽表、长单元格、寄存器/位域等高密度表格。")
    if normalized_count:
        add_reason("normalization", f"normalized {normalized_count} split table fragment(s)", "建议回写规范 Markdown 表格，减少转换前自动修复依赖。")

    if has_blocking_issue or score < 60:
        status = STATUS_FAIL
    elif reasons or score < 90:
        status = STATUS_REVIEW
    else:
        status = STATUS_PASS

    deliverable = status == STATUS_PASS
    review_level, review_summary = _classify_review_level(
        status=status,
        score=score,
        review_categories=review_categories,
        artifact=artifact,
        post_warnings=post_warnings,
        artifact_warnings=artifact_warnings,
        pre_warnings=pre_warnings,
    )
    if status == STATUS_PASS:
        recommendations.append("质量门禁通过，可作为可阅读产物交付。")
    elif status == STATUS_REVIEW:
        recommendations.append(review_summary)

    return QualityGateResult(
        status=status,
        score=score,
        deliverable=deliverable,
        reasons=reasons,
        recommendations=_dedupe(recommendations),
        review_categories={k: _dedupe(v) for k, v in review_categories.items() if v},
        review_level=review_level,
        review_summary=review_summary,
    )


def _classify_review_level(
    status: str,
    score: int,
    review_categories: Dict[str, List[str]],
    artifact: Dict[str, Any],
    post_warnings: int,
    artifact_warnings: int,
    pre_warnings: int,
) -> tuple[str, str]:
    if status == STATUS_PASS:
        return "passed", "质量门禁通过，可作为可阅读产物交付。"
    if status == STATUS_FAIL:
        return "blocked", "存在阻断性问题，不建议交付，需要修复后重新生成。"

    categories = {k for k, v in review_categories.items() if v}
    visual_dependency_only = _visual_dependency_only(artifact)
    format_categories = categories & {"output", "visual", "table"}

    if score < 75 or post_warnings >= 3 or artifact_warnings >= 3:
        return "format_risk", "产物已生成，但存在较高格式风险，建议修复后再交付。"
    if format_categories and not visual_dependency_only:
        return "format_risk", "产物可阅读性存在格式风险，请重点复核页面、表格、图片和目录。"
    if categories <= {"source", "normalization", "confidence", "visual"} and visual_dependency_only:
        return "readable_needs_review", "产物大概率可阅读，但因环境缺少视觉渲染或源文件自动规范化，建议人工快速复核。"
    if categories <= {"source", "normalization", "confidence"} and pre_warnings <= 10:
        return "readable_needs_review", "产物可生成且大概率可阅读，建议针对源文件警告和低置信度表格做人工复核。"
    return "needs_review", "产物可生成，但建议人工复核后再交付。"


def _visual_dependency_only(artifact: Dict[str, Any]) -> bool:
    issues = artifact.get("issues") or []
    visual_issues = [
        issue for issue in issues
        if str(issue.get("category", "")).startswith("visual:")
    ]
    if not visual_issues:
        return False
    return all(issue.get("category") == "visual:dependency" for issue in visual_issues)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
