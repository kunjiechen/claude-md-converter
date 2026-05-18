from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from content_loss_checker import check_ast


class Phase1NoSilentContentLossTest(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def test_mixed_text_image_paragraph_is_preserved(self):
        ast = self.parser.parse("请参考下图 ![系统框图](./arch.png) 完成接口连接。")
        self.assertEqual(len(ast), 1)
        node = ast[0]
        self.assertEqual(node["type"], "paragraph")
        self.assertIn("完成接口连接", node["content"])
        self.assertTrue(any(c.get("type") == "image" for c in node["children"]))
        self.assertTrue(any(c.get("type") == "text" and "请参考下图" in c.get("content", "") for c in node["children"]))

    def test_single_image_paragraph_keeps_legacy_image_node(self):
        ast = self.parser.parse("![单图](./single.png)")
        self.assertEqual(len(ast), 1)
        self.assertEqual(ast[0]["type"], "image")
        self.assertEqual(ast[0]["attributes"]["alt"], "单图")

    def test_raw_html_block_is_explicit_and_diagnosed(self):
        ast = self.parser.parse('<div class="warning">禁止带电插拔。</div>')
        self.assertEqual(len(ast), 1)
        self.assertEqual(ast[0]["type"], "raw_html")
        report = check_ast(ast)
        self.assertTrue(any(d.get("code") == "unsupported_raw_html_block" for d in report.diagnostics))


if __name__ == "__main__":
    unittest.main()
