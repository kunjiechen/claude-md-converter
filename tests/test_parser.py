"""
解析器单元测试
"""

import pytest
from src.md_converter.parser import MarkdownParser


class TestMarkdownParser:
    """Markdown解析器测试"""

    def setup_method(self):
        """测试前准备"""
        self.parser = MarkdownParser()

    def test_parse_heading(self):
        """测试标题解析"""
        text = "# 一级标题\n## 二级标题\n### 三级标题"
        result = self.parser.parse(text)

        assert len(result) == 3
        assert result[0]['type'] == 'heading'
        assert result[0]['level'] == 1
        assert result[0]['content'] == '一级标题'
        assert result[1]['level'] == 2
        assert result[2]['level'] == 3

    def test_parse_paragraph(self):
        """测试段落解析"""
        text = "这是第一个段落。\n\n这是第二个段落。"
        result = self.parser.parse(text)

        assert len(result) == 2
        assert result[0]['type'] == 'paragraph'
        assert result[0]['content'] == '这是第一个段落。'
        assert result[1]['type'] == 'paragraph'
        assert result[1]['content'] == '这是第二个段落。'

    def test_parse_unordered_list(self):
        """测试无序列表解析"""
        text = "- 项目1\n- 项目2\n- 项目3"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'list'
        assert result[0]['attributes']['ordered'] == False
        assert len(result[0]['children']) == 3

    def test_parse_ordered_list(self):
        """测试有序列表解析"""
        text = "1. 项目1\n2. 项目2\n3. 项目3"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'list'
        assert result[0]['attributes']['ordered'] == True
        assert len(result[0]['children']) == 3

    def test_parse_table(self):
        """测试表格解析"""
        text = "| 列1 | 列2 |\n|-----|-----|\n| 数据1 | 数据2 |"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'table'
        assert len(result[0]['children']) == 2  # 表头 + 数据行

    def test_parse_code_block(self):
        """测试代码块解析"""
        text = '```python\nprint("Hello")\n```'
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'code_block'
        assert result[0]['attributes']['language'] == 'python'
        assert 'print("Hello")' in result[0]['content']

    def test_parse_blockquote(self):
        """测试引用解析"""
        text = "> 这是引用内容"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'blockquote'
        assert len(result[0]['children']) == 1

    def test_parse_image(self):
        """测试图片解析"""
        text = "![图片描述](image.png)"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'image'
        assert result[0]['attributes']['src'] == 'image.png'
        assert result[0]['attributes']['alt'] == '图片描述'

    def test_parse_hr(self):
        """测试分割线解析"""
        text = "---"
        result = self.parser.parse(text)

        assert len(result) == 1
        assert result[0]['type'] == 'hr'

    def test_parse_complex_document(self):
        """测试复杂文档解析"""
        text = '''# 标题

段落内容

- 列表1
- 列表2

| A | B |
|---|---|
| 1 | 2 |

```code
content
```

> 引用

---
'''
        result = self.parser.parse(text)

        # 验证各种元素都被解析
        types = [node['type'] for node in result]
        assert 'heading' in types
        assert 'paragraph' in types
        assert 'list' in types
        assert 'table' in types
        assert 'code_block' in types
        assert 'blockquote' in types
        assert 'hr' in types

    def test_parse_file(self, sample_markdown_file):
        """测试文件解析"""
        result = self.parser.parse_file(str(sample_markdown_file))

        assert len(result) > 0
        assert result[0]['type'] == 'heading'
        assert result[0]['content'] == '测试文档'

    def test_parse_empty_text(self):
        """测试空文本解析"""
        result = self.parser.parse("")
        assert result == []

    def test_parse_whitespace_only(self):
        """测试纯空白文本解析"""
        result = self.parser.parse("   \n\n   ")
        assert result == []