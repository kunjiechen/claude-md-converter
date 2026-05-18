"""内联格式段 → HTML 渲染器"""

from typing import Dict, Any, List


class InlineRenderer:
    """将AST内联片段渲染为HTML"""

    def render(self, segments: List[Dict[str, Any]] = None, plain_text: str = "") -> str:
        """渲染内联片段为HTML字符串"""
        if not segments:
            return self._escape(plain_text)

        parts = []
        for seg in segments:
            html = self._render_segment(seg)
            if html:
                parts.append(html)
        return "".join(parts)

    def _render_segment(self, seg: Dict[str, Any]) -> str:
        seg_type = seg.get("type", "text")
        text = seg.get("content", "")

        if seg_type == "text":
            if not text:
                return ""
            out = self._escape(text)
            if seg.get("bold"):
                out = f"<strong>{out}</strong>"
            if seg.get("italic"):
                out = f"<em>{out}</em>"
            if seg.get("strikethrough"):
                out = f"<del>{out}</del>"
            if seg.get("underline"):
                out = f"<ins>{out}</ins>"
            return out

        elif seg_type == "code_inline":
            return f'<code class="code-inline">{self._escape(text)}</code>'

        elif seg_type == "link":
            href = seg.get("href", "")
            if href:
                return f'<a href="{self._escape_attr(href)}">{self._escape(text)}</a>'
            return self._escape(text)

        elif seg_type == "image":
            attrs = seg.get("attributes", {}) or {}
            src = seg.get("src", "") or attrs.get("src", "")
            alt = seg.get("alt", "") or attrs.get("alt", "")
            return f'<img src="{self._escape_attr(src)}" alt="{self._escape_attr(alt)}" class="inline-image">'

        elif seg_type == "footnote_ref":
            label = seg.get("label", "")
            return f'<sup class="footnote-ref"><a href="#fn-{self._escape_attr(label)}">[{self._escape(label)}]</a></sup>'

        elif seg_type == "math_inline":
            return f'<span class="math math--inline">\\({self._escape(text)}\\)</span>'

        elif seg_type == "kbd":
            return f"<kbd>{self._escape(text)}</kbd>"

        elif seg_type == "sub":
            return f"<sub>{self._escape(text)}</sub>"

        elif seg_type == "sup":
            return f"<sup>{self._escape(text)}</sup>"

        elif seg_type == "highlight":
            return f"<mark>{self._escape(text)}</mark>"

        elif seg_type in ("softbreak", "hardbreak"):
            return "<br>"

        return ""

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _escape_attr(text: str) -> str:
        return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
