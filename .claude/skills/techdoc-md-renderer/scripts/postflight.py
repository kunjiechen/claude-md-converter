"""Post-flight 输出质量检查

@tool
name: postflight_check
description: 转换完成后检查输出文件（HTML/Word/PDF），识别占位符残留、流程图未渲染、
             图片引用断裂、表格溢出等质量问题。
when_to_use: 每次 convert 之后必须调用。发现 critical 问题说明需要修复源文件后重新转换，
             发现 warning 则提醒用户但不阻断。
input: 输出文件路径 (str)，支持 .html / .docx / .pdf
output: PostflightReport (issues 列表, critical_count/warning_count)
side_effect: 无，只读检查

支持格式: HTML (.html), Word (.docx)
PDF 为二进制格式，仅做基本检查。

用法:
    from postflight import PostflightChecker

    checker = PostflightChecker()
    report = checker.check("output/doc.html")
    if report.has_critical:
        print("建议修复源文件后重新转换")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List
from dataclasses import dataclass, field


@dataclass
class PostflightIssue:
    """单个输出质量问题"""
    severity: str          # "critical" | "warning"
    category: str          # "placeholder" | "image" | "table" | "mermaid"
    message: str
    location: str = ""     # e.g., "L42", "paragraph 15"


@dataclass
class PostflightReport:
    """Post-flight 检查报告"""
    file_path: str
    format: str            # "html" | "docx" | "pdf"
    issues: List[PostflightIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0


class PostflightChecker:
    """输出文件质量检查器

    检查转换产物是否存在以下问题:
    - 占位符残留（[图片:xxx], [公式] 等）
    - Mermaid 在 Word/PDF 中未预渲染
    - HTML 中图片引用断裂
    - 表格溢出风险
    """

    # 占位符模式
    PLACEHOLDER_PATTERNS = [
        (re.compile(r'\[图片[:：]\s*[^\]]*\]'), '图片占位符未替换'),
        (re.compile(r'\[公式\]'), '公式占位符未替换'),
        (re.compile(r'\[数学[:：]\s*[^\]]*\]'), '数学公式占位符未替换'),
        (re.compile(r'\[table[:：]\s*[^\]]*\]'), '表格占位符未替换'),
    ]

    def check(self, file_path: str) -> PostflightReport:
        """检查输出文件，返回质量报告"""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = p.suffix.lower()
        if suffix in ('.html', '.htm'):
            return self._check_html(p)
        elif suffix == '.docx':
            return self._check_docx(p)
        elif suffix == '.pdf':
            return self._check_pdf(p)
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def format_report(self, report: PostflightReport) -> str:
        """将报告格式化为可读文本"""
        if not report.has_issues:
            return f"输出文件 {Path(report.file_path).name} 质量检查通过。"

        parts = [
            f"检查 {Path(report.file_path).name} ({report.format})："
            f"发现 {len(report.issues)} 个问题"
            f"（{report.critical_count} 严重, {report.warning_count} 警告）\n"
        ]

        by_cat: dict[str, list[PostflightIssue]] = {}
        for i in report.issues:
            by_cat.setdefault(i.category, []).append(i)

        cat_labels = {
            'placeholder': '占位符残留',
            'image': '图片问题',
            'mermaid': '流程图渲染',
            'table': '表格问题',
        }

        for cat, cat_issues in by_cat.items():
            label = cat_labels.get(cat, cat)
            parts.append(f"  {label}:")
            for issue in cat_issues:
                tag = '✕' if issue.severity == 'critical' else '△'
                loc = f" ({issue.location})" if issue.location else ""
                parts.append(f"    {tag}{loc}: {issue.message}")

        if report.has_critical:
            parts.append("\n存在严重问题，建议修复源文件后重新转换。")

        return '\n'.join(parts)

    # ---- HTML 检查 ----

    def _check_html(self, file_path: Path) -> PostflightReport:
        report = PostflightReport(file_path=str(file_path), format='html')
        html = file_path.read_text(encoding='utf-8')
        base_dir = file_path.parent

        self._check_placeholders(html, report)
        self._check_html_images(html, base_dir, report)
        self._check_html_mermaid(html, report)

        return self._finalize(report)

    def _check_html_images(self, html: str, base_dir: Path, report: PostflightReport):
        """检查 HTML 中本地图片的 src 是否可达"""
        img_re = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)
        for m in img_re.finditer(html):
            src = m.group(1)
            if src.startswith(('http://', 'https://', 'data:')):
                continue
            # 本地路径
            candidate = base_dir / src
            if not candidate.exists():
                self._add_issue(report, 'warning', 'image',
                              f'图片文件不存在: {src}')

    def _check_html_mermaid(self, html: str, report: PostflightReport):
        """检查 HTML 中的 mermaid 是否正确配置"""
        has_mermaid_pre = '<pre class="mermaid">' in html
        has_mermaid_js = 'mermaid.min.js' in html or 'mermaid.js' in html

        if has_mermaid_pre and not has_mermaid_js:
            self._add_issue(report, 'critical', 'mermaid',
                          'HTML 含 mermaid 代码块但未引入 mermaid.js，'
                          '流程图将无法渲染。请确保使用 browser 渲染模式')

    # ---- docx 检查 ----

    def _check_docx(self, file_path: Path) -> PostflightReport:
        report = PostflightReport(file_path=str(file_path), format='docx')
        try:
            from docx import Document
        except ImportError:
            self._add_issue(report, 'warning', 'placeholder',
                          '无法安装 python-docx，跳过 docx 内容检查')
            return report

        doc = Document(str(file_path))

        for i, para in enumerate(doc.paragraphs, 1):
            text = para.text
            self._check_text_for_placeholders(text, report, f'段落 {i}')

            # 检查 mermaid 退化：Word 中不应出现 <pre class="mermaid">
            if '<pre class="mermaid">' in text or '```mermaid' in text:
                self._add_issue(report, 'critical', 'mermaid',
                              'Word 中出现未渲染的 mermaid 代码，'
                              '应使用 server 模式预渲染',
                              f'段落 {i}')

        # 检查表格溢出风险
        for ti, table in enumerate(doc.tables, 1):
            col_count = len(table.columns)
            if col_count > 6:
                self._add_issue(report, 'warning', 'table',
                              f'表格有 {col_count} 列，在 A4 页面可能溢出',
                              f'表格 {ti}')

        return self._finalize(report)

    # ---- PDF 检查 ----

    def _check_pdf(self, file_path: Path) -> PostflightReport:
        report = PostflightReport(file_path=str(file_path), format='pdf')
        file_size = file_path.stat().st_size
        if file_size < 1024:
            self._add_issue(report, 'critical', 'placeholder',
                          f'PDF 文件过小 ({file_size} bytes)，可能生成失败')
        return self._finalize(report)

    # ---- 通用检查 ----

    def _check_placeholders(self, text: str, report: PostflightReport):
        """检查文本中的占位符残留"""
        self._check_text_for_placeholders(text, report, '')

    def _check_text_for_placeholders(self, text: str, report: PostflightReport,
                                     location: str):
        for pattern, desc in self.PLACEHOLDER_PATTERNS:
            for m in pattern.finditer(text):
                loc = f'L{text[:m.start()].count(chr(10)) + 1}' if not location else location
                self._add_issue(report, 'critical', 'placeholder',
                              f'{desc}: "{m.group()}"', loc)

    # ---- 工具方法 ----

    def _add_issue(self, report: PostflightReport, severity: str,
                   category: str, message: str, location: str = ''):
        issue = PostflightIssue(
            severity=severity, category=category,
            message=message, location=location,
        )
        report.issues.append(issue)
        if severity == 'critical':
            report.critical_count += 1
        else:
            report.warning_count += 1

    @staticmethod
    def _finalize(report: PostflightReport) -> PostflightReport:
        report.issues.sort(key=lambda x: (0 if x.severity == 'critical' else 1, x.category))
        return report
