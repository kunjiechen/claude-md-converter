"""
集成测试
"""

import pytest
from pathlib import Path
from src.md_converter.batch_processor import BatchProcessor


class TestBatchProcessor:
    """批量处理器集成测试"""

    def setup_method(self):
        """测试前准备"""
        pass

    def test_process_directory_word(self, sample_markdown_files, temp_dir):
        """测试目录批量处理Word"""
        # 获取测试文件所在目录
        test_dir = sample_markdown_files[0].parent
        output_dir = temp_dir / "output"

        processor = BatchProcessor(format='word', output_dir=str(output_dir), verbose=True)
        results = processor.process_directory(str(test_dir))

        assert results['total'] == 3
        assert results['success'] == 3
        assert results['failed'] == 0

        # 验证输出文件
        assert output_dir.exists()
        output_files = list(output_dir.glob("*.docx"))
        assert len(output_files) == 3

    def test_process_directory_pdf(self, sample_markdown_files, temp_dir):
        """测试目录批量处理PDF"""
        # 获取测试文件所在目录
        test_dir = sample_markdown_files[0].parent
        output_dir = temp_dir / "output"

        processor = BatchProcessor(format='pdf', output_dir=str(output_dir), verbose=True)
        results = processor.process_directory(str(test_dir))

        assert results['total'] == 3
        assert results['success'] == 3
        assert results['failed'] == 0

        # 验证输出文件
        assert output_dir.exists()
        output_files = list(output_dir.glob("*.pdf"))
        assert len(output_files) == 3

    def test_process_files(self, sample_markdown_files, temp_dir):
        """测试指定文件批量处理"""
        output_dir = temp_dir / "output"

        processor = BatchProcessor(format='word', output_dir=str(output_dir), verbose=True)
        results = processor.process_files(
            [str(f) for f in sample_markdown_files[:2]],
            str(output_dir)
        )

        assert results['total'] == 2
        assert results['success'] == 2
        assert results['failed'] == 0

    def test_process_with_log(self, sample_markdown_files, temp_dir):
        """测试带日志的批量处理"""
        # 获取测试文件所在目录
        test_dir = sample_markdown_files[0].parent
        output_dir = temp_dir / "output"
        log_file = temp_dir / "test.log.json"

        processor = BatchProcessor(
            format='word',
            output_dir=str(output_dir),
            log_file=str(log_file),
            verbose=True
        )
        results = processor.process_directory(str(test_dir))

        assert results['total'] == 3
        assert results['success'] == 3

        # 验证日志文件
        assert log_file.exists()

        # 检查日志摘要
        log_summary = processor.get_log_summary()
        assert log_summary['error_count'] == 0

    def test_process_nonexistent_directory(self, temp_dir):
        """测试不存在的目录"""
        nonexistent_dir = temp_dir / "nonexistent"

        processor = BatchProcessor(format='word', output_dir=str(temp_dir / "output"))

        with pytest.raises(FileNotFoundError):
            processor.process_directory(str(nonexistent_dir))

    def test_process_empty_directory(self, temp_dir):
        """测试空目录"""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        processor = BatchProcessor(format='word', output_dir=str(temp_dir / "output"), verbose=True)
        results = processor.process_directory(str(empty_dir))

        assert results['total'] == 0
        assert results['success'] == 0
        assert results['failed'] == 0

    def test_process_with_invalid_files(self, temp_dir):
        """测试包含无效文件的目录"""
        # 创建测试目录
        test_dir = temp_dir / "test"
        test_dir.mkdir()

        # 创建有效文件
        valid_file = test_dir / "valid.md"
        valid_file.write_text("# 有效文件", encoding='utf-8')

        # 创建无效文件（非Markdown）
        invalid_file = test_dir / "invalid.txt"
        invalid_file.write_text("这不是Markdown文件", encoding='utf-8')

        output_dir = temp_dir / "output"

        processor = BatchProcessor(format='word', output_dir=str(output_dir), verbose=True)
        results = processor.process_directory(str(test_dir))

        # 应该只处理Markdown文件
        assert results['total'] == 1
        assert results['success'] == 1

    def test_process_with_parallel_workers(self, sample_markdown_files, temp_dir):
        """测试并行处理"""
        # 获取测试文件所在目录
        test_dir = sample_markdown_files[0].parent
        output_dir = temp_dir / "output"

        processor = BatchProcessor(
            format='word',
            output_dir=str(output_dir),
            max_workers=2,
            verbose=True
        )
        results = processor.process_directory(str(test_dir))

        assert results['total'] == 3
        assert results['success'] == 3
        assert results['failed'] == 0


class TestEndToEnd:
    """端到端测试"""

    def test_markdown_to_word_pipeline(self, sample_markdown_file, temp_dir):
        """测试完整的Markdown到Word转换流程"""
        from src.md_converter.parser import MarkdownParser
        from src.md_converter.word_converter import WordConverter

        # 解析
        parser = MarkdownParser()
        ast = parser.parse_file(str(sample_markdown_file))

        assert len(ast) > 0

        # 转换
        output_path = temp_dir / "output.docx"
        converter = WordConverter()
        result = converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_markdown_to_pdf_pipeline(self, sample_markdown_file, temp_dir):
        """测试完整的Markdown到PDF转换流程"""
        from src.md_converter.parser import MarkdownParser
        from src.md_converter.pdf_converter_reportlab import PDFConverterReportlab

        # 解析
        parser = MarkdownParser()
        ast = parser.parse_file(str(sample_markdown_file))

        assert len(ast) > 0

        # 转换
        output_path = temp_dir / "output.pdf"
        converter = PDFConverterReportlab()
        result = converter.convert(ast, str(output_path))

        assert result == True
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_batch_pipeline(self, sample_markdown_files, temp_dir):
        """测试完整的批量转换流程"""
        # 获取测试文件所在目录
        test_dir = sample_markdown_files[0].parent
        output_dir = temp_dir / "output"
        log_file = temp_dir / "log.json"

        # 批量处理
        processor = BatchProcessor(
            format='word',
            output_dir=str(output_dir),
            log_file=str(log_file),
            verbose=True
        )
        results = processor.process_directory(str(test_dir))

        # 验证结果
        assert results['total'] == 3
        assert results['success'] == 3
        assert results['failed'] == 0

        # 验证输出文件
        assert output_dir.exists()
        output_files = list(output_dir.glob("*.docx"))
        assert len(output_files) == 3

        # 验证日志
        assert log_file.exists()
        log_summary = processor.get_log_summary()
        assert log_summary['error_count'] == 0