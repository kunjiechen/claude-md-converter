"""
目录索引生成器

为多文件 HTML 输出生成 index.html 索引页，形成可浏览的文档站点。
"""

import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape


class IndexGenerator:
    """多文件文档站点的索引页生成器"""

    def __init__(self, title: str = "文档索引", template_dir: Optional[Path] = None):
        self.title = title
        if template_dir is None:
            template_dir = Path(__file__).parent / 'html_engine' / 'templates'
        self._jinja = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
        )
        self._template = self._jinja.get_template('index.html.j2')

    def generate(self, html_files: List[Path], output_dir: Path,
                 title: str = None, description: str = None) -> Path:
        """在 output_dir 中生成 index.html，链接到所有 html_files"""
        entries = []
        for fpath in sorted(html_files):
            doc_title = self._extract_title(fpath)
            entries.append({
                'title': doc_title,
                'href': fpath.name,
                'meta': f"{self._format_size(fpath)} &middot; {datetime.now().strftime('%Y-%m-%d')}",
            })

        html = self._template.render(
            title=title or self.title,
            description=description or '',
            entries=entries,
        )

        index_path = output_dir / 'index.html'
        index_path.write_text(html, encoding='utf-8')
        return index_path

    @staticmethod
    def _extract_title(html_path: Path) -> str:
        """从 HTML 文件中提取标题：<title> → 第一个 <h1> → stem"""
        try:
            text = html_path.read_text(encoding='utf-8')
            m = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
            if m:
                return m.group(1).strip()
            m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.DOTALL)
            if m:
                return re.sub(r'<[^>]+>', '', m.group(1)).strip()
        except Exception:
            pass
        return html_path.stem

    @staticmethod
    def _format_size(path: Path) -> str:
        size = path.stat().st_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
