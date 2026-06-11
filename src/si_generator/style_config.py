from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_STYLE_CONFIG: dict[str, Any] = {
    "document": {
        "base_style": "Normal",
    },
    "compound": {
        "title": {
            "paragraph_style": "",
            "bold": True,
            "italic": False,
        },
        "number": {
            "bold": True,
            "italic": False,
        },
        "structure": {
            "top_offset_pt": 12,
            "wrap": "square",
            "distance_right_pt": 8,
        },
        "summary": {
            "paragraph_style": "",
            "line_spacing": 1.5,
        },
    },
    "nmr": {
        "paragraph_style": "",
        "label": {
            "bold": True,
            "italic": False,
        },
        "conditions": {
            "bold": False,
            "italic": False,
        },
        "body": {
            "bold": False,
            "italic": False,
        },
    },
    "chem_formatting": {
        "formulas": {
            "subscripts": True,
        },
        "isotope_numbers": {
            "superscript": True,
        },
        "coupling_constants": {
            "order_superscript": False,
            "j_italic": False,
            "coupling_partner_subscript": False,
        },
        "ranges": {
            "en_dash": False,
        },
    },
    "hrms": {
        "paragraph_style": "",
        "label": {
            "bold": True,
            "italic": False,
        },
        "formula": {
            "subscripts": True,
            "charge_superscript": True,
            "isotope_labels": True,
            "isotope_label_superscript": True,
        },
        "adduct": {
            "superscript_charge": False,
        },
    },
    "ir": {
        "paragraph_style": "",
        "label": {
            "bold": True,
            "italic": False,
        },
        "unit": {
            "superscript_minus_one": True,
        },
    },
    "appendix": {
        "title": {
            "paragraph_style": "",
            "bold": True,
            "italic": False,
        },
        "spectrum_title": {
            "paragraph_style": "",
            "bold": True,
            "italic": False,
        },
        "structure": {
            "top_offset_pt": 0,
            "wrap": "in_front",
        },
        "image": {
            "width": "page",
            "align": "center",
        },
    },
    "references": {
        "title": {
            "paragraph_style": "",
            "bold": True,
            "italic": False,
        },
        "body": {
            "paragraph_style": "",
            "bold": False,
            "italic": False,
        },
    },
}


def load_style_config(path: str | Path | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_STYLE_CONFIG)
    if not path:
        return config
    data = parse_simple_yaml(Path(path).read_text(encoding="utf-8-sig"))
    _deep_update(config, data)
    return config


def config_get(config: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def apply_run_style(run, config: dict[str, Any], path: str) -> None:
    section = config_get(config, path, {})
    if not isinstance(section, dict):
        return
    if "bold" in section:
        run.bold = bool(section["bold"])
    if "italic" in section:
        run.italic = bool(section["italic"])


def apply_paragraph_style(paragraph, config: dict[str, Any], path: str) -> None:
    style_name = config_get(config, f"{path}.paragraph_style", "")
    if isinstance(style_name, str) and style_name:
        try:
            paragraph.style = style_name
        except KeyError:
            pass
    line_spacing = config_get(config, f"{path}.line_spacing", None)
    if isinstance(line_spacing, int | float | str) and line_spacing != "":
        paragraph.paragraph_format.line_spacing = float(line_spacing)


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)

    return root


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(item.strip()) for item in body.split(",")]
    if value.lower() in {"true", "yes", "on"}:
        return True
    if value.lower() in {"false", "no", "off"}:
        return False
    if value.lower() in {"null", "none"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
