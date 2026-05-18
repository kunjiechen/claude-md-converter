"""Programmatic conversion API based on the unified V2 pipeline."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union


@dataclass
class ConversionResult:
    input_path: str
    output_path: str
    format: str
    success: bool
    error: Optional[str] = None
    size_bytes: int = 0
    quality_report_path: Optional[str] = None
    quality_report_html_path: Optional[str] = None
    quality_status: Optional[str] = None
    quality_score: Optional[int] = None
    deliverable: Optional[bool] = None
    unified_report_path: Optional[str] = None
    pipeline: Optional[str] = None
    renderer_used: Optional[str] = None
    fidelity_level: Optional[str] = None


@dataclass
class BatchConversionResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    files: List[ConversionResult] = field(default_factory=list)
    index_path: Optional[str] = None
    elapsed_seconds: float = 0.0


class Converter:
    """Unified converter: all requests go through V2 adapters."""

    SUPPORTED_FORMATS = ("word", "html", "pdf")

    def __init__(self, **default_options):
        self.default_options = default_options

    def convert_file(
        self,
        input_path: Union[str, Path],
        format: str = "",
        output_path: Optional[Union[str, Path]] = None,
        **options,
    ) -> ConversionResult:
        from core.pipeline import render_document

        input_path = Path(input_path)
        format = format or self.default_options.get("format", "html")
        merged = {**self.default_options, **options, "format": format}
        pipeline_mode = merged.get("pipeline") or merged.get("render_pipeline")
        if pipeline_mode and pipeline_mode not in ("v2",):
            return ConversionResult(
                input_path=str(input_path),
                output_path="",
                format=format,
                success=False,
                error=f"Unsupported pipeline: {pipeline_mode}. Only 'v2' is allowed.",
                pipeline="v2",
            )

        try:
            if format not in self.SUPPORTED_FORMATS:
                return ConversionResult(
                    input_path=str(input_path),
                    output_path="",
                    format=format,
                    success=False,
                    error=f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}",
                    pipeline="v2",
                )

            render_options = dict(merged)
            if merged.get("profile") and not merged.get("document_profile"):
                render_options["document_profile"] = merged.get("profile")
            report = render_document(
                input_path,
                output_path=output_path,
                format=format,
                options=render_options,
            )
            if merged.get("strict") and report.quality_gate.get("status") != "pass":
                report.success = False
                report.error = report.error or f"Strict quality gate failed: {report.quality_gate.get('status')}"
            report_path = self._write_unified_report(input_path, output_path, report, merged)
            size = Path(report.output_path).stat().st_size if report.output_path and Path(report.output_path).exists() else 0
            return ConversionResult(
                input_path=str(input_path),
                output_path=report.output_path or "",
                format=format,
                success=report.success,
                error=report.error,
                size_bytes=size,
                quality_status=(report.quality_gate or {}).get("status"),
                quality_score=(report.quality_gate or {}).get("score"),
                deliverable=(report.quality_gate or {}).get("deliverable"),
                unified_report_path=report_path,
                pipeline="v2",
                renderer_used=report.renderer_used,
                fidelity_level=report.fidelity_level,
            )
        except Exception as exc:
            return ConversionResult(
                input_path=str(input_path),
                output_path="",
                format=format,
                success=False,
                error=str(exc),
                pipeline="v2",
            )

    def convert_directory(
        self,
        input_dir: Union[str, Path],
        format: str = "",
        output_dir: Optional[Union[str, Path]] = None,
        generate_index: bool = True,
        index_title: str = "文档索引",
        max_workers: int = 4,
        **options,
    ) -> BatchConversionResult:
        start = time.time()
        format = format or self.default_options.get("format", "html")
        input_dir = Path(input_dir)
        output_root = Path(output_dir) if output_dir else input_dir
        output_root.mkdir(parents=True, exist_ok=True)
        md_files = sorted(list(input_dir.rglob("*.md")) + list(input_dir.rglob("*.markdown")))

        results: List[ConversionResult] = []
        ext = ".docx" if format == "word" else f".{format}"
        for md in md_files:
            out = output_root / (md.stem + ext)
            item = self.convert_file(md, format=format, output_path=out, **options)
            results.append(item)

        success = sum(1 for item in results if item.success)
        failed = len(results) - success
        index_path = None
        if generate_index and format == "html" and success > 0:
            from index_generator import IndexGenerator

            html_files = [Path(item.output_path) for item in results if item.success and item.output_path]
            if html_files:
                index_path = str(IndexGenerator(title=index_title).generate(html_files, output_root, title=index_title))

        return BatchConversionResult(
            total=len(results),
            success=success,
            failed=failed,
            files=results,
            index_path=index_path,
            elapsed_seconds=round(time.time() - start, 2),
        )

    @classmethod
    def get_available_formats(cls) -> tuple:
        return cls.SUPPORTED_FORMATS

    @staticmethod
    def _write_unified_report(input_path, output_path, report, merged) -> Optional[str]:
        if not merged.get("report"):
            return None
        explicit = merged.get("report_path")
        if explicit:
            path = Path(explicit)
        elif output_path:
            path = Path(output_path).with_suffix(Path(output_path).suffix + ".unified-report.json")
        else:
            path = Path(input_path).with_suffix(".unified-report.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
