"""Word 自定义样式定义 & 段落分类规则

将 HTML 段落内容和结构映射到语义化 Word 样式（正文2/正文3/小标题/规范/公式），
替代原来所有内容映射到单一 Normal 样式的方式。

样式定义用于在文档中自动创建缺失的样式（模板已提供时跳过）。
段落分类规则基于 HTML 标签的文本内容和结构模式。
"""

import re
from typing import Dict, Any, Optional

from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from bs4 import Tag

# ============================================================
# 样式定义
# ============================================================

STYLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    '正文2': {
        # 完全继承 Normal 的字体/字号/间距，仅作为语义标签
        'description': '默认正文样式，替代 Normal',
    },
    '正文3': {
        'first_line_indent': Cm(0.74),
        'description': '辅助说明/补充注释，首行缩进',
    },
    '短正文': {
        'space_after': Pt(3),
        'line_spacing': 1.15,
        'description': '单句短段落，避免两端对齐和过大段后距',
    },
    '紧凑正文': {
        'space_after': Pt(2),
        'line_spacing': 1.1,
        'description': '连续短段落组，压缩段间距',
    },
    '小标题': {
        'bold': True,
        'description': '段落内加粗子标题',
    },
    '规范': {
        'font_name': 'Consolas',    # Latin 等宽，CJK 继承 Normal
        'font_size': Pt(10.5),
        'first_line_indent': Cm(0.74),
        'description': '命名规范/语法条目',
    },
    '公式': {
        'bold': True,
        'alignment': WD_ALIGN_PARAGRAPH.CENTER,
        'description': '居中公式/结构定义',
    },
}


def ensure_styles(doc) -> int:
    """确保文档中存在所有自定义样式，不存在则创建。返回新创建的样式数量。

    当文档从模板创建时，模板可能已包含这些样式，跳过已存在的。
    """
    created = 0
    for style_name, props in STYLE_DEFINITIONS.items():
        try:
            doc.styles[style_name]
        except KeyError:
            _create_paragraph_style(doc, style_name, props)
            created += 1
    return created


def _create_paragraph_style(doc, style_name: str, props: dict):
    """基于 Normal 创建新的段落样式。

    只设置 props 中明确配置的属性，字体/字号/间距等未配置项从 Normal 继承。
    """
    base = doc.styles['Normal']
    style = doc.styles.add_style(style_name, 1)  # WD_STYLE_TYPE.PARAGRAPH = 1
    style.base_style = base

    font = style.font
    if props.get('font_name'):
        font.name = props['font_name']
    if props.get('font_size'):
        font.size = props['font_size']
    if props.get('bold'):
        font.bold = True

    pf = style.paragraph_format
    if props.get('alignment') is not None:
        pf.alignment = props['alignment']
    if props.get('first_line_indent') is not None:
        pf.first_line_indent = props['first_line_indent']
    if props.get('space_after') is not None:
        pf.space_after = props['space_after']
    if props.get('line_spacing') is not None:
        pf.line_spacing = props['line_spacing']


# ============================================================
# 段落分类规则
# ============================================================

# 命名规范语法模式：含 <> 角括号 + _ 下划线
_SPEC_PATTERN = re.compile(r'&lt;[^&]+&gt;.*_|_.*&lt;[^&]+&gt;|<[^>]+>.*_.*<[^>]+>')

# 辅助文本前缀模式
_NOTE_PREFIX = re.compile(r'^(注意|注|例如|示例|参考|说明)[：:]')

# 代码块中的规范语法行模式：行内包含 <> 符号 + 下划线的命名约定
_CODE_SPEC_LINE = re.compile(r'^\s*(&lt;|<)[^&>]+(&gt;|>).*[_]|[_].*(&lt;|<)[^&>]+(&gt;|>)')

# 数学公式模式
_FORMULA_PATTERN = re.compile(r'\$\$.*\$\$|\\\[.*\\\]')


