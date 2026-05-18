from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.normalize import ast_to_document
from core.plugins import PluginInfo, PluginRegistry
from core.rules import PolicyBuilder, RuleLoader
from core.semantic import analyze_document


class DummyTableClassifier:
    info = PluginInfo(
        name="dummy_table_classifier",
        kind="table_classifier",
        version="1.0.0",
        capability_version="1.0",
        description="test plugin",
    )

    def classify(self, table, context):
        return {"kind": "generic", "confidence": 1.0, "evidence": ["dummy"], "diagnostics": []}


class Phase12MaintenancePluginizationTest(unittest.TestCase):
    def test_plugin_registry_accepts_minimal_plugin(self):
        registry = PluginRegistry()
        plugin = DummyTableClassifier()
        registry.register(plugin)
        self.assertIs(registry.get("table_classifier", "dummy_table_classifier"), plugin)
        infos = registry.list("table_classifier")
        self.assertEqual(infos[0].capability_version, "1.0")

    def test_plugin_registry_rejects_invalid_kind(self):
        class BadPlugin:
            info = PluginInfo(name="bad", kind="unknown", version="1", capability_version="1")

        with self.assertRaises(ValueError):
            PluginRegistry().register(BadPlugin())

    def test_profile_extensions_load_without_core_code_changes(self):
        config = RuleLoader().load()
        for profile in ("chip_manual", "autosar_spec", "api_reference", "test_report", "requirement_spec"):
            self.assertIn(profile, config["profiles"])
            self.assertEqual(config["profiles"][profile]["profile_version"], "1.0")
            self.assertIn("document_policy", config["profiles"][profile])
            self.assertIn("table_policy", config["profiles"][profile])

    def test_extended_profile_can_build_render_policy(self):
        ast = MarkdownParser().parse("# API\n\n```python\nprint('x')\n```\n")
        doc = ast_to_document(ast, source_hint="api_reference.md")
        analyze_document(doc)
        policy = PolicyBuilder().build(doc, document_profile="api_reference")
        self.assertEqual(policy.document_profile, "api_reference")
        self.assertTrue(policy.code_policy["preserve_code_identity"])
        self.assertIn("interface", policy.table_policy["supported_table_kinds"])

    def test_schema_versions_are_traceable(self):
        config = RuleLoader().load()
        versions = config.get("schema_versions") or {}
        self.assertEqual(versions["spec_version"], "2.0")
        self.assertEqual(versions["render_rules_schema"], "2.0")
        self.assertEqual(versions["profile_schema"], "1.0")
        self.assertEqual(versions["adapter_capability_schema"], "1.0")


if __name__ == "__main__":
    unittest.main()
