from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from api import Converter
from cli import parse_args
from renderers.base import RenderResult


class Phase10ReleaseCutoverTest(unittest.TestCase):
    def test_api_rejects_legacy_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "sample.md"
            out = Path(tmp) / "legacy.html"
            md.write_text("# Legacy\n\n正文。", encoding="utf-8")
            result = Converter().convert_file(md, format="html", output_path=out, pipeline="legacy")
            self.assertFalse(result.success)
            self.assertIn("Unsupported pipeline", result.error or "")

    def test_api_v2_uses_unified_pipeline_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "sample.md"
            out = Path(tmp) / "v2.html"
            md.write_text("# Auto\n\n正文。", encoding="utf-8")
            result = Converter().convert_file(
                md,
                format="html",
                output_path=out,
                pipeline="v2",
                profile="lightweight_tech_note",
                report=True,
            )
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.pipeline, "v2")
            self.assertEqual(result.renderer_used, "html_adapter")
            self.assertTrue(Path(result.unified_report_path).exists())

    def test_api_rejects_auto_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "formal.md"
            out = Path(tmp) / "formal.pdf"
            md.write_text("# Formal\n\n正文。", encoding="utf-8")
            result = Converter().convert_file(
                md,
                format="pdf",
                output_path=out,
                pipeline="auto",
                profile="automotive_formal_spec",
            )
            self.assertFalse(result.success)
            self.assertIn("Unsupported pipeline", result.error or "")

    def test_api_v2_failure_returns_error_with_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "fallback.md"
            out = Path(tmp) / "fallback.html"
            md.write_text("# Fallback\n\n正文。", encoding="utf-8")
            failed = RenderResult(False, error="forced failure", diagnostics=[])
            with patch("core.pipeline.unified.HtmlRendererAdapter.render", return_value=failed):
                result = Converter().convert_file(
                    md,
                    format="html",
                    output_path=out,
                    pipeline="v2",
                    profile="lightweight_tech_note",
                    report=True,
                )
            self.assertFalse(result.success)
            self.assertEqual(result.pipeline, "v2")
            self.assertTrue(Path(result.unified_report_path).exists())

    def test_cli_accepts_new_phase10_parameters(self):
        args = parse_args([
            "doc.md",
            "--format", "html",
            "--pipeline", "v2",
            "--profile", "lightweight_tech_note",
            "--quality-gate", "review",
            "--strict",
            "--report",
        ])
        self.assertEqual(args.pipeline, "v2")
        self.assertEqual(args.profile, "lightweight_tech_note")
        self.assertTrue(args.strict)
        self.assertTrue(args.report)

if __name__ == "__main__":
    unittest.main()
