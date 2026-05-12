"""转换质量管线 —— preflight → convert → postflight 自动闭环

@tool
name: conversion_pipeline
description: 自动编排 preflight→auto-fix→convert→postflight→retry 全流程。
             单文件转换的首选入口，替代手工三步调用。内置重试闭环：
             postflight 发现 critical 问题时自动修正源文件并重新转换。
when_to_use: 用户要求转换单个 Markdown 文件时优先使用。复杂/批量场景
             则手工编排 preflight + convert_directory + postflight。
input: Markdown 文件路径, format ('word'|'html'|'pdf'), max_retries (默认2)
output: PipelineResult (success, output_path, preflight/preflight_fixed/
        postflight_issues/postflight_critical/retries/error)
side_effect: 生成输出文件；源文件可能被 preflight 原地修改（有备份恢复）

用法:
    from pipeline import ConversionPipeline

    pipeline = ConversionPipeline(max_retries=2)
    result = pipeline.run("doc.md", format="word")

    print(f"输出: {result.output_path}")
    print(f"预检: {result.preflight_fixed} 处自动修复")
    print(f"重试: {result.retries} 次")
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Union, List
from dataclasses import dataclass, field

from preflight import PreflightChecker, PreflightReport
from postflight import PostflightChecker, PostflightReport
from api import Converter, ConversionResult


@dataclass
class PipelineResult:
    """一次完整管线的执行结果"""

    input_path: str
    output_path: str
    format: str
    success: bool

    # Preflight
    preflight_issues: int = 0
    preflight_errors: int = 0
    preflight_warnings: int = 0
    preflight_fixed: int = 0

    # Conversion
    conversion: Optional[ConversionResult] = None

    # Postflight
    postflight_issues: int = 0
    postflight_critical: int = 0

    # Retry
    retries: int = 0
    attempts: List[PipelineAttempt] = field(default_factory=list)

    # Error
    error: Optional[str] = None

    @property
    def had_preflight_errors(self) -> bool:
        return self.preflight_errors > 0

    @property
    def had_postflight_critical(self) -> bool:
        return self.postflight_critical > 0


@dataclass
class PipelineAttempt:
    """单次尝试的记录"""
    attempt: int
    preflight_report: Optional[PreflightReport] = None
    preflight_fixed: int = 0
    conversion: Optional[ConversionResult] = None
    postflight_report: Optional[PostflightReport] = None
    reverted_source: bool = False


class ConversionPipeline:
    """preflight → auto-fix → convert → postflight → retry 全自动管线

    将 Agent 级的手工协调下沉为 Python 层的自动闭环：

    1. Preflight 扫描 ──► 自动修复可修复项
    2. 如有不可修复的 error ──► 询问是否继续（返回 False）
    3. Convert ──► 执行转换
    4. Postflight 检查 ──► 如有 critical 问题
       a. 分析问题类型
       b. 尝试修正源文件
       c. 重新转换（最多 max_retries 次）
    """

    def __init__(self, max_retries: int = 2,
                 abort_on_preflight_error: bool = False):
        """
        Args:
            max_retries: postflight 失败后的最大重试次数
            abort_on_preflight_error: True 则在 preflight 发现不可修复 error 时终止
        """
        self.max_retries = max_retries
        self.abort_on_preflight_error = abort_on_preflight_error
        self._preflight = PreflightChecker()
        self._postflight = PostflightChecker()

    def run(
        self,
        input_path: Union[str, Path],
        format: str = '',
        output_path: Optional[Union[str, Path]] = None,
        **converter_options,
    ) -> PipelineResult:
        """执行完整管线

        Args:
            input_path: Markdown 源文件
            format: 输出格式，默认从 converter_options 或回退到 html
            output_path: 输出路径，None 则自动生成
            **converter_options: 传递给 Converter 的选项

        Returns:
            PipelineResult 包含每个阶段的摘要
        """
        input_path = Path(input_path)
        if not input_path.exists():
            return PipelineResult(
                input_path=str(input_path),
                output_path='',
                format=format or 'html',
                success=False,
                error=f'文件不存在: {input_path}',
            )

        format = format or converter_options.get('format', 'html')
        result = PipelineResult(
            input_path=str(input_path),
            output_path='',
            format=format,
            success=False,
        )

        # 备份源文件（用于重试时 revert）
        backup = self._backup(input_path)

        try:
            # === Phase 1: Preflight ===
            preflight_report = self._preflight.check(str(input_path))

            result.preflight_issues = len(preflight_report.issues)
            result.preflight_errors = preflight_report.errors
            result.preflight_warnings = preflight_report.warnings

            if preflight_report.has_fixable:
                fixed = self._preflight.auto_fix(str(input_path), preflight_report)
                result.preflight_fixed = fixed

            if preflight_report.has_errors and self.abort_on_preflight_error:
                result.error = (
                    f'Preflight 发现 {preflight_report.errors} 个不可自动修复的错误，'
                    f'已终止转换。请手动修复后重试。'
                )
                return result

            # === Phase 2-4: Convert + Postflight + Retry ===
            last_conversion = None

            for attempt_num in range(self.max_retries + 1):
                attempt = PipelineAttempt(attempt=attempt_num + 1)

                if attempt_num == 0:
                    attempt.preflight_report = preflight_report
                    attempt.preflight_fixed = result.preflight_fixed

                # Convert
                converter = Converter(**converter_options)
                conversion = converter.convert_file(
                    str(input_path), format=format, output_path=output_path,
                )
                attempt.conversion = conversion

                if not conversion.success:
                    result.attempts.append(attempt)
                    result.error = f'转换失败: {conversion.error}'
                    result.retries = attempt_num
                    return result

                last_conversion = conversion

                # Postflight
                postflight_report = self._postflight.check(conversion.output_path)
                attempt.postflight_report = postflight_report

                result.postflight_issues = len(postflight_report.issues)
                result.postflight_critical = postflight_report.critical_count

                if not postflight_report.has_critical:
                    # 成功
                    result.success = True
                    result.output_path = conversion.output_path
                    result.conversion = conversion
                    result.retries = attempt_num
                    result.attempts.append(attempt)
                    break

                # 有 critical 问题，尝试修复
                if attempt_num < self.max_retries:
                    fixed_any = self._attempt_postflight_fix(
                        input_path, postflight_report
                    )
                    if not fixed_any:
                        # 无法自动修复，不再重试
                        result.error = (
                            f'Postflight 发现 {postflight_report.critical_count} 个严重问题，'
                            f'无法自动修复。建议手动检查源文件。'
                        )
                        result.retries = attempt_num
                        result.attempts.append(attempt)
                        break

                    attempt.reverted_source = True
                    # 恢复备份，准备下一次尝试
                    self._restore(input_path, backup)

                result.attempts.append(attempt)

            # 最后一次尝试后仍有问题
            if not result.success and last_conversion:
                result.output_path = last_conversion.output_path
                result.conversion = last_conversion

        finally:
            # 恢复源文件
            self._restore(input_path, backup)

        return result

    def format_result(self, result: PipelineResult) -> str:
        """将管线结果格式化为用户可读的摘要"""
        parts = [f"转换{'完成' if result.success else '未完成'}："
                 f"{Path(result.input_path).name} → {result.format.upper()}"]

        if result.preflight_issues > 0:
            fixed_info = f"，自动修复 {result.preflight_fixed} 处" if result.preflight_fixed else ""
            parts.append(f"  Preflight: 发现 {result.preflight_issues} 个问题"
                        f"（{result.preflight_errors} 错误, {result.preflight_warnings} 警告）{fixed_info}")

        if result.success and result.conversion:
            kb = result.conversion.size_bytes // 1024
            parts.append(f"  输出: {result.output_path} ({kb} KB)")

        if result.retries > 0:
            parts.append(f"  重试: {result.retries} 次")

        if result.postflight_issues > 0:
            parts.append(f"  Postflight: {result.postflight_issues} 个问题"
                        f"（{result.postflight_critical} 严重）")

        if result.error:
            parts.append(f"  错误: {result.error}")

        return '\n'.join(parts)

    # ---- 内部方法 ----

    @staticmethod
    def _backup(file_path: Path) -> Path:
        backup = file_path.with_suffix(file_path.suffix + '.pipeline_bak')
        shutil.copy2(file_path, backup)
        return backup

    @staticmethod
    def _restore(file_path: Path, backup: Path):
        if backup.exists():
            shutil.move(str(backup), str(file_path))

    def _attempt_postflight_fix(
        self, input_path: Path, report: PostflightReport
    ) -> bool:
        """根据 postflight 报告尝试修正源文件，返回是否做了任何修改"""
        content = input_path.read_text(encoding='utf-8')
        modified = False

        for issue in report.issues:
            if issue.category == 'placeholder':
                # 占位符残留 → 源文件中可能有对应的错误写法
                # 常见情况：[图片:xxx] → 图片引用路径不对
                modified |= self._fix_placeholder_source(content, issue)

            elif issue.category == 'mermaid':
                # Mermaid 在 Word/PDF 中未渲染 → 可能是中文标点问题
                modified |= self._fix_mermaid_source(content, issue)

        if modified:
            input_path.write_text(content, encoding='utf-8')
        return modified

    @staticmethod
    def _fix_placeholder_source(content: str, issue) -> bool:
        """尝试修复导致占位符的源文件问题"""
        # 占位符通常源于图片路径问题或 math 语法错误
        # 源文件修复能力有限，主要靠 preflight 预防
        return False  # 占位符问题难以自动追溯到源文件具体位置

    @staticmethod
    def _fix_mermaid_source(content: str, issue) -> bool:
        """修正 mermaid 相关问题的源文件"""
        # Mermaid 在 Word/PDF 中出现原始代码 →
        # 可能是 mermaid 代码块中的中文标点导致渲染失败
        # preflight 已经处理过，这里作为二次保险
        replacements = {
            '"': '"', '"': '"',  # 中文引号
            '：': ':',             # 中文冒号
            '；': ';',             # 中文分号
            '（': '(', '）': ')',  # 中文括号
        }
        modified = False
        for old, new in replacements.items():
            if old in content:
                content = content.replace(old, new)
                modified = True
        return modified
