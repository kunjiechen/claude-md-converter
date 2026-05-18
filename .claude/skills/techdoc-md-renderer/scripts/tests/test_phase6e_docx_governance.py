from pathlib import Path
import json
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
GOLDEN_DIR = SCRIPT_DIR / "tests" / "golden" / "docx"
sys.path.insert(0, str(SCRIPT_DIR))

from api import Converter
from parser import MarkdownParser
from core.layout import LayoutPlanner
from core.normalize import ast_to_document
from core.rules import PolicyBuilder
from core.semantic import analyze_document
from renderers.base import RenderContext
from renderers.docx import DocxRendererAdapter, collect_docx_metrics, evaluate_docx_adapter_readiness


class Phase6EDocxGovernanceTest(unittest.TestCase):
    def build_doc_and_result(self, markdown: str, base_path: Path, *, profile: str):
        ast = MarkdownParser().parse(markdown)
        doc = ast_to_document(ast, source_hint=f"{profile}.md")
        analyze_document(doc, base_path=base_path)
        policy = PolicyBuilder().build(doc, document_profile=profile)
        plan = LayoutPlanner().plan(doc, policy)
        result = DocxRendererAdapter().render(RenderContext(
            document=doc,
            policy=policy,
            layout_plan=plan,
            output_path=base_path / f"{profile}.docx",
            diagnostics=doc.metadata.get("semantic_analysis", {}).get("diagnostics", []),
            options={"doc_title": profile},
        ))
        self.assertTrue(result.success, result.error)
        return doc, result

    def test_golden_docx_baseline_metrics(self):
        baseline = json.loads((GOLDEN_DIR / "baseline.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for profile, expected in baseline.items():
                markdown = (GOLDEN_DIR / f"{profile}.md").read_text(encoding="utf-8")
                _, result = self.build_doc_and_result(markdown, base, profile=profile)
                metrics = collect_docx_metrics(Path(result.output_path))
                self.assertGreaterEqual(metrics.table_count, expected["min_tables"], profile)
                self.assertGreaterEqual(metrics.heading_count, expected["min_headings"], profile)
                self.assertEqual(metrics.has_toc_field or metrics.has_visible_toc, expected["requires_toc"], profile)
                if expected["requires_revision"]:
                    self.assertTrue(metrics.has_revision_table, profile)

    def test_readiness_report_contains_supported_degraded_and_score(self):
        markdown = (GOLDEN_DIR / "lightweight_tech_note.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            doc, result = self.build_doc_and_result(markdown, Path(tmp), profile="lightweight_tech_note")
            readiness = evaluate_docx_adapter_readiness(doc, result)
        payload = readiness.to_dict()
        self.assertIn("Paragraph", payload["supported_nodes"])
        self.assertTrue(payload["degraded_features"])
        self.assertGreaterEqual(payload["fidelity_score"], 0)
        self.assertIn(payload["fidelity_level"], ("conformant", "review", "degraded", "non_conformant"))

    def test_converter_word_uses_v2_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "chip.md"
            out = Path(tmp) / "v2.docx"
            md.write_text((GOLDEN_DIR / "chip_register_manual.md").read_text(encoding="utf-8"), encoding="utf-8")
            result = Converter().convert_file(md, format="word", output_path=out, pipeline="v2")
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.pipeline, "v2")
            self.assertTrue(out.exists())

    def test_docx_adapter_render_result_has_fidelity_and_degradation_reason(self):
        markdown = "![missing](missing.png)\n\n<div>raw</div>"
        with tempfile.TemporaryDirectory() as tmp:
            _, result = self.build_doc_and_result(markdown, Path(tmp), profile="lightweight_tech_note")
        self.assertIn(result.fidelity_level, ("conformant", "review", "degraded", "non_conformant"))
        self.assertTrue(result.degradation_reason)
        codes = {d.get("code") for d in result.diagnostics}
        self.assertIn("docx_image_placeholder", codes)
        self.assertIn("docx_raw_html_fallback", codes)


if __name__ == "__main__":
    unittest.main()
