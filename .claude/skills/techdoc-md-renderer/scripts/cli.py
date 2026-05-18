"""
命令行接口
提供命令行工具用于Markdown转Word/PDF
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from api import Converter


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    解析命令行参数

    Args:
        args: 命令行参数列表

    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(
        description='Markdown转Word/PDF转换器',
        prog='md-converter'
    )

    parser.add_argument(
        'input',
        help='输入Markdown文件或文件夹路径'
    )

    parser.add_argument(
        '--format', '-f',
        choices=['word', 'pdf', 'html'],
        default='word',
        help='输出格式 (默认: word)'
    )

    parser.add_argument(
        '--output', '-o',
        help='输出目录；转换单个文件时也可传入完整输出文件路径'
    )

    parser.add_argument(
        '--template', '-t',
        help='Word模板文件路径 (.docx/.dotx) 或 CSS模板文件路径 (.css)'
    )

    parser.add_argument(
        '--doc-title',
        help='文档标题（替换模板页眉中的标题占位）'
    )

    parser.add_argument(
        '--doc-number',
        help='文件编号（替换模板页眉中的编号占位）'
    )

    parser.add_argument(
        '--doc-version',
        help='版本号（替换模板页眉中的版本占位）'
    )

    parser.add_argument(
        '--doc-department',
        help='制定部门（替换模板页眉中的部门占位）'
    )

    parser.add_argument(
        '--doc-company',
        help='公司名称（替换模板页眉中的公司名占位）'
    )

    parser.add_argument(
        '--theme',
        default='tech-doc',
        help='HTML/PDF主题 (默认: tech-doc)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='最大并行数 (默认: 4)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )

    parser.add_argument(
        '--mermaid-render',
        choices=['browser', 'server', 'auto'],
        default='auto',
        help='Mermaid渲染模式: browser(浏览器端) / server(服务器端) / auto(自动, 默认)'
    )

    parser.add_argument(
        '--inline-images',
        action='store_true',
        help='将本地图片 base64 内联到 HTML 中（生成真正的自包含单文件）'
    )

    parser.add_argument(
        '--include-cover',
        action='store_true',
        help='HTML/PDF 输出封面页；默认关闭以对齐 Word 的目录→修订→正文结构'
    )

    parser.add_argument(
        '--no-index',
        action='store_true',
        help='禁止自动生成目录索引页 index.html（仅目录输入时有效）'
    )

    parser.add_argument(
        '--index-title',
        default='文档索引',
        help='索引页面标题 (默认: 文档索引)'
    )

    parser.add_argument(
        '--quality-report',
        action='store_true',
        help='转换完成后生成 .quality.json 质量分析报告'
    )

    parser.add_argument(
        '--pipeline',
        choices=['v2'],
        default='v2',
        help='渲染管线: 仅支持 v2'
    )

    parser.add_argument(
        '--profile',
        choices=['automotive_formal_spec', 'chip_register_manual', 'lightweight_tech_note'],
        help='V2 文档 profile'
    )

    parser.add_argument(
        '--quality-gate',
        choices=['pass', 'review', 'fail'],
        default='review',
        help='V2 发布选择所需质量门禁级别 (默认: review)'
    )

    parser.add_argument(
        '--strict',
        action='store_true',
        help='V2 strict 模式：要求质量门禁通过'
    )

    parser.add_argument(
        '--report',
        action='store_true',
        help='V2/auto 模式输出 UnifiedRenderReport JSON'
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None):
    """
    主函数

    Args:
        args: 命令行参数列表
    """
    parsed_args = parse_args(args)

    # 准备选项
    options = {
        'format': parsed_args.format,
        'max_workers': parsed_args.max_workers,
        'verbose': parsed_args.verbose,
        'theme': parsed_args.theme,
    }

    if parsed_args.template:
        options['template'] = parsed_args.template
        options['css_template'] = parsed_args.template
    if parsed_args.doc_title:
        options['doc_title'] = parsed_args.doc_title
    if parsed_args.doc_number:
        options['doc_number'] = parsed_args.doc_number
    if parsed_args.doc_version:
        options['doc_version'] = parsed_args.doc_version
    if parsed_args.doc_department:
        options['doc_department'] = parsed_args.doc_department
    if parsed_args.doc_company:
        options['doc_company'] = parsed_args.doc_company

    # 新增：mermaid 渲染模式 & 图片内联 & 索引
    options['mermaid_render_mode'] = parsed_args.mermaid_render
    options['inline_images'] = parsed_args.inline_images
    options['include_cover'] = parsed_args.include_cover
    options['generate_index'] = not parsed_args.no_index
    options['index_title'] = parsed_args.index_title
    options['quality_report'] = parsed_args.quality_report
    options['pipeline'] = 'v2'
    if parsed_args.profile:
        options['profile'] = parsed_args.profile
        options['document_profile'] = parsed_args.profile
    options['quality_gate'] = parsed_args.quality_gate
    options['strict'] = parsed_args.strict
    options['report'] = parsed_args.report

    # 判断是文件还是目录
    input_path = Path(parsed_args.input)

    if input_path.is_file():
        # 转换单个文件
        output_target = Path(parsed_args.output) if parsed_args.output else None
        expected_suffix = {
            'word': '.docx',
            'html': '.html',
            'pdf': '.pdf',
        }[parsed_args.format]
        if output_target and output_target.suffix.lower() == expected_suffix:
            converter = Converter()
            converter_options = dict(options)
            converter_options.pop('format', None)
            result = converter.convert_file(
                input_path,
                format=parsed_args.format,
                output_path=output_target,
                **converter_options,
            )
            if result.success:
                print("转换成功")
                print(f"输出文件: {result.output_path}")
                _print_quality_gate(result.quality_status, result.quality_score, result.deliverable)
                _print_unified_result(result)
                if result.quality_report_path:
                    print(f"质量报告: {result.quality_report_path}")
                if result.quality_report_html_path:
                    print(f"可视化报告: {result.quality_report_html_path}")
            else:
                print(f"转换失败: {result.error or ''}", file=sys.stderr)
                sys.exit(1)
        else:
            converter = Converter()
            converter_options = dict(options)
            converter_options.pop('format', None)
            out = None
            if parsed_args.output:
                out_dir = Path(parsed_args.output)
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / f"{input_path.stem}{expected_suffix}"
            result = converter.convert_file(
                input_path,
                format=parsed_args.format,
                output_path=out,
                **converter_options,
            )
            if result.success:
                print("转换成功")
                print(f"输出文件: {result.output_path}")
                _print_quality_gate(result.quality_status, result.quality_score, result.deliverable)
                _print_unified_result(result)
            else:
                print(f"转换失败: {result.error or ''}", file=sys.stderr)
                sys.exit(1)

    elif input_path.is_dir():
        # 批量转换目录
        converter = Converter()
        converter_options = dict(options)
        converter_options.pop('format', None)
        results = converter.convert_directory(
            str(input_path),
            format=parsed_args.format,
            output_dir=parsed_args.output,
            generate_index=not parsed_args.no_index,
            index_title=parsed_args.index_title,
            max_workers=parsed_args.max_workers,
            **converter_options,
        )
        print(f"\n批量转换完成:")
        print(f"  总计: {results.total}")
        print(f"  成功: {results.success}")
        print(f"  失败: {results.failed}")

        # 显示失败文件
        failed_files = [f for f in results.files if not f.success]
        if failed_files:
            print(f"\n失败文件:")
            for file_info in failed_files:
                print(f"  - {Path(file_info.input_path).name}: {file_info.error}")

        if results.failed > 0:
            sys.exit(1)

    else:
        print(f"输入路径不存在: {parsed_args.input}", file=sys.stderr)
        sys.exit(1)


def _print_quality_gate(status, score, deliverable):
    if not status:
        return
    label = {
        'pass': '通过',
        'review': '需复核',
        'fail': '失败',
    }.get(status, status)
    deliverable_text = '可交付' if deliverable else '不建议直接交付'
    print(f"质量门禁: {label} / {score} 分 / {deliverable_text}")


def _print_unified_result(result):
    if not getattr(result, 'pipeline', None):
        return
    print(f"渲染管线: {result.pipeline}")
    if getattr(result, 'renderer_used', None):
        print(f"Renderer: {result.renderer_used}")
    if getattr(result, 'fidelity_level', None):
        print(f"Fidelity: {result.fidelity_level}")
    if getattr(result, 'unified_report_path', None):
        print(f"Unified Report: {result.unified_report_path}")


if __name__ == '__main__':
    main()
