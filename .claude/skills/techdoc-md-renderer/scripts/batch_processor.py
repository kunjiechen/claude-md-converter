"""
批量处理器
支持批量转换Markdown文件
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from parser import MarkdownParser
from exporters.html import HtmlExporter
from exporters.word import WordExporter
from exporters.pdf import PdfExporter


class BatchProcessor:
    """批量处理器"""

    def __init__(self, **options):
        """
        初始化批量处理器

        Args:
            **options: 处理选项
                - format: 输出格式（word/html/pdf）
                - output_dir: 输出目录
                - max_workers: 最大并行数
                - log_file: 日志文件路径
                - verbose: 详细输出
        """
        self.format = options.get('format', 'word')
        self.output_dir = options.get('output_dir')
        self.max_workers = options.get('max_workers', 4)
        self.log_file = options.get('log_file')
        self.verbose = options.get('verbose', False)

        # 初始化解析器
        self.parser = MarkdownParser()

        # 初始化转换器
        if self.format == 'word':
            self.converter = WordExporter(**options)
        elif self.format == 'html':
            self.converter = HtmlExporter(**options)
        else:
            self.converter = PdfExporter(**options)

        # 日志记录
        self.logs = []

    def process_directory(self, input_dir: str) -> Dict[str, Any]:
        """
        处理目录中的所有Markdown文件

        Args:
            input_dir: 输入目录路径

        Returns:
            处理结果统计
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")

        if not input_path.is_dir():
            raise ValueError(f"输入路径不是目录: {input_dir}")

        # 查找所有Markdown文件
        md_files = self._find_markdown_files(input_path)

        if not md_files:
            self._log("warning", f"目录中没有找到Markdown文件: {input_dir}")
            return {'total': 0, 'success': 0, 'failed': 0, 'files': []}

        # 确保输出目录存在
        if self.output_dir:
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_path

        # 处理文件
        return self._process_files(md_files, output_path)

    def process_files(self, input_files: List[str], output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        处理指定的Markdown文件列表

        Args:
            input_files: 输入文件路径列表
            output_dir: 输出目录路径

        Returns:
            处理结果统计
        """
        # 验证文件
        md_files = []
        for file_path in input_files:
            path = Path(file_path)
            if path.exists() and path.suffix.lower() in ('.md', '.markdown'):
                md_files.append(path)
            else:
                self._log("warning", f"跳过无效文件: {file_path}")

        if not md_files:
            self._log("warning", "没有有效的Markdown文件")
            return {'total': 0, 'success': 0, 'failed': 0, 'files': []}

        # 确定输出目录
        if output_dir:
            output_path = Path(output_dir)
        elif self.output_dir:
            output_path = Path(self.output_dir)
        else:
            output_path = md_files[0].parent

        output_path.mkdir(parents=True, exist_ok=True)

        # 处理文件
        return self._process_files(md_files, output_path)

    def _find_markdown_files(self, directory: Path) -> List[Path]:
        """
        查找目录中的Markdown文件

        Args:
            directory: 目录路径

        Returns:
            Markdown文件列表
        """
        md_files = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.md', '.markdown')):
                    md_files.append(Path(root) / file)

        return sorted(md_files)

    def _process_files(self, md_files: List[Path], output_path: Path) -> Dict[str, Any]:
        """
        处理文件列表

        Args:
            md_files: Markdown文件列表
            output_path: 输出目录路径

        Returns:
            处理结果统计
        """
        results = {
            'total': len(md_files),
            'success': 0,
            'failed': 0,
            'files': [],
            'start_time': datetime.now().isoformat(),
            'end_time': None
        }

        self._log("info", f"开始批量处理: {len(md_files)} 个文件")

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_file = {}
            for md_file in md_files:
                output_file = self._get_output_path(md_file, output_path)
                future = executor.submit(self._convert_file, md_file, output_file)
                future_to_file[future] = md_file

            # 处理完成的任务
            for future in as_completed(future_to_file):
                md_file = future_to_file[future]
                try:
                    success, message = future.result()
                    file_result = {
                        'input': str(md_file),
                        'success': success,
                        'message': message
                    }

                    if success:
                        results['success'] += 1
                        self._log("info", f"转换成功: {md_file.name}")
                    else:
                        results['failed'] += 1
                        self._log("error", f"转换失败: {md_file.name} - {message}")

                    results['files'].append(file_result)

                except Exception as e:
                    results['failed'] += 1
                    file_result = {
                        'input': str(md_file),
                        'success': False,
                        'message': str(e)
                    }
                    results['files'].append(file_result)
                    self._log("error", f"处理异常: {md_file.name} - {e}")

        results['end_time'] = datetime.now().isoformat()

        # 保存日志
        if self.log_file:
            self._save_log(results)

        self._log("info", f"批量处理完成: 成功 {results['success']}, 失败 {results['failed']}")

        return results

    def _convert_file(self, input_path: Path, output_path: Path) -> tuple:
        """
        转换单个文件

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径

        Returns:
            (成功标志, 消息)
        """
        try:
            # 解析Markdown
            ast = self.parser.parse_file(str(input_path))

            # 转换格式
            success = self.converter.convert(ast, str(output_path))

            if success:
                return True, f"转换成功: {output_path}"
            else:
                return False, "转换失败"

        except Exception as e:
            return False, str(e)

    def _get_output_path(self, input_path: Path, output_dir: Path) -> Path:
        """
        获取输出文件路径

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录路径

        Returns:
            输出文件路径
        """
        # 生成输出文件名
        if self.format == 'word':
            output_name = input_path.stem + '.docx'
        elif self.format == 'html':
            output_name = input_path.stem + '.html'
        else:
            output_name = input_path.stem + '.pdf'

        return output_dir / output_name

    def _log(self, level: str, message: str):
        """
        记录日志

        Args:
            level: 日志级别
            message: 日志消息
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }

        self.logs.append(log_entry)

        # 控制台输出
        if self.verbose or level == 'error':
            print(f"[{level.upper()}] {message}")

    def _save_log(self, results: Dict[str, Any]):
        """
        保存日志文件

        Args:
            results: 处理结果
        """
        try:
            log_data = {
                'summary': {
                    'total': results['total'],
                    'success': results['success'],
                    'failed': results['failed'],
                    'start_time': results['start_time'],
                    'end_time': results['end_time']
                },
                'files': results['files'],
                'logs': self.logs
            }

            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)

            print(f"日志已保存: {self.log_file}")

        except Exception as e:
            print(f"保存日志失败: {e}")

    def get_log_summary(self) -> Dict[str, Any]:
        """
        获取日志摘要

        Returns:
            日志摘要
        """
        return {
            'total_logs': len(self.logs),
            'error_count': len([l for l in self.logs if l['level'] == 'error']),
            'warning_count': len([l for l in self.logs if l['level'] == 'warning']),
            'info_count': len([l for l in self.logs if l['level'] == 'info'])
        }