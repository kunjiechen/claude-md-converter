from pathlib import Path
import sys
import tempfile
import unittest

import yaml


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.normalize import ast_to_document
from core.semantic import analyze_document
from core.rules import PolicyBuilder, RenderPolicy, RuleLoader, RuleResolver
from core.rules.loader import RuleConfigError


class Phase4RenderPolicyTest(unittest.TestCase):
    def setUp(self):
        self.parser = MarkdownParser()

    def document_from_markdown(self, markdown: str):
        ast = self.parser.parse(markdown)
        doc = ast_to_document(ast, source_hint="policy-test.md")
        analyze_document(doc)
        return doc

    def test_render_rules_yaml_loads_and_validates(self):
        config = RuleLoader().load()
        self.assertEqual(config["version"], 2)
        self.assertIn("automotive_formal_spec", config["profiles"])
        self.assertIn("chip_register_manual", config["profiles"])
        self.assertIn("lightweight_tech_note", config["profiles"])
        self.assertIn("a4_cn_formal", config["page_profiles"])
        self.assertIn("web_responsive", config["page_profiles"])

    def test_validation_rejects_missing_required_profile(self):
        config = RuleLoader().load()
        config["profiles"].pop("chip_register_manual")
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh)
            fh.flush()
            with self.assertRaises(RuleConfigError):
                RuleLoader(Path(fh.name)).load()

    def test_policy_builder_uses_semantic_document_profile(self):
        doc = self.document_from_markdown(
            "# 芯片寄存器手册\n\n"
            "本章描述 register offset bit field reset access。\n\n"
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Description |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | Control register |\n"
        )
        policy = PolicyBuilder().build(doc)
        self.assertIsInstance(policy, RenderPolicy)
        self.assertEqual(policy.document_profile, "chip_register_manual")
        self.assertEqual(policy.source["document_profile_source"], "semantic_analysis")
        self.assertIn("register", policy.table_policy["supported_table_kinds"])
        self.assertTrue(policy.table_policy["landscape_allowed"])

    def test_profile_override_takes_precedence(self):
        doc = self.document_from_markdown("# 轻量说明\n\n正文。")
        policy = PolicyBuilder().build(doc, document_profile="automotive_formal_spec", page_profile="a4_cn_formal")
        self.assertEqual(policy.document_profile, "automotive_formal_spec")
        self.assertEqual(policy.page_profile, "a4_cn_formal")
        self.assertEqual(policy.source["document_profile_source"], "override")
        self.assertEqual(policy.document_policy["toc"], "required")

    def test_render_policy_expresses_required_policy_areas(self):
        doc = self.document_from_markdown("# 轻量说明\n\n正文。")
        policy = PolicyBuilder().build(doc)
        payload = policy.to_dict()
        for key in (
            "document_policy",
            "typography_policy",
            "table_policy",
            "image_policy",
            "diagram_policy",
            "code_policy",
            "renderer_policy",
            "quality_policy",
        ):
            self.assertIn(key, payload)
            self.assertTrue(payload[key])
        self.assertTrue(policy.code_policy["preserve_code_identity"])
        self.assertIn("diagnostics_required_for", policy.quality_policy)

    def test_renderer_specific_rules_are_isolated_in_renderer_policy(self):
        doc = self.document_from_markdown("# 轻量说明\n\n正文。")
        policy = PolicyBuilder().build(doc)
        self.assertIn("docx", policy.renderer_policy)
        self.assertIn("word_style_mapping", policy.renderer_policy["docx"]["adapter_policy"])
        self.assertNotIn("word_style_mapping", policy.document_policy)
        self.assertNotIn("word_style_mapping", policy.table_policy)

    def test_rule_resolver_merges_profile_overrides(self):
        config = RuleLoader().load()
        rules = RuleResolver(config).resolve("automotive_formal_spec", "a4_cn_formal")
        self.assertEqual(rules["document_policy"]["toc"], "required")
        self.assertEqual(rules["image_policy"]["missing_asset_policy"], "diagnostic_error")
        self.assertIn("pdf", rules["diagram_policy"]["prerender_required_targets"])


if __name__ == "__main__":
    unittest.main()
