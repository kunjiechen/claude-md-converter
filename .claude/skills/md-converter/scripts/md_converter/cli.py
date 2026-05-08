"""
命令行接口
提供命令行工具用于Markdown转Word/PDF
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .batch_processor import BatchProcessor


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
        choices=['word', 'pdf'],
        default='word',
        help='输出格式 (默认: word)'
    )

    parser.add_argument(
        '--output', '-o',
        help='输出目录 (默认: 与输入相同目录)'
    )

    parser.add_argument(
        '--template', '-t',
        help='Word模板文件路径 (.dotx) 或 CSS模板文件路径 (.css)'
    )

    parser.add_argument(
        '--font',
        default='宋体',
        help='默认字体 (默认: 宋体)'
    )

    parser.add_argument(
        '--font-size',
        type=int,
        default=12,
        help='默认字号 (默认: 12)'
    )

    parser.add_argument(
        '--enable-pdf',
        action='store_true',
        default=False,
        help='启用PDF转换功能（默认关闭）'
    )

    parser.add_argument(
        '--page-size',
        default='A4',
        help='PDF页面大小 (默认: A4)'
    )

    parser.add_argument(
        '--margin',
        default='2.5cm',
        help='PDF页边距 (默认: 2.5cm)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='最大并行数 (默认: 4)'
    )

    parser.add_argument(
        '--log-file', '-l',
        help='日志文件路径 (JSON格式)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细输出'
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None):
    """
    主函数

    Args:
        args: 命令行参数列表
    """
    parsed_args = parse_args(args)

    # 检查PDF功能是否启用
    if parsed_args.format == 'pdf' and not parsed_args.enable_pdf:
        print("错误：PDF功能当前已关闭，请使用 --enable-pdf 参数启用", file=sys.stderr)
        print("示例：md-converter input.md --format pdf --enable-pdf", file=sys.stderr)
        sys.exit(1)

    # 准备选项
    options = {
        'format': parsed_args.format,
        'font': parsed_args.font,
        'font_size': parsed_args.font_size,
        'page_size': parsed_args.page_size,
        'margin': parsed_args.margin,
        'max_workers': parsed_args.max_workers,
        'verbose': parsed_args.verbose,
    }

    if parsed_args.template:
        options['css_template'] = parsed_args.template

    if parsed_args.output:
        options['output_dir'] = parsed_args.output

    if parsed_args.log_file:
        options['log_file'] = parsed_args.log_file

    # 判断是文件还是目录
    input_path = Path(parsed_args.input)

    if input_path.is_file():
        # 转换单个文件
        processor = BatchProcessor(**options)
        result = processor.process_files([str(input_path)], parsed_args.output)

        if result['success'] > 0:
            print(f"转换成功")
        else:
            print("转换失败", file=sys.stderr)
            sys.exit(1)

    elif input_path.is_dir():
        # 批量转换目录
        processor = BatchProcessor(**options)
        results = processor.process_directory(str(input_path))

        print(f"\n批量转换完成:")
        print(f"  总计: {results['total']}")
        print(f"  成功: {results['success']}")
        print(f"  失败: {results['failed']}")

        # 显示失败文件
        failed_files = [f for f in results['files'] if not f['success']]
        if failed_files:
            print(f"\n失败文件:")
            for file_info in failed_files:
                print(f"  - {Path(file_info['input']).name}: {file_info['message']}")

        # 显示日志摘要
        log_summary = processor.get_log_summary()
        if log_summary['error_count'] > 0:
            print(f"\n日志统计:")
            print(f"  错误: {log_summary['error_count']}")
            print(f"  警告: {log_summary['warning_count']}")

        if results['failed'] > 0:
            sys.exit(1)

    else:
        print(f"输入路径不存在: {parsed_args.input}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()