"""主题基类与注册表"""

from abc import ABC, abstractmethod
from typing import Dict, Type, Optional
from pathlib import Path


class BaseTheme(ABC):
    """抽象主题基类"""

    name: str = "base"
    display_name: str = "Base Theme"
    description: str = ""

    @property
    @abstractmethod
    def css_tokens(self) -> str:
        """CSS 设计令牌（CSS 变量字符串）"""
        ...

    @property
    @abstractmethod
    def css_files(self) -> list:
        """CSS 文件路径列表（相对于 css/ 目录）"""
        ...

    @property
    def template_name(self) -> str:
        """Jinja2 模板名称"""
        return "document.html.j2"

    def get_context_defaults(self) -> dict:
        """返回默认的渲染上下文覆盖"""
        return {}

    def get_css(self, css_dir: Path) -> str:
        """加载并合并所有CSS文件，统一包装在单个 <style> 标签中"""
        parts = [self.css_tokens]
        for fname in self.css_files:
            fpath = css_dir / fname
            if fpath.exists():
                parts.append(fpath.read_text(encoding='utf-8'))
        return "<style>\n" + "\n".join(parts) + "\n</style>"


class ThemeRegistry:
    """主题注册表"""

    _themes: Dict[str, Type[BaseTheme]] = {}

    @classmethod
    def register(cls, theme_cls: Type[BaseTheme]):
        cls._themes[theme_cls.name] = theme_cls

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseTheme]]:
        return cls._themes.get(name)

    @classmethod
    def names(cls) -> list:
        return list(cls._themes.keys())

    @classmethod
    def default(cls) -> Optional[Type[BaseTheme]]:
        return cls._themes.get('tech-doc') or (list(cls._themes.values())[0] if cls._themes else None)
