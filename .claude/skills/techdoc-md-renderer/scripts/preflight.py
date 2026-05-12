"""Pre-flight 文档检查 & 自动修复

@tool
name: preflight_check
description: 在转换前扫描 Markdown 源文件，检测断链/图片缺失/Mermaid 中文标点/
             过宽表格/标题层级跳跃等 10 类问题，并提供自动修复。
when_to_use: 每次 convert 之前必须调用。发现可修复问题直接 auto_fix，
             不可修复的 error 告知用户后询问是否继续。
input: Markdown 文件路径 (str)
output: PreflightReport (issues 列表, errors/warnings/fixable 计数)
side_effect: auto_fix() 会原地修改源文件，修复中文标点、空链接、行尾空白等
example: |
    checker = PreflightChecker()
    report = checker.check("doc.md")
    if report.has_fixable:
        checker.auto_fix("doc.md", report)

用法:
    from preflight import PreflightChecker

    checker = PreflightChecker()
    report = checker.check("doc.md")

    for issue in report.issues:
        print(f"L{issue.line}: [{issue.severity}] {issue.message}")

    if report.has_fixable:
        fixed = checker.auto_fix("doc.md", report)
        print(f"已修复 {fixed} 处问题")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class CheckIssue:
    """单个检查问题"""
    line: int
    severity: str          # "error" | "warning" | "info"
    category: str          # "link" | "image" | "table" | "mermaid" | "heading" | "structure"
    message: str
    fixable: bool = False
    _fix_fn: Optional[Callable[[str], str]] = field(default=None, repr=False)

    def apply_fix(self, line_text: str) -> str:
        """对这一行文本应用修复，返回修复后的文本"""
        if self._fix_fn:
            return self._fix_fn(line_text)
        return line_text


@dataclass
class PreflightReport:
    """Pre-flight 检查报告"""
    file_path: str
    total_lines: int
    issues: List[CheckIssue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    fixable_count: int = 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def has_fixable(self) -> bool:
        return self.fixable_count > 0

    @property
    def has_errors(self) -> bool:
        return self.errors > 0


class PreflightChecker:
    """Markdown 文档 pre-flight 检查器

    扫描文档中的常见问题:
    - 断链 / 空 href
    - 图片路径不存在 / 远程图片风险
    - 过宽表格 (>6列)
    - Mermaid 常见语法错误 (中文标点等)
    - 标题层级跳跃
    - 空章节
    """

    # ---- 公共 API ----

    def check(self, file_path: str) -> PreflightReport:
        """扫描文件，返回检查报告"""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        lines = p.read_text(encoding='utf-8').split('\n')
        report = PreflightReport(
            file_path=str(p.resolve()),
            total_lines=len(lines),
        )

        checks = [
            self._check_broken_links,
            self._check_image_refs,
            self._check_wide_tables,
            self._check_mermaid_syntax,
            self._check_heading_gaps,
            self._check_empty_sections,
            self._check_trailing_whitespace,
            self._check_codeblock_language,
            self._check_duplicate_headings,
            self._check_consecutive_blank_lines,
        ]

        for check_fn in checks:
            for issue in check_fn(lines, p):
                report.issues.append(issue)
                if issue.severity == 'error':
                    report.errors += 1
                else:
                    report.warnings += 1
                if issue.fixable:
                    report.fixable_count += 1

        # 按行号排序
        report.issues.sort(key=lambda x: x.line)
        return report

    def auto_fix(self, file_path: str, report: PreflightReport = None) -> int:
        """自动修复所有 fixable 问题，返回修复数量。会原地修改文件。"""
        if report is None:
            report = self.check(file_path)

        fixable = [i for i in report.issues if i.fixable]
        if not fixable:
            return 0

        p = Path(file_path)
        lines = p.read_text(encoding='utf-8').split('\n')

        # 按行号分组，每行可能有多处修复
        fixes_by_line: dict[int, list[CheckIssue]] = {}
        for issue in fixable:
            fixes_by_line.setdefault(issue.line - 1, []).append(issue)

        for line_idx, issue_list in fixes_by_line.items():
            text = lines[line_idx]
            for issue in issue_list:
                text = issue.apply_fix(text)
            lines[line_idx] = text

        # 移除标记为 __DELETE__ 的行
        lines = [l for l in lines if l != '__DELETE__']

        p.write_text('\n'.join(lines), encoding='utf-8')
        return len(fixable)

    def format_report(self, report: PreflightReport) -> str:
        """将报告格式化为可读文本"""
        if not report.has_issues:
            return "文档检查通过，未发现问题。"

        parts = [f"检查 {Path(report.file_path).name}："
                 f"发现 {len(report.issues)} 个问题"
                 f"（{report.errors} 错误, {report.warnings} 警告, {report.fixable_count} 可自动修复）\n"]

        by_cat: dict[str, list[CheckIssue]] = {}
        for i in report.issues:
            by_cat.setdefault(i.category, []).append(i)

        cat_labels = {
            'link': '链接问题',
            'image': '图片问题',
            'table': '表格问题',
            'mermaid': 'Mermaid 语法',
            'heading': '标题结构',
            'structure': '文档结构',
        }

        for cat, cat_issues in by_cat.items():
            label = cat_labels.get(cat, cat)
            parts.append(f"  {label}:")
            for issue in cat_issues:
                tag = '✕' if issue.severity == 'error' else '△'
                fix_tag = ' [可自动修复]' if issue.fixable else ''
                parts.append(f"    {tag} L{issue.line}: {issue.message}{fix_tag}")

        if report.has_fixable:
            parts.append(f"\n可对 {report.fixable_count} 处问题执行自动修复。")

        return '\n'.join(parts)

    # ---- 各项检查 ----

    def _check_broken_links(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查断链和空链接"""
        issues = []
        # 匹配 [text](url)
        link_re = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
        # 排除图片 ![]()
        img_re = re.compile(r'!\[([^\]]*)\]\(([^)]*)\)')

        for i, line in enumerate(lines, 1):
            # 跳过代码块
            if line.strip().startswith('```'):
                continue
            # 跳过图片
            for m in img_re.finditer(line):
                url = m.group(2)
                if not url.strip():
                    issues.append(CheckIssue(
                        line=i, severity='error', category='link',
                        message=f'图片链接缺少 URL: ![{m.group(1)}]()',
                        fixable=False,
                    ))

            for m in link_re.finditer(line):
                # 前面没有 ! 才是链接
                start = m.start()
                if start > 0 and line[start - 1] == '!':
                    continue
                text, url = m.group(1), m.group(2)
                if not url.strip():
                    issues.append(CheckIssue(
                        line=i, severity='error', category='link',
                        message=f'空链接: [{text}]()',
                        fixable=True,
                        _fix_fn=lambda lt, t=text: lt.replace(
                            f'[{t}]()', f'[{t}](#)', 1),
                    ))
                elif url.startswith('http') and 'example.com' in url:
                    issues.append(CheckIssue(
                        line=i, severity='warning', category='link',
                        message=f'疑似示例链接: [{text}]({url})',
                        fixable=False,
                    ))

        return issues

    def _check_image_refs(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查图片引用"""
        issues = []
        img_re = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        doc_dir = file_path.parent

        for i, line in enumerate(lines, 1):
            if line.strip().startswith('```'):
                continue
            for m in img_re.finditer(line):
                alt, src = m.group(1), m.group(2)
                if src.startswith(('http://', 'https://')):
                    issues.append(CheckIssue(
                        line=i, severity='warning', category='image',
                        message=f'远程图片（需网络）: ![{alt}]({src})',
                        fixable=False,
                    ))
                elif src.startswith('data:'):
                    continue  # base64 内联，OK
                else:
                    # 本地图片
                    candidate = doc_dir / src
                    if not candidate.exists():
                        # 尝试相对于 doc_dir
                        alt_candidate = doc_dir / src.lstrip('/')
                        if not alt_candidate.exists():
                            issues.append(CheckIssue(
                                line=i, severity='error', category='image',
                                message=f'本地图片不存在: ![{alt}]({src})',
                                fixable=False,
                            ))

        return issues

    def _check_wide_tables(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查过宽的表格（列数 > 6）"""
        issues = []
        in_table = False
        table_start = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_start = i
                # 统计列数
                cols = [c for c in stripped.split('|') if c.strip() != '']
                # 跳过对齐行
                if all(re.match(r'^:?-+:?$', c.strip()) for c in cols if c.strip()):
                    continue
                if len(cols) > 6:
                    issues.append(CheckIssue(
                        line=table_start, severity='warning', category='table',
                        message=f'表格有 {len(cols)} 列，在 Word/PDF 中可能过宽溢出页面',
                        fixable=False,
                    ))
                    break  # 每个表格只报一次
            elif in_table and not stripped.startswith('|'):
                in_table = False

        return issues

    def _check_mermaid_syntax(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查 Mermaid 代码块常见错误"""
        issues = []
        in_mermaid = False
        block_start = 0
        block_lines: List[str] = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('```mermaid') or stripped == '```mermaid':
                in_mermaid = True
                block_start = i
                block_lines = [stripped]
            elif stripped == '```' and in_mermaid:
                block_lines.append(stripped)
                issues.extend(self._analyze_mermaid_block(block_start, block_lines))
                in_mermaid = False
                block_lines = []
            elif in_mermaid:
                block_lines.append(line)

        return issues

    def _analyze_mermaid_block(self, start_line: int, block_lines: List[str]) -> List[CheckIssue]:
        """分析单个 mermaid 代码块"""
        issues = []
        full_text = '\n'.join(block_lines)

        # 中文标点检查
        for i, line in enumerate(block_lines):
            rel_line = start_line + i
            # 中文引号
            if '“' in line or '”' in line:
                issues.append(CheckIssue(
                    line=rel_line, severity='error', category='mermaid',
                    message=f'Mermaid 中使用了中文引号 """, 会导致渲染失败',
                    fixable=True,
                    _fix_fn=lambda lt: lt.replace('“', '"').replace('”', '"'),
                ))
            # 中文冒号
            if '：' in line:
                issues.append(CheckIssue(
                    line=rel_line, severity='error', category='mermaid',
                    message=f'Mermaid 中使用了中文冒号 ：, 应改为英文 :',
                    fixable=True,
                    _fix_fn=lambda lt: lt.replace('：', ':'),
                ))
            # 中文分号（时序图）
            if '；' in line and ('sequenceDiagram' in full_text or 'sequenceDiagram' in block_lines[0]):
                issues.append(CheckIssue(
                    line=rel_line, severity='warning', category='mermaid',
                    message=f'时序图中使用了中文分号 ；, 应改为英文 ;',
                    fixable=True,
                    _fix_fn=lambda lt: lt.replace('；', ';'),
                ))
            # 中文括号
            if '（' in line or '）' in line:
                issues.append(CheckIssue(
                    line=rel_line, severity='error', category='mermaid',
                    message=f'Mermaid 节点标签中使用了中文括号（）, 可能导致解析错误',
                    fixable=True,
                    _fix_fn=lambda lt: lt.replace('（', '(').replace('）', ')'),
                ))

        # 空图检查
        content_lines = [l for l in block_lines[1:-1]
                         if l.strip() and not l.strip().startswith('%%')]
        if len(content_lines) <= 1:
            issues.append(CheckIssue(
                line=start_line, severity='warning', category='mermaid',
                message='Mermaid 图内容似乎为空或只有一行',
                fixable=False,
            ))

        return issues

    def _check_heading_gaps(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查标题层级跳跃（如 h1→h3 跳过 h2）"""
        issues = []
        prev_level = 0

        for i, line in enumerate(lines, 1):
            m = re.match(r'^(#{1,6})\s+', line)
            if m:
                level = len(m.group(1))
                if prev_level > 0 and level > prev_level + 1:
                    issues.append(CheckIssue(
                        line=i, severity='warning', category='heading',
                        message=f'标题层级跳跃: h{prev_level} → h{level}（跳过了 h{prev_level + 1}）',
                        fixable=False,
                    ))
                prev_level = level

        return issues

    def _check_empty_sections(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查空章节（标题后到下一个标题之间没有实质内容）"""
        issues = []

        for i, line in enumerate(lines, 1):
            m = re.match(r'^(#{1,6})\s+(.+)', line)
            if m:
                heading_level = len(m.group(1))
                has_content = False
                # 往后扫描直到遇到同级或上级标题，或文件末尾
                for j in range(i, len(lines)):
                    next_line = lines[j].strip()
                    next_m = re.match(r'^(#{1,6})\s+', next_line)
                    if next_m:
                        next_level = len(next_m.group(1))
                        if next_level <= heading_level:
                            break
                        continue
                    if next_line and not next_line.startswith('```'):
                        has_content = True
                        break
                if not has_content:
                    issues.append(CheckIssue(
                        line=i, severity='info', category='structure',
                        message=f'章节 "{m.group(2)}" 下方没有内容',
                        fixable=False,
                    ))

        return issues

    def _check_trailing_whitespace(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查行尾空白字符（可自动修复）"""
        issues = []
        for i, line in enumerate(lines, 1):
            if line.endswith((' ', '\t')) and line.strip():
                issues.append(CheckIssue(
                    line=i, severity='warning', category='structure',
                    message='行尾有多余空白字符',
                    fixable=True,
                    _fix_fn=lambda lt: lt.rstrip(),
                ))
        return issues

    def _check_codeblock_language(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查未指定语言的围栏代码块"""
        issues = []
        in_codeblock = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('```') and not line.startswith('    '):
                lang = stripped[3:].strip()
                if in_codeblock:
                    in_codeblock = False
                else:
                    if not lang:
                        issues.append(CheckIssue(
                            line=i, severity='warning', category='structure',
                            message='代码块未指定语言，建议添加语言标识（如 ```python）',
                            fixable=False,
                        ))
                    in_codeblock = True
        return issues

    def _check_duplicate_headings(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查重复的标题文本"""
        issues = []
        seen: dict[str, int] = {}
        for i, line in enumerate(lines, 1):
            m = re.match(r'^(#{1,6})\s+(.+)', line)
            if m:
                title = m.group(2).strip()
                if title in seen:
                    issues.append(CheckIssue(
                        line=i, severity='warning', category='heading',
                        message=f'标题 "{title}" 重复出现（首次出现在 L{seen[title]}）',
                        fixable=False,
                    ))
                else:
                    seen[title] = i
        return issues

    def _check_consecutive_blank_lines(self, lines: List[str], file_path: Path) -> List[CheckIssue]:
        """检查连续空白行过多（>2 行），可自动合并"""
        issues = []
        blank_start = 0
        blank_count = 0

        for i, line in enumerate(lines, 1):
            if not line.strip():
                if blank_count == 0:
                    blank_start = i
                blank_count += 1
            else:
                if blank_count > 2:
                    for extra_line in range(blank_start + 2, i):
                        issues.append(CheckIssue(
                            line=extra_line, severity='warning', category='structure',
                            message=f'连续 {blank_count} 行空白，建议保留 2 行以内',
                            fixable=True,
                            _fix_fn=lambda lt, marker=None: '__DELETE__',
                        ))
                blank_count = 0

        # 处理文件末尾的连续空行
        if blank_count > 2:
            for extra_line in range(blank_start + 2, len(lines) + 1):
                issues.append(CheckIssue(
                    line=extra_line, severity='warning', category='structure',
                    message=f'文件末尾连续 {blank_count} 行空白',
                    fixable=True,
                    _fix_fn=lambda lt: '__DELETE__',
                ))

        return issues
