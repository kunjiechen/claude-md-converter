"""主题模块"""

from .base import BaseTheme, ThemeRegistry
from .tech_doc import TechDocTheme

# 注册内置主题
ThemeRegistry.register(TechDocTheme)

__all__ = ["BaseTheme", "ThemeRegistry", "TechDocTheme"]
