from __future__ import annotations

import re

from .types import XRDBlock


def xrd_from_fields(fields: dict[str, str]) -> XRDBlock:
    block: XRDBlock = {}
    formatted_text = _first_value(fields, "xrd", "xrd_text", "xrd_formatted_text")
    ccdc_number = _first_value(fields, "ccdc", "ccdc_number")
    cif_path = _first_value(fields, "cif", "cif_path")
    checkcif_path = _first_value(fields, "checkcif", "checkcif_path", "check_cif", "check_cif_path")
    table_path = _first_value(fields, "xrd_table", "xrd_table_path", "crystal_table", "crystal_table_path")
    figure_paths = _split_paths(_first_value(fields, "xrd_figures", "xrd_figure_paths", "crystal_figures"))

    if formatted_text:
        block["formatted_text"] = formatted_text
    if ccdc_number:
        block["ccdc_number"] = ccdc_number
    if cif_path:
        block["cif_path"] = cif_path
    if checkcif_path:
        block["checkcif_path"] = checkcif_path
    if table_path:
        block["table_path"] = table_path
    if figure_paths:
        block["figure_paths"] = figure_paths
    return block


def xrd_formatted_text(block: XRDBlock) -> str:
    text = str(block.get("formatted_text") or "").strip()
    if text:
        return _ensure_sentence(text)

    ccdc_number = str(block.get("ccdc_number") or "").strip()
    cif_path = str(block.get("cif_path") or "").strip()
    if ccdc_number and cif_path:
        return f"XRD: crystallographic data are provided in the CIF file; CCDC {ccdc_number}."
    if ccdc_number:
        return f"XRD: CCDC {ccdc_number}."
    if cif_path:
        return "XRD: crystallographic data are provided in the CIF file."
    return ""


def xrd_artifacts(block: XRDBlock) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for key in ("cif_path", "checkcif_path", "table_path"):
        value = str(block.get(key) or "").strip()
        if value:
            artifacts[_artifact_key(key)] = value
    for index, value in enumerate(block.get("figure_paths", []) or [], start=1):
        path = str(value or "").strip()
        if path:
            artifacts[f"xrd_figure_{index}"] = path
    return artifacts


def _first_value(fields: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = str(fields.get(key) or "").strip()
        if value:
            return value
    return ""


def _split_paths(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;\n]+", value) if part.strip()]


def _ensure_sentence(text: str) -> str:
    return text if text[-1:] in ".!?" else f"{text}."


def _artifact_key(field_key: str) -> str:
    return {
        "cif_path": "xrd_cif",
        "checkcif_path": "xrd_checkcif",
        "table_path": "xrd_table",
    }[field_key]
