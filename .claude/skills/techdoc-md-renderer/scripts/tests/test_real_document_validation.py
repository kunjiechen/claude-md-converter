from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from core.validation import (
    RealDocumentCase,
    build_quality_dashboard,
    default_real_document_corpus,
    run_validation_case,
)


class RealDocumentValidationTest(unittest.TestCase):
    def test_default_corpus_contains_user_real_document_and_planned_profiles(self):
        corpus = default_real_document_corpus()
        case_ids = {case.case_id for case in corpus}
        profiles = {case.profile for case in corpus}
        self.assertIn("g-c110-flowchart-spec-a0", case_ids)
        self.assertTrue({"chip_manual", "autosar_spec", "api_reference", "test_report", "requirement_spec"} <= profiles)

    def test_validation_case_runs_v2_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "realish.md"
            md.write_text(
                "# 文件修订履历表\n\n"
                "| 版次 | 修订内容 |\n| --- | --- |\n| A/0 | 初版 |\n\n"
                "# 目的\n\n中文 English mixed content.\n",
                encoding="utf-8",
            )
            case = RealDocumentCase(
                case_id="realish",
                path=str(md),
                profile="requirement_spec",
                category="mixed_chinese_formal_spec",
                expected_features=["toc", "revision_table"],
            )
            result = run_validation_case(case, Path(tmp) / "validation", "html")
        self.assertTrue(result.v2["success"])
        self.assertIn(result.comparison["layout_fidelity"], ("pass", "fail"))
        self.assertIn("recommendation", result.to_dict())

    def test_quality_dashboard_summarizes_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "realish.md"
            md.write_text("# API\n\nText\n", encoding="utf-8")
            case = RealDocumentCase("api", str(md), "api_reference", "api_reference")
            result = run_validation_case(case, Path(tmp) / "validation", "html")
            dashboard = build_quality_dashboard([result])
        self.assertEqual(dashboard.total_runs, 1)
        self.assertIn("html", dashboard.renderer_pass_rate)
        self.assertIn("api_reference", dashboard.profile_coverage)
        self.assertIn("html", dashboard.rollout_recommendation)


if __name__ == "__main__":
    unittest.main()
