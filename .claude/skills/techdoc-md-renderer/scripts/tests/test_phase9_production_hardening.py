from pathlib import Path
import sys
import tempfile
import unittest

import yaml


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(SCRIPT_DIR))

from core.pipeline import (
    build_production_readiness_report,
    evaluate_unified_quality,
    render_document,
)
from core.rules.loader import RuleConfigError, RuleLoader


class Phase9ProductionHardeningTest(unittest.TestCase):
    def test_unified_report_contains_trace_performance_and_quality_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "sample.md"
            md.write_text("# 标题\n\n正文。\n", encoding="utf-8")
            out = Path(tmp) / "sample.html"
            report = render_document(md, output_path=out, format="html")
        self.assertTrue(report.success, report.error)
        self.assertIn("status", report.quality_gate)
        self.assertIn(report.quality_gate["status"], ("pass", "review", "fail"))
        self.assertIn("events", report.render_trace)
        self.assertIn("phase_timings", report.performance_report)
        phases = {event["phase"] for event in report.render_trace["events"]}
        self.assertTrue({"markdown_parse", "document_model_build", "semantic_analysis", "policy_build", "layout_plan", "renderer_adapter"} <= phases)

    def test_quality_gate_fails_non_conformant_and_reviews_fallback(self):
        failed = evaluate_unified_quality(
            diagnostics=[{"severity": "error", "category": "renderer", "code": "pdf_adapter_render_failed"}],
            fidelity_level="non_conformant",
            fallback_used=False,
            layout_plan={},
        )
        self.assertEqual(failed.status, "fail")
        review = evaluate_unified_quality(
            diagnostics=[{"severity": "warning", "category": "pipeline", "code": "fallback_to_legacy_renderer"}],
            fidelity_level="review",
            fallback_used=True,
            layout_plan={},
        )
        self.assertEqual(review.status, "review")
        self.assertIn("fallback_used", review.reasons)

    def test_config_validation_rejects_invalid_backend_and_profile(self):
        config = RuleLoader().load()
        config["renderer_policy"]["pdf"]["adapter_policy"]["preferred_backend"] = "unknown_pdf"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "render-rules.yaml"
            path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
            with self.assertRaises(RuleConfigError):
                RuleLoader(path).load()

    def test_config_validation_rejects_unchecked_unsupported_policy(self):
        config = RuleLoader().load()
        config["profiles"]["lightweight_tech_note"]["document_policy"]["unsupported_content_policy"] = "drop"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "render-rules.yaml"
            path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
            with self.assertRaises(RuleConfigError):
                RuleLoader(path).load()

    def test_production_readiness_report_has_rollout_and_risk_sections(self):
        report = build_production_readiness_report(REPO_ROOT)
        self.assertEqual(report["status"], "review")
        self.assertIn("default_rollout_policy", report)
        self.assertIn("remaining_legacy_dependency_report", report)
        self.assertIn("known_risks", report)
        self.assertIn("dashboard", report)


if __name__ == "__main__":
    unittest.main()
