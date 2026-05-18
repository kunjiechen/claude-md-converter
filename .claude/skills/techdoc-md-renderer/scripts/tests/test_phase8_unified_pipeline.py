from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(SCRIPT_DIR))

from core.governance import (
    audit_legacy_rules,
    build_patch_retirement_report,
    build_technical_debt_dashboard,
    collect_legacy_retirement_metrics,
    renderer_capability_registry,
)
from core.pipeline import render_document
from api import Converter
from renderers.base import RenderResult


class Phase8UnifiedPipelineTest(unittest.TestCase):
    def write_markdown(self, tmp: str, text: str = None) -> Path:
        path = Path(tmp) / "sample.md"
        path.write_text(text or "# 标题\n\n正文。\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n", encoding="utf-8")
        return path

    def test_unified_pipeline_renders_html_with_policy_and_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = self.write_markdown(tmp)
            out = Path(tmp) / "out.html"
            report = render_document(md, output_path=out, format="html", options={"doc_title": "Unified"})
            self.assertTrue(report.success, report.error)
            self.assertTrue(out.exists())
        self.assertEqual(report.renderer_used, "html_adapter")
        self.assertFalse(report.legacy_used)
        self.assertIn("semantic_analysis", report.to_dict())
        self.assertIn("tables", report.semantic_analysis)
        self.assertIn("tables", report.layout_plan)
        self.assertEqual(report.render_policy["document_profile"], "lightweight_tech_note")

    def test_unified_pipeline_can_call_docx_and_pdf_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = self.write_markdown(tmp, "# 标题\n\n正文。\n")
            docx_report = render_document(md, output_path=Path(tmp) / "out.docx", format="docx")
            pdf_report = render_document(
                md,
                output_path=Path(tmp) / "out.pdf",
                format="pdf",
                options={"pdf_backend": "reportlab", "pdf_fallback_backends": []},
            )
        self.assertTrue(docx_report.success, docx_report.error)
        self.assertEqual(docx_report.renderer_used, "docx_adapter")
        self.assertTrue(pdf_report.success, pdf_report.error)
        self.assertEqual(pdf_report.renderer_used, "pdf_adapter")
        self.assertEqual(pdf_report.renderer_metadata.get("backend_used"), "reportlab")

    def test_converter_v2_allows_semantic_profile_detection_when_not_overridden(self):
        markdown = (
            "# 目的\n\n"
            "本命名规范用于定义软件各功能模块的命名。\n\n"
            "# 适用范围\n\n"
            "该命名规范适用于所有产品的软件模块命名。\n\n"
            "# 定义和缩写\n\n"
            "# 域定义\n\n"
            "FC模块命名规则。\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            md = self.write_markdown(tmp, markdown)
            out = Path(tmp) / "formal.docx"
            result = Converter().convert_file(md, format="word", output_path=out, pipeline="v2", report=True)
            report_text = out.with_suffix(".docx.unified-report.json").read_text(encoding="utf-8")
        self.assertTrue(result.success, result.error)
        self.assertIn('"document_profile": "automotive_formal_spec"', report_text)
        self.assertIn('"toc": "required"', report_text)

    def test_adapter_failure_returns_error_in_strict_v2_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = self.write_markdown(tmp, "# Fallback\n\n正文。\n")
            failed = RenderResult(False, error="forced adapter failure", diagnostics=[])
            with patch("core.pipeline.unified.HtmlRendererAdapter.render", return_value=failed):
                report = render_document(md, output_path=Path(tmp) / "fallback.html", format="html")
        self.assertFalse(report.success)
        self.assertFalse(report.legacy_used)
        self.assertFalse(report.fallback_used)
        codes = {diag.get("code") for diag in report.diagnostics}
        self.assertIn("unified_pipeline_adapter_failed", codes)

    def test_adapter_failure_returns_non_conformant_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = self.write_markdown(tmp)
            failed = RenderResult(False, error="forced adapter failure", diagnostics=[])
            with patch("core.pipeline.unified.HtmlRendererAdapter.render", return_value=failed):
                report = render_document(md, output_path=Path(tmp) / "failed.html", format="html")
        self.assertFalse(report.success)
        self.assertFalse(report.legacy_used)
        self.assertEqual(report.fidelity_level, "non_conformant")

    def test_governance_audit_patch_report_metrics_and_dashboard(self):
        audits = audit_legacy_rules(REPO_ROOT)
        self.assertGreater(len(audits), 0)
        self.assertTrue(any(item.category in ("duplicated_overflow_handling", "duplicated_image_scaling", "duplicated_toc_logic") for item in audits))
        retirement = build_patch_retirement_report(audits)
        self.assertGreater(len(retirement), 0)
        for item in retirement:
            payload = item.to_dict()
            self.assertTrue(payload["owner"])
            self.assertTrue(payload["replacement"])
            self.assertTrue(payload["retirement_condition"])
        metrics = collect_legacy_retirement_metrics(REPO_ROOT, audits)
        self.assertIn("remaining_legacy_paths", metrics)
        self.assertIn("duplicated_logic_count", metrics)
        dashboard = build_technical_debt_dashboard(REPO_ROOT)
        self.assertIn("rule_source_governance", dashboard)
        self.assertIn("legacy_retirement_metrics", dashboard)

    def test_renderer_capability_governance_is_explicit(self):
        registry = renderer_capability_registry()
        self.assertEqual(registry["html"]["semantic_source"], "Document.metadata.semantic_analysis")
        self.assertEqual(registry["docx"]["rule_source"], "RenderPolicy")
        self.assertEqual(registry["pdf"]["layout_source"], "LayoutPlan")


if __name__ == "__main__":
    unittest.main()
