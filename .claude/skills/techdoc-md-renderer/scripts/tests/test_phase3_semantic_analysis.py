from pathlib import Path
import tempfile
import sys
import unittest
from typing import Optional


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.normalize import ast_to_document
from core.semantic import analyze_document


class Phase3SemanticAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def analyze(self, markdown: str, *, base_path: Optional[Path] = None):
        ast = self.parser.parse(markdown)
        doc = ast_to_document(ast, source_hint="semantic-test.md")
        report = analyze_document(doc, base_path=base_path)
        return doc, report

    def table_kind(self, markdown: str) -> str:
        _, report = self.analyze(markdown)
        self.assertTrue(report.tables)
        self.assertTrue(report.tables[0].evidence)
        return report.tables[0].kind

    def test_table_analyzer_detects_register_bitfield_interface_and_generic(self):
        self.assertEqual(self.table_kind(
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | Control register |\n"
        ), "register")

        self.assertEqual(self.table_kind(
            "<!-- table: bitfield -->\n"
            "| Bits | Field | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| [7:4] | MODE | RW | 0 | 工作模式 |\n"
        ), "bitfield")

        self.assertEqual(self.table_kind(
            "<!-- table: interface -->\n"
            "| 元素名称 | 基本结构 | 描述 |\n"
            "| --- | --- | --- |\n"
            "| RequestId | `<Id>` | 请求标识 |\n"
        ), "interface")

        _, report = self.analyze(
            "| A | B | C | D | E |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| one | two | three | four | five |\n"
        )
        self.assertEqual(report.tables[0].kind, "generic")
        self.assertTrue(any(d.get("code") == "low_confidence_table_classification" for d in report.tables[0].diagnostics))

    def test_header_analysis_preserves_parser_header_information(self):
        _, report = self.analyze(
            "| 名称 | 说明 |\n"
            "| --- | --- |\n"
            "| ENABLE | 使能 |\n"
        )
        self.assertEqual(report.headers[0].kind, "reliable")
        self.assertTrue(any(e.code == "parser_header" and e.value is True for e in report.headers[0].evidence))

    def test_paragraph_analysis_reports_reason_codes(self):
        _, report = self.analyze(
            "注意：禁止带电插拔。\n\n"
            "<!-- prose: preserve -->\n\n"
            "这个段落需要保持原始间距。\n\n"
            "<!-- /prose -->\n"
        )
        kinds = [p.kind for p in report.paragraphs]
        self.assertIn("note", kinds)
        self.assertIn("preserve", kinds)
        self.assertTrue(all(any(e.code == "reason_code" for e in p.evidence) for p in report.paragraphs))

    def test_document_profile_detects_chip_register_manual(self):
        _, report = self.analyze(
            "# 芯片寄存器手册\n\n"
            "本章描述 register offset bit field reset access。\n\n"
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | Control register |\n"
        )
        self.assertEqual(report.document_profile.kind, "chip_register_manual")
        self.assertGreaterEqual(report.document_profile.confidence, 0.60)

    def test_document_profile_detects_formal_naming_spec_without_revision_table(self):
        _, report = self.analyze(
            "# 目的\n\n"
            "本命名规范用于定义软件各功能模块的命名。\n\n"
            "# 适用范围\n\n"
            "该命名规范适用于所有产品的软件模块命名。\n\n"
            "# 定义和缩写\n\n"
            "# 域定义\n\n"
            "FC模块命名规则。\n\n"
            "## P1 公司名称\n\n"
            "公司名称指金脉或供应商的名称。\n"
        )
        self.assertEqual(report.document_profile.kind, "automotive_formal_spec")
        self.assertGreaterEqual(report.document_profile.confidence, 0.60)

    def test_asset_analyzer_reports_missing_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, report = self.analyze("![缺失图片](missing.png)", base_path=Path(tmp))
        self.assertEqual(report.assets[0].kind, "missing_asset")
        self.assertTrue(any(d.get("code") == "asset_requires_review" for d in report.assets[0].diagnostics))

    def test_diagram_analyzer_reports_fidelity_risk(self):
        _, report = self.analyze(
            "```mermaid\n"
            "graph TD\n"
            "A --> B\n"
            "```\n"
        )
        self.assertEqual(report.diagrams[0].kind, "mermaid")
        self.assertEqual(report.diagrams[0].attributes["fidelity_risk"], "source_only_if_not_prerendered")
        self.assertTrue(any(d.get("code") == "diagram_static_asset_required" for d in report.diagrams[0].diagnostics))

    def test_raw_html_diagnostics_are_carried_into_semantic_report(self):
        doc, report = self.analyze('<div class="warning">禁止带电插拔。</div>')
        self.assertIn("semantic_analysis", doc.metadata)
        self.assertTrue(any(d.get("code") == "unsupported_raw_html_block" for d in report.diagnostics))


if __name__ == "__main__":
    unittest.main()
