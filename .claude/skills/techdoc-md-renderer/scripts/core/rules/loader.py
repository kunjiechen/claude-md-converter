"""Load and validate render-rules.yaml v2."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class RuleConfigError(ValueError):
    pass


class RuleLoader:
    REQUIRED_TOP_LEVEL = {
        "version",
        "defaults",
        "page_profiles",
        "profiles",
        "typography_policy",
        "table_policy",
        "image_policy",
        "diagram_policy",
        "code_policy",
        "renderer_policy",
        "quality_policy",
    }

    REQUIRED_PROFILES = {
        "automotive_formal_spec",
        "chip_register_manual",
        "lightweight_tech_note",
    }

    REQUIRED_PAGE_PROFILES = {
        "a4_cn_formal",
        "web_responsive",
    }

    POLICY_AREAS = [
        "document_policy",
        "typography_policy",
        "table_policy",
        "image_policy",
        "diagram_policy",
        "code_policy",
        "renderer_policy",
        "quality_policy",
    ]
    FIDELITY_LEVELS = {"conformant", "review", "degraded", "non_conformant"}
    PDF_BACKENDS = {"weasyprint", "chromium", "wkhtmltopdf", "reportlab"}

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.default_config_path()

    @staticmethod
    def default_config_path() -> Path:
        return Path(__file__).resolve().parents[3] / "config" / "render-rules.yaml"

    def load(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
        config = self._load_profile_extensions(config)
        self.validate(config)
        return config

    def _load_profile_extensions(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge config/profiles/*.yaml profile extensions into the loaded config."""

        profiles_dir = self.config_path.parent / "profiles"
        if not profiles_dir.exists():
            return config
        result = dict(config)
        result.setdefault("profiles", {})
        for path in sorted(profiles_dir.glob("*.yaml")):
            with path.open("r", encoding="utf-8") as fh:
                extension = yaml.safe_load(fh) or {}
            profile_name = extension.get("profile") or path.stem
            extends = extension.get("extends")
            if extends:
                base = result["profiles"].get(extends)
                if not isinstance(base, dict):
                    continue
                merged = _deep_merge(base, {
                    k: v for k, v in extension.items()
                    if k not in ("profile", "extends")
                })
            else:
                merged = {
                    k: v for k, v in extension.items()
                    if k not in ("profile", "extends")
                }
            merged.setdefault("profile_version", str(extension.get("profile_version", "1.0")))
            result["profiles"][profile_name] = merged
        return result

    def validate(self, config: Dict[str, Any]) -> None:
        errors: List[str] = []
        missing = sorted(self.REQUIRED_TOP_LEVEL - set(config))
        if missing:
            errors.append(f"missing top-level keys: {', '.join(missing)}")
        if config.get("version") != 2:
            errors.append("render-rules.yaml version must be 2")

        profiles = config.get("profiles") or {}
        page_profiles = config.get("page_profiles") or {}
        missing_profiles = sorted(self.REQUIRED_PROFILES - set(profiles))
        missing_pages = sorted(self.REQUIRED_PAGE_PROFILES - set(page_profiles))
        if missing_profiles:
            errors.append(f"missing document profiles: {', '.join(missing_profiles)}")
        if missing_pages:
            errors.append(f"missing page profiles: {', '.join(missing_pages)}")

        for profile_name, profile in profiles.items():
            if not isinstance(profile, dict):
                errors.append(f"profile {profile_name} must be a mapping")
                continue
            page_profile = profile.get("page_profile")
            if page_profile and page_profile not in page_profiles:
                errors.append(f"profile {profile_name} references unknown page_profile {page_profile}")
            if not page_profile:
                errors.append(f"profile {profile_name}.page_profile is required")
            if "document_policy" not in profile:
                errors.append(f"profile {profile_name}.document_policy is required")
            if "table_policy" not in profile:
                errors.append(f"profile {profile_name}.table_policy is required")
            doc_policy = profile.get("document_policy") or {}
            if doc_policy.get("unsupported_content_policy") != "diagnostic_required":
                errors.append(f"profile {profile_name}.document_policy.unsupported_content_policy must be diagnostic_required")
            table_policy_for_profile = profile.get("table_policy") or {}
            supported = table_policy_for_profile.get("supported_table_kinds")
            if supported is not None and not isinstance(supported, list):
                errors.append(f"profile {profile_name}.table_policy.supported_table_kinds must be a list")

        for page_name, page_profile in page_profiles.items():
            if not isinstance(page_profile, dict):
                errors.append(f"page_profile {page_name} must be a mapping")
                continue
            for key in ("page_size", "margins", "content_width_policy"):
                if key not in page_profile:
                    errors.append(f"page_profile {page_name}.{key} is required")

        table_policy = config.get("table_policy") or {}
        thresholds = table_policy.get("table_classifier_thresholds") or {}
        for key in ("low_confidence", "header_reliable"):
            value = thresholds.get(key)
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                errors.append(f"table_classifier_thresholds.{key} must be between 0 and 1")

        renderer_policy = config.get("renderer_policy") or {}
        for target in ("html", "docx", "pdf"):
            if target not in renderer_policy:
                errors.append(f"renderer_policy.{target} is required")
            elif not isinstance(renderer_policy.get(target), dict):
                errors.append(f"renderer_policy.{target} must be a mapping")
            else:
                fidelity = renderer_policy[target].get("target_fidelity")
                if fidelity and fidelity not in self.FIDELITY_LEVELS:
                    errors.append(f"renderer_policy.{target}.target_fidelity is invalid: {fidelity}")

        docx_policy = (renderer_policy.get("docx") or {}).get("adapter_policy") or {}
        if "word_style_mapping" not in docx_policy:
            errors.append("renderer_policy.docx.adapter_policy.word_style_mapping is required")

        pdf_policy = (renderer_policy.get("pdf") or {}).get("adapter_policy") or {}
        preferred = pdf_policy.get("preferred_backend")
        if preferred and preferred not in self.PDF_BACKENDS:
            errors.append(f"renderer_policy.pdf.adapter_policy.preferred_backend is invalid: {preferred}")
        for backend in pdf_policy.get("fallback_backends") or []:
            if backend not in self.PDF_BACKENDS:
                errors.append(f"renderer_policy.pdf.adapter_policy.fallback_backends contains invalid backend: {backend}")
        backend_rules = (renderer_policy.get("pdf") or {}).get("backend_fidelity_rules") or {}
        for name, fidelity in backend_rules.items():
            if fidelity not in self.FIDELITY_LEVELS and not str(fidelity).startswith("conformant_"):
                errors.append(f"renderer_policy.pdf.backend_fidelity_rules.{name} has invalid fidelity: {fidelity}")

        quality_policy = config.get("quality_policy") or {}
        levels = quality_policy.get("fidelity_levels") or []
        if set(levels) != self.FIDELITY_LEVELS:
            errors.append("quality_policy.fidelity_levels must contain conformant, review, degraded, non_conformant")

        feature_flags = config.get("feature_flags") or {}
        unified = feature_flags.get("unified_pipeline_rollout") or {}
        if unified:
            if "automatic_fallback" not in unified:
                errors.append("feature_flags.unified_pipeline_rollout.automatic_fallback is required")
            mode = unified.get("release_mode", "legacy_only")
            if mode not in ("legacy_only", "v2_canary", "v2_default_with_fallback", "v2_strict"):
                errors.append(f"feature_flags.unified_pipeline_rollout.release_mode is invalid: {mode}")
            gate = unified.get("quality_gate_required", "review")
            if gate not in ("pass", "review", "fail"):
                errors.append(f"feature_flags.unified_pipeline_rollout.quality_gate_required is invalid: {gate}")
            canary = unified.get("canary_percent", 0)
            if not isinstance(canary, int) or not 0 <= canary <= 100:
                errors.append("feature_flags.unified_pipeline_rollout.canary_percent must be an integer between 0 and 100")

        if errors:
            raise RuleConfigError("; ".join(errors))


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
