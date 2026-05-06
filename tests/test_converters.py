"""
转换器单元测试
"""

import pytest
from pathlib import Path
from src.md_converter.parser import MarkdownParser
from src.md_converter.word_converter import WordConverter
from src.md_converter.pdf_converter_reportlab import PDFConverterReportlab


class TestWordConverter:
    """Word转换器测试"""

    def setup_method(self):
        """测试前准备"""
        self.parser = MarkdownParser()
        self.converter = WordConverter()

    def test_convert_heading(self, temp_dir):
        """测试标题转换"""
        ast = [{'type': 'heading', 'content': '测试标题', 'level': 1, 'children': [], 'attributes': {}}]
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_paragraph(self, temp_dir):
        """测试段落转换"""
        ast = [{'type': 'paragraph', 'content': '测试段落', 'children': [], 'attributes': {}}]
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_list(self, temp_dir):
        """测试列表转换"""
        ast = [{
            'type': 'list',
            'content': '',
            'children': [
                {'type': 'list_item', 'content': '', 'children': [
                    {'type': 'paragraph', 'content': '项目1', 'children': [], 'attributes': {}}
                ], 'attributes': {}},
                {'type': 'list_item', 'content': '', 'children': [
                    {'type': 'paragraph', 'content': '项目2', 'children': [], 'attributes': {}}
                ], 'attributes': {}}
            ],
            'attributes': {'ordered': False}
        }]
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_table(self, temp_dir):
        """测试表格转换"""
        ast = [{
            'type': 'table',
            'content': '',
            'children': [
                {'type': 'table_row', 'content': '', 'children': [
                    {'type': 'table_cell', 'content': '列1', 'children': [], 'attributes': {}},
                    {'type': 'table_cell', 'content': '列2', 'children': [], 'attributes': {}}
                ], 'attributes': {}},
                {'type': 'table_row', 'content': '', 'children': [
                    {'type': 'table_cell', 'content': '数据1', 'children': [], 'attributes': {}},
                    {'type': 'table_cell', 'content': '数据2', 'children': [], 'attributes': {}}
                ], 'attributes': {}}
            ],
            'attributes': {}
        }]
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_code_block(self, temp_dir):
        """测试代码块转换"""
        ast = [{
            'type': 'code_block',
            'content': 'print("Hello")',
            'children': [],
            'attributes': {'language': 'python'}
        }]
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_file(self, sample_markdown_file, temp_dir):
        """测试文件转换"""
        output_path = temp_dir / "test.docx"

        result = self.converter.convert_file(str(sample_markdown_file), str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_empty_ast(self, temp_dir):
        """测试空AST转换"""
        ast = []
        output_path = temp_dir / "test.docx"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()


class TestPDFConverter:
    """PDF转换器测试"""

    def setup_method(self):
        """测试前准备"""
        self.parser = MarkdownParser()
        self.converter = PDFConverterReportlab()

    def test_convert_heading(self, temp_dir):
        """测试标题转换"""
        ast = [{'type': 'heading', 'content': '测试标题', 'level': 1, 'children': [], 'attributes': {}}]
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_paragraph(self, temp_dir):
        """测试段落转换"""
        ast = [{'type': 'paragraph', 'content': '测试段落', 'children': [], 'attributes': {}}]
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_list(self, temp_dir):
        """测试列表转换"""
        ast = [{
            'type': 'list',
            'content': '',
            'children': [
                {'type': 'list_item', 'content': '', 'children': [
                    {'type': 'paragraph', 'content': '项目1', 'children': [], 'attributes': {}}
                ], 'attributes': {}},
                {'type': 'list_item', 'content': '', 'children': [
                    {'type': 'paragraph', 'content': '项目2', 'children': [], 'attributes': {}}
                ], 'attributes': {}}
            ],
            'attributes': {'ordered': False}
        }]
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_table(self, temp_dir):
        """测试表格转换"""
        ast = [{
            'type': 'table',
            'content': '',
            'children': [
                {'type': 'table_row', 'content': '', 'children': [
                    {'type': 'table_cell', 'content': '列1', 'children': [], 'attributes': {}},
                    {'type': 'table_cell', 'content': '列2', 'children': [], 'attributes': {}}
                ], 'attributes': {}},
                {'type': 'table_row', 'content': '', 'children': [
                    {'type': 'table_cell', 'content': '数据1', 'children': [], 'attributes': {}},
                    {'type': 'table_cell', 'content': '数据2', 'children': [], 'attributes': {}}
                ], 'attributes': {}}
            ],
            'attributes': {}
        }]
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_code_block(self, temp_dir):
        """测试代码块转换"""
        ast = [{
            'type': 'code_block',
            'content': 'print("Hello")',
            'children': [],
            'attributes': {'language': 'python'}
        }]
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_file(self, sample_markdown_file, temp_dir):
        """测试文件转换"""
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert_file(str(sample_markdown_file), str(output_path))

        assert result == True
        assert output_path.exists()

    def test_convert_empty_ast(self, temp_dir):
        """测试空AST转换"""
        ast = []
        output_path = temp_dir / "test.pdf"

        result = self.converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()