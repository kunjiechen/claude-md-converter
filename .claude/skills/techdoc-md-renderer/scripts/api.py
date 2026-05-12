"""
程序化 API — 统一的文档转换接口

@tool
name: convert_document
description: 将 Markdown 文件转换为 HTML/Word/PDF。统一 HTML 中间表示架构，
             所有格式共享同一渲染管线。支持单文件和目录批量转换。
when_to_use: preflight 检查通过后调用。用户指定目标格式时直接转换，
             格式不明确时根据场景推断（手机→HTML, 老板→Word, 打印→PDF）。
input: Markdown 文件路径, format ('word'|'html'|'pdf'), 可选参数 (doc_title,
       doc_version, doc_company, theme, mermaid_render_mode, inline_images)
output: ConversionResult (success, output_path, size_bytes, error)
side_effect: 在输出目录生成 .html / .docx / .pdf 文件

用法:
    from api import Converter

    converter = Converter()
    result = converter.convert_file("doc.md", format="html")
    print(result.output_path)

    batch = converter.convert_directory("./docs", format="html")
    print(f"成功: {batch.success}/{batch.total}, 索引: {batch.index_path}")
"""

import time
from pathlib import Path
from typing import Optional, Union, List
from dataclasses import dataclass, field

from exporters.html import HtmlExporter
from exporters.word import WordExporter
from exporters.pdf import PdfExporter
from batch_processor import BatchProcessor


@dataclass
class ConversionResult:
    """单文件转换结果"""
    input_path: str
    output_path: str
    format: str
    success: bool
    error: Optional[str] = None
    size_bytes: int = 0


@dataclass
class BatchConversionResult:
    """批量转换结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    files: List[ConversionResult] = field(default_factory=list)
    index_path: Optional[str] = None
    elapsed_seconds: float = 0.0


class Converter:
    """统一的文档转换器（程序化 API）

    支持单文件和目录批量转换，所有格式（HTML/Word/PDF）。

    用法:
        converter = Converter()
        result = converter.convert_file("doc.md", format="html")
        result = converter.convert_directory("./docs", format="html", generate_index=True)

    所有方法都是同步的。批量转换使用内部线程池。
    """

    SUPPORTED_FORMATS = ('word', 'html', 'pdf')

    def __init__(self, **default_options):
        self.default_options = default_options

    def convert_file(
        self,
        input_path: Union[str, Path],
        format: str = '',
        output_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> ConversionResult:
        """转换单个 Markdown 文件

        Args:
            input_path: .md 文件路径
            format: 输出格式 ('word' | 'html' | 'pdf')，默认从构造函数继承
            output_path: 输出文件路径，为 None 时自动生成
            **options: 覆盖默认选项 (theme, mermaid_render_mode, inline_images, doc_title 等)

        Returns:
            ConversionResult 包含 success/error/output_path/size_bytes
        """
        input_path = Path(input_path)
        format = format or self.default_options.get('format', 'html')
        merged = {**self.default_options, **options, 'format': format}

        try:
            if format not in self.SUPPORTED_FORMATS:
                return ConversionResult(
                    input_path=str(input_path),
                    output_path='',
                    format=format,
                    success=False,
                    error=f'Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}',
                )

            if format == 'html':
                exporter = HtmlExporter(**merged)
            elif format == 'word':
                exporter = WordExporter(**merged)
            else:
                exporter = PdfExporter(**merged)

            out = Path(output_path) if output_path else None
            success = exporter.convert_file(str(input_path), str(out) if out else None)

            if success:
                if out is None:
                    ext = '.docx' if format == 'word' else f'.{format}'
                    out = Path(exporter.get_output_path(str(input_path), ext))
                size = out.stat().st_size if out.exists() else 0
                return ConversionResult(
                    input_path=str(input_path),
                    output_path=str(out),
                    format=format,
                    success=True,
                    size_bytes=size,
                )
            else:
                return ConversionResult(
                    input_path=str(input_path),
                    output_path='',
                    format=format,
                    success=False,
                    error='Conversion failed (see logs)',
                )

        except Exception as e:
            return ConversionResult(
                input_path=str(input_path),
                output_path='',
                format=format,
                success=False,
                error=str(e),
            )

    def convert_directory(
        self,
        input_dir: Union[str, Path],
        format: str = '',
        output_dir: Optional[Union[str, Path]] = None,
        generate_index: bool = True,
        index_title: str = '文档索引',
        max_workers: int = 4,
        **options,
    ) -> BatchConversionResult:
        """转换目录中所有 Markdown 文件

        Args:
            input_dir: 包含 .md 文件的目录
            format: 目标格式
            output_dir: 输出目录，默认使用 input_dir
            generate_index: 自动生成 index.html（仅 HTML 格式）
            index_title: 索引页标题
            max_workers: 线程池大小
            **options: 覆盖选项

        Returns:
            BatchConversionResult 包含每个文件的结果和可选的 index_path
        """
        start = time.time()

        format = format or self.default_options.get('format', 'html')

        merged = {
            **self.default_options,
            **options,
            'format': format,
            'output_dir': str(output_dir) if output_dir else None,
            'max_workers': max_workers,
            'generate_index': generate_index and format == 'html',
            'index_title': index_title,
        }

        processor = BatchProcessor(**merged)
        raw = processor.process_directory(str(input_dir))

        files = []
        for f in raw.get('files', []):
            out_path = f.get('output', '')
            size = 0
            if out_path and Path(out_path).exists():
                size = Path(out_path).stat().st_size
            files.append(ConversionResult(
                input_path=f.get('input', ''),
                output_path=out_path,
                format=format,
                success=f.get('success', False),
                error=f.get('message') if not f.get('success') else None,
                size_bytes=size,
            ))

        actual_output_dir = Path(output_dir) if output_dir else Path(input_dir)
        index_path = actual_output_dir / 'index.html'

        return BatchConversionResult(
            total=raw.get('total', 0),
            success=raw.get('success', 0),
            failed=raw.get('failed', 0),
            files=files,
            index_path=str(index_path) if index_path.exists() else None,
            elapsed_seconds=round(time.time() - start, 2),
        )

    @classmethod
    def get_available_formats(cls) -> tuple:
        """返回支持的输出格式"""
        return cls.SUPPORTED_FORMATS
