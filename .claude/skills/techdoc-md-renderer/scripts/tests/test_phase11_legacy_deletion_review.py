from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(SCRIPT_DIR))

from core.governance import build_legacy_deletion_review, build_legacy_inventory


class Phase11LegacyDeletionReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = build_legacy_inventory(REPO_ROOT)
        cls.review = build_legacy_deletion_review(REPO_ROOT)

    def test_inventory_covers_legacy_areas(self):
        owners = {item.current_owner for item in self.inventory}
        self.assertIn("legacy_html_renderer", owners)
        self.assertIn("legacy_docx_renderer", owners)
        self.assertIn("legacy_pdf_renderer", owners)
        self.assertIn("post_polish", owners)
        self.assertIn("preflight", owners)
        self.assertIn("postflight", owners)

    def test_all_items_are_classified_and_scored(self):
        self.assertGreater(len(self.inventory), 20)
        allowed = {
            "safe_to_remove",
            "remove_after_rollout",
            "compatibility_required",
            "renderer_specific_required",
            "unknown_risk",
        }
        for item in self.inventory:
            self.assertIn(item.classification, allowed)
            self.assertGreaterEqual(item.readiness_score, 0)
            self.assertLessEqual(item.readiness_score, 100)
            self.assertTrue(item.rollback_dependency if hasattr(item, "rollback_dependency") else True)

    def test_deletion_candidate_report_has_required_buckets(self):
        report = self.review["deletion_candidate_report"]
        for bucket in ("safe_to_remove", "remove_after_rollout", "compatibility_required", "renderer_specific_required", "unknown_risk"):
            self.assertIn(bucket, report)
        self.assertGreater(len(report["remove_after_rollout"]), 0)
        self.assertGreater(len(report["compatibility_required"]), 0)

    def test_compatibility_critical_logic_is_not_safe_to_remove(self):
        high_risk = self.review["high_risk_legacy_areas"]
        files = {item["file"] for item in high_risk}
        self.assertTrue(any("preflight.py" in file for file in files))
        self.assertTrue(any("postflight.py" in file for file in files))
        self.assertTrue(any("polisher.py" in file for file in files))
        safe = self.review["deletion_candidate_report"]["safe_to_remove"]
        self.assertFalse(any("preflight.py" in item["file"] for item in safe))
        self.assertFalse(any("postflight.py" in item["file"] for item in safe))

    def test_patch_and_hardcoded_audits_are_traceable(self):
        patch_audit = self.review["patch_audit"]
        hardcoded = self.review["hardcoded_rule_audit"]
        self.assertGreater(len(patch_audit), 0)
        self.assertGreater(len(hardcoded), 0)
        for item in patch_audit[:20]:
            self.assertTrue(item["replacement"])
            self.assertTrue(item["retirement_condition"])
            self.assertTrue(item["test_coverage"])
        for item in hardcoded[:20]:
            self.assertTrue(item["migration_status"])
            self.assertTrue(item["recommendation"])

    def test_rollout_scores_and_removal_order_are_present(self):
        scores = self.review["deletion_readiness_scores"]
        self.assertIn("legacy_html_renderer", scores)
        self.assertIn("legacy_docx_renderer", scores)
        self.assertIn("legacy_pdf_renderer", scores)
        self.assertIn("recommended_removal_order", self.review)
        self.assertIn("rollback_strategy", self.review)
        self.assertGreater(len(self.review["rollback_strategy"]), 0)


if __name__ == "__main__":
    unittest.main()
