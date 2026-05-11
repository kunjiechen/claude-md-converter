"""
格式转换器基类
定义转换器的通用接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path


class BaseConverter(ABC):
    """格式转换器基类"""

    def __init__(self, **options):
        """
        初始化转换器

        Args:
            **options: 转换选项
        """
        self.options = options
        self.template_path: Optional[str] = options.get('template') or options.get('css_template')
        self.output_dir: Optional[str] = options.get('output_dir')
        # 模板页眉动态字段
        self.doc_title: Optional[str] = options.get('doc_title')
        self.doc_number: Optional[str] = options.get('doc_number')
        self.doc_version: Optional[str] = options.get('doc_version')
        self.doc_department: Optional[str] = options.get('doc_department')
        self.doc_company: Optional[str] = options.get('doc_company')

    @abstractmethod
    def convert(self, ast: List[Dict[str, Any]], output_path: str) -> bool:
        """
        将AST转换为目标格式

        Args:
            ast: Markdown AST节点列表
            output_path: 输出文件路径

        Returns:
            转换是否成功
        """
        pass

    @abstractmethod
    def convert_file(self, input_path: str, output_path: str) -> bool:
        """
        转换Markdown文件

        Args:
            input_path: 输入Markdown文件路径
            output_path: 输出文件路径

        Returns:
            转换是否成功
        """
        pass

    def get_output_path(self, input_path: str, format_ext: str) -> str:
        """
        生成输出文件路径

        Args:
            input_path: 输入文件路径
            format_ext: 输出格式扩展名

        Returns:
            输出文件路径
        """
        input_file = Path(input_path)
        output_name = input_file.stem + format_ext

        if self.output_dir:
            output_dir = Path(self.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            return str(output_dir / output_name)
        else:
            return str(input_file.parent / output_name)

    def validate_input(self, input_path: str) -> bool:
        """
        验证输入文件

        Args:
            input_path: 输入文件路径

        Returns:
            文件是否有效
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        if not path.suffix.lower() == '.md':
            raise ValueError(f"输入文件不是Markdown文件: {input_path}")
        return True

    def log(self, message: str, level: str = "info"):
        """
        记录日志

        Args:
            message: 日志消息
            level: 日志级别
        """
        # TODO: 实现日志系统
        print(f"[{level.upper()}] {message}")