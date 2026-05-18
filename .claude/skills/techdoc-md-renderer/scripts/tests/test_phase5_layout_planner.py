from pathlib import Path
import sys
import tempfile
import unittest
from typing import Optional


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.layout import LayoutPlanner
from core.normalize import ast_to_document
from core.rules import PolicyBuilder
from core.semantic import analyze_document


class Phase5LayoutPlannerTest(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def build_plan(self, markdown: str, *, base_path: Optional[Path] = None, document_profile: Optional[str] = None):
        ast = self.parser.parse(markdown)
        doc = ast_to_document(ast, source_hint="layout-test.md")
        analyze_document(doc, base_path=base_path)
        policy = PolicyBuilder().build(doc, document_profile=document_profile)
        plan = LayoutPlanner().plan(doc, policy)
        return doc, policy, plan

    def test_layout_plan_attaches_to_document_metadata(self):
        doc, policy, plan = self.build_plan("# 标题\n\n正文。")
        self.assertEqual(plan.page.page_profile, policy.page_profile)
        self.assertIn("layout_plan", doc.metadata)
        self.assertEqual(doc.metadata["layout_plan"]["page"]["page_profile"], policy.page_profile)

    def test_register_bitfield_and_generic_tables_get_different_layouts(self):
        markdown = (
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | Control register |\n\n"
            "<!-- table: bitfield -->\n"
            "| Bits | Field | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| [7:4] | MODE | RW | 0 | 工作模式 |\n\n"
            "### Generic table\n\n"
            "| A | B | C | D | E |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| one | two | three | four | five |\n"
        )
        _, _, plan = self.build_plan(markdown, document_profile="chip_register_manual")
        self.assertEqual([t.kind for t in plan.tables], ["register", "bitfield", "generic"])
        self.assertIn("description", [c.role for c in plan.tables[0].columns])
        self.assertEqual(set(c.role for c in plan.tables[2].columns), {"content"})
        self.assertNotEqual(
            [c.width_ratio for c in plan.tables[0].columns],
            [c.width_ratio for c in plan.tables[2].columns],
        )

    def test_wide_table_produces_overflow_risk_and_landscape_recommendation(self):
        _, _, plan = self.build_plan(
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Clock | Domain | Description |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | APB | SYS | This is a very long description intended to exercise overflow risk planning for register documentation. |\n",
            document_profile="chip_register_manual",
        )
        self.assertEqual(plan.tables[0].overflow_risk, "high")
        self.assertEqual(plan.tables[0].landscape_recommendation, "recommended")
        self.assertTrue(any(d.get("code") == "table_overflow_risk" for d in plan.tables[0].diagnostics))
        self.assertEqual(plan.sections[0].orientation_intent, "mixed_portrait_landscape")

    def test_missing_image_produces_placeholder_intent_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, plan = self.build_plan("![缺失图片](missing.png)", base_path=Path(tmp))
        self.assertEqual(plan.figures[0].asset_status, "missing_asset")
        self.assertEqual(plan.figures[0].missing_image_placeholder_intent, "render_declared_missing_asset_placeholder")
        self.assertTrue(any(d.get("code") == "missing_image_placeholder_intent" for d in plan.figures[0].diagnostics))

    def test_code_block_layout_preserves_identity(self):
        _, _, plan = self.build_plan("```c\nuint8_t value = read_reg(0x00);\n```")
        self.assertEqual(plan.code_blocks[0].language, "c")
        self.assertTrue(plan.code_blocks[0].preserve_identity)
        self.assertEqual(plan.code_blocks[0].max_width_behavior, "fit_content_box")

    def test_diagram_layout_declares_prerender_requirement(self):
        _, _, plan = self.build_plan(
            "```mermaid\n"
            "graph TD\n"
            "A --> B\n"
            "```\n"
        )
        self.assertEqual(plan.diagrams[0].diagram_kind, "mermaid")
        self.assertIn("docx", plan.diagrams[0].prerender_required_targets)
        self.assertIn("pdf", plan.diagrams[0].prerender_required_targets)
        self.assertTrue(any(d.get("code") == "diagram_prerender_requirement_planned" for d in plan.diagrams[0].diagnostics))


if __name__ == "__main__":
    unittest.main()
