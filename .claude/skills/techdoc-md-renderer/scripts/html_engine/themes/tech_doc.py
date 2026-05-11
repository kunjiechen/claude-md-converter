"""技术文档主题 — G-C045 公司规范风格"""

from .base import BaseTheme


class TechDocTheme(BaseTheme):
    """技术文档主题，遵循 G-C045 公司规范"""

    name = "tech-doc"
    display_name = "技术文档 (G-C045)"
    description = "符合公司G-C045规范的技术文档风格：楷体正文、黑白配色、正式排版"

    @property
    def css_tokens(self) -> str:
        return """
:root {
    /* 字体 */
    --font-body: "楷体", "KaiTi", serif;
    --font-heading: "黑体", "SimHei", sans-serif;
    --font-code: "Courier New", "Consolas", monospace;
    --font-table: "Microsoft YaHei", "微软雅黑", sans-serif;

    /* 字号 */
    --font-size-body: 12pt;
    --font-size-h1: 22pt;
    --font-size-h2: 16pt;
    --font-size-h3: 14pt;
    --font-size-h4: 12pt;
    --font-size-code: 10pt;
    --font-size-table: 10pt;
    --font-size-footnote: 9pt;

    /* 颜色 */
    --color-text: #000000;
    --color-text-secondary: #333333;
    --color-bg: #FFFFFF;
    --color-bg-code: #F5F5F5;
    --color-bg-table-header: #D9D9D9;
    --color-bg-math: #F0F4FF;
    --color-border: #808080;
    --color-border-light: #BFBFBF;
    --color-link: #0563C1;
    --color-figcaption: #808080;

    /* 间距 */
    --spacing-para: 6pt;
    --spacing-heading-top: 12pt;
    --spacing-heading-bottom: 6pt;
    --spacing-block: 12pt;
    --table-cell-padding: 4px 8px;
    --table-text-indent: 0;

    /* 表格 */
    --table-border: 0.5px solid var(--color-border);

    /* 页面 */
    --page-width: 210mm;
    --page-margin: 2.5cm;
}"""

    @property
    def css_files(self) -> list:
        return ["base.css", "tech_doc.css", "components.css"]

    def get_context_defaults(self) -> dict:
        return {
            "lang": "zh-CN",
            "meta_viewport": "width=device-width, initial-scale=1.0",
        }
