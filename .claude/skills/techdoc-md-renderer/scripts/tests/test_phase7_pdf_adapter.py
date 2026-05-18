from pathlib import Path
import base64
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from api import Converter
from parser import MarkdownParser
from core.layout import LayoutPlanner
from core.normalize import ast_to_document
from core.rules import PolicyBuilder
from core.semantic import analyze_document
from renderers.base import RenderContext
from renderers.pdf import PdfBackendRegistry, PdfRendererAdapter
from renderers.pdf.reportlab_fallback import ReportLabFallbackBackend


ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class OnlyReportLabRegistry(PdfBackendRegistry):
    def __init__(self):
        super().__init__([ReportLabFallbackBackend()])

    def select(self, preferred="weasyprint", fallback_order=None):
        return self.backends["reportlab"]


class Phase7PdfAdapterTest(unittest.TestCase):
    def build_context(self, markdown: str, base_path: Path, *, profile: str = "chip_register_manual", output_name: str = "out.pdf") -> RenderContext:
        ast = MarkdownParser().parse(markdown)
        doc = ast_to_document(ast, source_hint="phase7.md")
        analyze_document(doc, base_path=base_path)
        policy = PolicyBuilder().build(doc, document_profile=profile)
        plan = LayoutPlanner().plan(doc, policy)
        return RenderContext(
            document=doc,
            policy=policy,
            layout_plan=plan,
            output_path=base_path / output_name,
            diagnostics=doc.metadata.get("semantic_analysis", {}).get("diagnostics", []),
            assets={"base_path": str(base_path)},
            options={"doc_title": "PDF Adapter Test"},
        )

    def render_pdf(self, markdown: str, base_path: Path, *, registry=None, profile="chip_register_manual"):
        context = self.build_context(markdown, base_path, profile=profile)
        result = PdfRendererAdapter(registry=registry).render(context)
        self.assertTrue(result.success, result.error)
        self.assertTrue(Path(result.output_path).exists())
        self.assertGreater(Path(result.output_path).stat().st_size, 0)
        return result

    def test_backend_registry_capabilities_are_queryable(self):
        caps = PdfBackendRegistry().capabilities()
        self.assertIn("weasyprint", caps)
        self.assertIn("chromium", caps)
        self.assertIn("wkhtmltopdf", caps)
        self.assertIn("reportlab", caps)
        self.assertTrue(caps["weasyprint"]["paged_media"])
        self.assertEqual(caps["reportlab"]["fidelity_level"], "non_conformant")

    def test_simple_a4_document_and_pagebreak_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.render_pdf("# 标题\n\n正文\n\n<!-- pagebreak -->\n\n下一页", Path(tmp), profile="automotive_formal_spec")
        self.assertIn(result.fidelity_level, ("conformant", "review"))
        self.assertIn("backend_used", result.metadata)

    def test_register_wide_table_code_and_mermaid_diagnostics(self):
        markdown = (
            "# Manual\n\n"
            "<!-- table: register -->\n"
            "| Address | Register | Bits | Access | Reset | Clock | Domain | Description |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| 0x00 | CTRL | [3:0] | RW | 0x0 | APB | SYS | Long description for overflow. |\n\n"
            "```c\nuint8_t value = read_reg(0x00);\n```\n\n"
            "```mermaid\ngraph TD\nA --> B\n```\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = self.render_pdf(markdown, Path(tmp))
        codes = {d.get("code") for d in result.diagnostics}
        self.assertIn("degraded_table_split", codes)
        self.assertIn("degraded_pagination", codes)
        self.assertIn(result.fidelity_level, ("review", "degraded", "non_conformant"))

    def test_image_scaling_missing_and_svg_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "tiny.png").write_bytes(base64.b64decode(ONE_PIXEL_PNG))
            (base / "icon.svg").write_text("<svg></svg>", encoding="utf-8")
            markdown = "![png](tiny.png)\n\n![missing](missing.png)\n\n![svg](icon.svg)\n"
            result = self.render_pdf(markdown, base, profile="lightweight_tech_note")
        codes = {d.get("code") for d in result.diagnostics}
        self.assertIn("degraded_svg_render", codes)
        self.assertTrue(any(code in codes for code in ("asset_requires_review", "html_adapter_missing_image_placeholder", "html_adapter_missing_inline_image_placeholder")))

    def test_reportlab_fallback_is_non_conformant_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.render_pdf("# Fallback\n\n正文。", Path(tmp), registry=OnlyReportLabRegistry(), profile="lightweight_tech_note")
        self.assertEqual(result.metadata["backend_used"], "reportlab")
        self.assertEqual(result.fidelity_level, "non_conformant")
        self.assertTrue(result.fallback_used)
        self.assertTrue(any(d.get("code") == "reportlab_non_conformant" for d in result.diagnostics))

    def test_unsupported_backend_feature_diagnostic_for_table_repeat_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.render_pdf(
                "<!-- table: register -->\n"
                "| Address | Register | Bits | Access | Reset | Description |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| 0x00 | CTRL | [3:0] | RW | 0x0 | Control |\n",
                Path(tmp),
                registry=OnlyReportLabRegistry(),
        )
        self.assertTrue(any(d.get("code") == "unsupported_backend_feature" for d in result.diagnostics))

    def test_pdf_v2_conversion_outputs_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "sample.md"
            md.write_text("# PDF\n\n正文。", encoding="utf-8")
            result = Converter().convert_file(md, format="pdf", output_path=Path(tmp) / "v2.pdf", pipeline="v2")
        self.assertTrue(result.success, result.error)


if __name__ == "__main__":
    unittest.main()
