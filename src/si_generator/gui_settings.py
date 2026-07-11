from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .runtime_paths import gui_settings_path


SETTINGS_VERSION = 1
STRING_FIELDS = (
    "input_path",
    "spectra_source",
    "spectra_zip",
    "template_docx",
    "references_file",
    "loadings_schema_docx",
    "loadings_scope_docx",
    "mnova_exe",
    "mnova_graphics_profile",
    "mnova_graphics_profile_1h",
    "mnova_graphics_profile_13c",
    "output_docx",
    "output_folder",
    "theme_mode",
    "peak_threshold_percent",
    "peak_threshold_1h_percent",
    "peak_threshold_13c_percent",
    "target_signal_height_percent",
    "h1_ppm_min",
    "h1_ppm_max",
    "c13_ppm_min",
    "c13_ppm_max",
    "baseline_poly_order",
    "whittaker_lambda",
    "whittaker_asymmetry",
    "existing_manifest",
    "check_support_docx",
    "patch_output_docx",
    "patch_renumber",
    "patch_remove",
    "patch_reorder",
    "add_previous_output_dir",
    "add_manifest",
    "add_support_docx",
    "add_template_docx",
    "add_loadings_schema_docx",
    "add_loadings_scope_docx",
    "add_input_path",
    "add_spectra_source",
    "add_output_docx",
    "add_output_folder",
    "add_method_mode",
)
BOOL_FIELDS = (
    "check_support",
    "generate_loadings",
    "calculate_elemental_analysis",
    "baseline_apply_1h",
    "baseline_apply_13c",
    "highlight_solvent_peaks",
)
CHOICE_FIELDS = {
    "input_kind": {"word"},
    "add_input_kind": {"word"},
    "add_method_mode": {"same_series", "new_method"},
    "insert_spectra_as": {"png", "mnova", "none"},
    "baseline_mode": {"auto", "off", "bernstein", "whittaker"},
    "theme_mode": {"light", "dark"},
}


def default_gui_settings_path() -> Path:
    return gui_settings_path(environ=os.environ)


def load_gui_settings(path: str | Path | None = None) -> dict[str, str | bool]:
    settings_path = Path(path) if path else default_gui_settings_path()
    if not settings_path.exists():
        return {}
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return normalize_gui_settings(raw)


def save_gui_settings(values: Mapping[str, Any], path: str | Path | None = None) -> Path:
    settings_path = Path(path) if path else default_gui_settings_path()
    settings = normalize_gui_settings(values)
    payload = {"version": SETTINGS_VERSION, "settings": settings}
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = settings_path.with_suffix(settings_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(settings_path)
    return settings_path


def normalize_gui_settings(raw: Mapping[str, Any]) -> dict[str, str | bool]:
    source = raw.get("settings", raw)
    if not isinstance(source, Mapping):
        return {}

    settings: dict[str, str | bool] = {}
    for field in STRING_FIELDS:
        if field in source and source[field] is not None:
            settings[field] = str(source[field])
    for field in BOOL_FIELDS:
        if field in source:
            settings[field] = _bool_value(source[field])
    for field, allowed in CHOICE_FIELDS.items():
        value = str(source.get(field, "")).strip().lower()
        if value in allowed:
            settings[field] = value
    _migrate_legacy_mngp_settings(settings)
    return settings


def _bool_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _migrate_legacy_mngp_settings(settings: dict[str, str | bool]) -> None:
    raw_profile = str(settings.get("mnova_graphics_profile", "")).strip().strip('"')
    if not raw_profile:
        return

    path = Path(raw_profile)
    name = path.name.lower()
    if name not in {"classic.mngp", "grid.mngp"}:
        return

    stem = "classic" if name == "classic.mngp" else "grid"
    if not str(settings.get("mnova_graphics_profile_1h", "")).strip():
        settings["mnova_graphics_profile_1h"] = str(path.with_name(f"{stem}_1H.mngp"))
    if not str(settings.get("mnova_graphics_profile_13c", "")).strip():
        settings["mnova_graphics_profile_13c"] = str(path.with_name(f"{stem}_13C.mngp"))
    settings["mnova_graphics_profile"] = ""
