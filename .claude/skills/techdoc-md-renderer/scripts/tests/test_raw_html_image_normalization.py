from pathlib import Path
import base64
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from parser import MarkdownParser
from core.layout import LayoutPlanner
from core.model import Figure, RawHtmlBlock, Table
from core.normalize import ast_to_document
from core.rules import PolicyBuilder
from core.semantic import analyze_document
from core.validation import RealDocumentCase, run_validation_case
from renderers.base import RenderContext
from renderers.docx import DocxRendererAdapter
from renderers.html import HtmlRendererAdapter


ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class RawHtmlImageNormalizationTest(unittest.TestCase):
    def build(self, markdown: str, base_path: Path):
        ast = MarkdownParser().parse(markdown)
        doc = ast_to_document(ast, source_hint=str(base_path / "sample.md"))
        analyze_document(doc, base_path=base_path)
        policy = PolicyBuilder().build(doc, document_profile="api_reference")
        plan = LayoutPlanner().plan(doc, policy)
        return doc, policy, plan

    def test_raw_html_image_block_becomes_figure_and_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "img.png").write_bytes(base64.b64decode(ONE_PIXEL_PNG))
            doc, policy, plan = self.build('<img src="img.png" alt="A" style="width:1in;height:2in" />', base)
        figures = [block for block in doc.blocks if isinstance(block, Figure)]
        self.assertEqual(len(figures), 1)
        self.assertEqual(figures[0].image.src, "img.png")
        self.assertEqual(figures[0].image.width, "1in")
        assets = doc.metadata["semantic_analysis"]["assets"]
        self.assertEqual(assets[0]["kind"], "local_image")
        self.assertEqual(assets[0]["attributes"]["source_kind"], "raw_html_img")
        self.assertEqual(len(plan.figures), 1)

    def test_complex_raw_html_is_preserved_and_image_is_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "img.png").write_bytes(base64.b64decode(ONE_PIXEL_PNG))
            doc, policy, plan = self.build('<div class="x">说明<img src="img.png" alt="A" /></div>', base)
        self.assertTrue(any(isinstance(block, RawHtmlBlock) for block in doc.blocks))
        self.assertTrue(any(isinstance(block, Figure) for block in doc.blocks))
        codes = {d.get("code") for block in doc.blocks for d in getattr(block, "diagnostics", [])}
        self.assertIn("complex_raw_html_preserved_with_images_extracted", codes)

    def test_raw_html_table_cell_image_enters_asset_analysis_and_renderers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "img.png").write_bytes(base64.b64decode(ONE_PIXEL_PNG))
            md = (
                "<table><tr><th>符号</th><th>说明</th></tr>"
                "<tr><td><img src=\"img.png\" alt=\"symbol\" /></td><td>处理</td></tr></table>"
            )
            doc, policy, plan = self.build(md, base)
            table = next(block for block in doc.blocks if isinstance(block, Table))
            self.assertEqual(table.rows[1].cells[0].children[-1].src, "img.png")
            self.assertEqual(doc.metadata["semantic_analysis"]["assets"][0]["kind"], "local_image")

            html = HtmlRendererAdapter().render(RenderContext(
                document=doc,
                policy=policy,
                layout_plan=plan,
                diagnostics=[],
                assets={"base_path": str(base)},
            ))
            self.assertIn('src="img.png"', html.content)

            out = base / "out.docx"
            docx = DocxRendererAdapter().render(RenderContext(
                document=doc,
                policy=policy,
                layout_plan=plan,
                output_path=out,
                diagnostics=[],
                assets={"base_path": str(base)},
            ))
            self.assertTrue(docx.success, docx.error)

    def test_missing_raw_html_image_is_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            doc, policy, plan = self.build('<img src="missing.png" alt="missing" />', base)
        diagnostics = doc.metadata["semantic_analysis"]["diagnostics"]
        self.assertTrue(any(d.get("code") == "asset_requires_review" for d in diagnostics))

    def test_real_document_benchmark_improves_docx_image_count(self):
        source = Path("/Users/chenkunjie/Downloads/SBPAI/Proj/规范文档/G-C110 流程图编制规范_A0/out/G-C110 流程图编制规范_A0.md")
        if not source.exists():
            self.skipTest("G-C110 real document is not available")
        with tempfile.TemporaryDirectory() as tmp:
            case = RealDocumentCase("g-c110-test", str(source), "requirement_spec", "mixed_chinese_formal_spec")
            result = run_validation_case(case, Path(tmp), "word")
        self.assertGreater(result.v2["metrics"].get("image_count", 0), 0)


if __name__ == "__main__":
    unittest.main()