def _is_spec_code_line(text: str) -> bool:
    """判断代码块中的单行是否为规范语法条目（非实际代码）

    规范语法特征：
    - 含 &lt;...&gt;（HTML 转义）或 <...>（原始）命名约定
    - 含下划线连接标识符段
    - 不含明显的 C 代码特征（分号结尾除外，typedef 行可以有分号）
    """
    text = text.strip()
    if not text:
        return False

    # 排除纯代码特征行
    code_indicators = [
        r'^\s*#',           # 预处理器指令
        r'^\s*//',          # 注释
        r'^\s*/\*',         # 块注释
        r'^\s*\*',          # 注释续行
        r'^\s*\}',          # 闭合大括号
        r'^\s*\{',          # 开放大括号（单独一行）
        r';\s*$',           # 以分号结尾（代码语句）
    ]
    for pat in code_indicators:
        if re.match(pat, text):
            return False

    # 检测规范语法特征：<> 命名约定 + 下划线
    # 如：<Id>_<pp>{<Dd>}1-n_<xx><dt>
    angle_count = len(re.findall(r'&lt;|&gt;|<|>', text))
    has_underscore = '_' in text
    has_brace = '{' in text or '}' in text
    has_square = '[' in text or ']' in text

    if angle_count >= 2 and has_underscore:
        return True
    if angle_count >= 4 and (has_underscore or has_brace or has_square):
        return True

    # 简单类型/变量定义行：如 "uint8 unsigned integer" 或 "float32 float"
    words = text.split()
    if 2 <= len(words) <= 5 and re.match(r'^\w+\s+\w[\w\s]*$', text):
        return True

    return False


def _is_spec_paragraph(text: str) -> bool:
    """判断普通段落文本是否为规范条目"""
    text = text.strip()
    if not text:
        return False

    # 检测 HTML 转义后的角括号 + 下划线
    escaped_spec = bool(re.search(r'&lt;[^&]+&gt;.*_|_.*&lt;[^&]+&gt;', text))
    if escaped_spec:
        return True

    # 检测原始角括号 + 下划线（非转义，如直接写在 HTML 中）
    raw_spec = bool(re.search(r'<[A-Za-z][^>]*>.*_', text))
    if raw_spec:
        return True

    return False


def _is_sub_heading(tag: Tag) -> bool:
    """判断段落是否为加粗子标题

    特征：段落内只有一个 <strong> 子元素，且文本较短。
    """
    # 获取所有直接子元素
    children = [c for c in tag.children if c.name is not None or str(c).strip()]
    strong_children = [c for c in children if c.name == 'strong']

    if len(strong_children) != 1:
        return False

    strong = strong_children[0]
    strong_text = strong.get_text(strip=True)

    # 子标题文本特征：较短，不含句子
    if len(strong_text) > 50:
        return False

    # 排除以粗体开头的正常句子（粗体后还有大量文本）
    total_text = tag.get_text(strip=True)
    if len(total_text) > len(strong_text) * 2.5:
        return False

    return True


def classify_paragraph(tag: Tag) -> str:
    """根据 HTML 标签的内容和结构返回 Word 样式名

    优先级：
    1. 公式段落
    2. 小标题（单 strong + 短文本）
    3. 规范条目（<> + _ 命名约定）
    4. 辅助说明（注意/注/例如 开头 + 短文本）
    5. 正文2（默认）
    """
    classes = set(tag.get('class', []))
    if 'paragraph--compact' in classes or 'paragraph--grouped' in classes:
        return '紧凑正文'
    if 'paragraph--short' in classes or 'paragraph--clause' in classes:
        return '短正文'
    if 'paragraph--note' in classes:
        return '正文3'

    text = tag.get_text(strip=False)

    # 1. 公式模式 $$...$$
    if _FORMULA_PATTERN.search(text):
        return '公式'

    # 2. 小标题
    if _is_sub_heading(tag):
        return '小标题'

    # 3. 规范条目
    if _is_spec_paragraph(text):
        return '规范'

    # 4. 辅助说明
    stripped = text.strip()
    if _NOTE_PREFIX.match(stripped) and len(stripped) < 120:
        return '正文3'

    # 5. 默认正文
    return '正文2'


def classify_code_block(code_text: str) -> Optional[str]:
    """判断整个代码块的内容是否为规范语法（而非实际代码）

    如果超过 40% 的非空行匹配规范语法模式，返回 '规范'；
    否则返回 None（需要逐行混合分类）。
    """
    lines = [l for l in code_text.split('\n') if l.strip()]
    if not lines:
        return None

    spec_lines = sum(1 for l in lines if _is_spec_code_line(l))
    ratio = spec_lines / len(lines)

    if ratio >= 0.4:
        return '规范'
    return None


def classify_code_line(text: str) -> str:
    """对代码块中的单行进行分类，返回样式名。

    用于混合内容代码块（spec 行占比不足 40%），逐行判断。
    规范语法行 → '规范'，其余 → '正文2'。
    """
    text = text.strip()
    if not text:
        return '正文2'

    if _is_spec_code_line(text):
        return '规范'
    return '正文2'
