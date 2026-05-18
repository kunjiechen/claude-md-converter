from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.model import (
    CodeBlock,
    Diagram,
    Document,
    Figure,
    ImageRun,
    Paragraph,
    RawHtmlBlock,
    Table,
    TextRun,
    node_to_dict,
)
from core.normalize import ast_to_document, document_to_ast


class Phase2DocumentModelTest(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def model_from_markdown(self, text: str) -> Document:
        return ast_to_document(self.parser.parse(text), source_hint="unit-test.md")

    def test_mixed_text_image_paragraph_preserves_inline_structure(self):
        doc = self.model_from_markdown("请参考下图 ![系统框图](./arch.png) 完成接口连接。")
        self.assertIsInstance(doc.blocks[0], Paragraph)
        para = doc.blocks[0]
        self.assertTrue(any(isinstance(c, TextRun) and "请参考下图" in c.text for c in para.children))
        self.assertTrue(any(isinstance(c, ImageRun) and c.src == "./arch.png" for c in para.children))
        self.assertTrue(any(isinstance(c, TextRun) and "完成接口连接" in c.text for c in para.children))

    def test_single_image_becomes_figure(self):
        doc = self.model_from_markdown("![单图](./single.png)")
        self.assertIsInstance(doc.blocks[0], Figure)
        self.assertEqual(doc.blocks[0].image.src, "./single.png")
        self.assertEqual(doc.blocks[0].image.alt, "单图")

    def test_raw_html_block_is_preserved_with_diagnostic(self):
        doc = self.model_from_markdown('<div class="warning">禁止带电插拔。</div>')
        self.assertIsInstance(doc.blocks[0], RawHtmlBlock)
        self.assertIn("禁止带电插拔", doc.blocks[0].text_fallback)
        self.assertTrue(any(d.get("code") == "unsupported_raw_html_block" for d in doc.blocks[0].diagnostics))

    def test_table_structure_enters_document_model(self):
        doc = self.model_from_markdown(
            "| 名称 | 说明 |\n"
            "| ---- | ---- |\n"
            "| ENABLE | 使能控制 |\n"
        )
        table = doc.blocks[0]
        self.assertIsInstance(table, Table)
        self.assertEqual(len(table.rows), 2)
        self.assertEqual(len(table.rows[0].cells), 2)
        self.assertTrue(table.rows[0].header)
        self.assertEqual(table.rows[1].cells[0].text, "ENABLE")

    def test_code_block_identity_is_preserved(self):
        doc = self.model_from_markdown("```c\nuint8_t value = read_reg(0x00);\n```")
        self.assertIsInstance(doc.blocks[0], CodeBlock)
        self.assertEqual(doc.blocks[0].language, "c")
        self.assertIn("read_reg", doc.blocks[0].code)

    def test_mermaid_code_block_becomes_diagram(self):
        doc = self.model_from_markdown("```mermaid\ngraph TD\nA --> B\n```")
        self.assertIsInstance(doc.blocks[0], Diagram)
        self.assertEqual(doc.blocks[0].diagram_type, "mermaid")
        self.assertEqual(doc.blocks[0].subtype, "flowchart")

    def test_legacy_bridge_roundtrip_keeps_core_shapes(self):
        ast = self.parser.parse(
            "# 标题\n\n"
            "请参考 ![图](./a.png) 文本。\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "```c\nint main(void) { return 0; }\n```\n"
        )
        doc = ast_to_document(ast, source_hint="roundtrip.md")
        bridged = document_to_ast(doc)
        self.assertEqual(bridged[0]["type"], "heading")
        self.assertEqual(bridged[1]["type"], "paragraph")
        self.assertTrue(any(c.get("type") == "image" for c in bridged[1]["children"]))
        self.assertEqual(bridged[2]["type"], "table")
        self.assertEqual(bridged[3]["type"], "code_block")

    def test_model_is_serializable(self):
        doc = self.model_from_markdown("# 标题\n\n正文")
        payload = node_to_dict(doc)
        self.assertEqual(payload["node_type"], "Document")
        self.assertEqual(payload["blocks"][0]["node_type"], "Heading")


if __name__ == "__main__":
    unittest.main()
