"""Mermaid HTML 内嵌渲染

为浏览器端 mermaid.js 渲染提供 CDN 脚本和初始化配置。
用于在线预览模式：输出 <pre class="mermaid"> 代码块 + mermaid.js CDN。
"""


def get_mermaid_cdn_script() -> str:
    """获取 mermaid.js CDN <script> 标签"""
    return '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'


def get_mermaid_init_script(theme: str = "neutral") -> str:
    """获取 mermaid.initialize() 配置脚本"""
    return f"""<script>
document.addEventListener('DOMContentLoaded', function() {{
    mermaid.initialize({{
        startOnLoad: true,
        theme: '{theme}',
        securityLevel: 'loose',
        flowchart: {{ useMaxWidth: true, htmlLabels: true }},
    }});
}});
</script>"""
