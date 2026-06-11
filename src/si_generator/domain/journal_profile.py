from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..config_yaml import parse_simple_yaml
from .types import JournalProfile


BUILTIN_PROFILE_DIR = Path(__file__).resolve().parents[1] / "render" / "journal_profiles"

DEFAULT_JOURNAL_PROFILE: JournalProfile = {
    "id": "default",
    "name": "Default Supporting Information",
    "section_order": ["compound_descriptions", "spectra_appendix"],
    "use_subscripts_in_formulae": True,
    "use_superscript_isotopes": True,
    "use_italic_j": False,
}


def load_journal_profile(profile: str | Path | None = None) -> JournalProfile:
    result: JournalProfile = deepcopy(DEFAULT_JOURNAL_PROFILE)
    profile_path = _resolve_profile_path(profile)
    if not profile_path:
        return result

    data = parse_simple_yaml(profile_path.read_text(encoding="utf-8-sig"))
    _deep_update(result, data)
    if "id" not in data:
        result["id"] = profile_path.stem
    if "docx_template_path" in result:
        result["docx_template_path"] = str(_resolve_profile_relative_path(profile_path, str(result["docx_template_path"])))
    if "word_template" in result:
        result["docx_template_path"] = str(_resolve_profile_relative_path(profile_path, str(result["word_template"])))
    return result


def available_builtin_profiles() -> list[str]:
    if not BUILTIN_PROFILE_DIR.exists():
        return []
    return sorted(path.stem for path in BUILTIN_PROFILE_DIR.glob("*.yml"))


def profile_template_path(profile: JournalProfile, fallback: str | Path | None = None) -> Path | None:
    if fallback:
        return Path(fallback)
    template = profile.get("docx_template_path", "")
    return Path(template) if template else None


def _resolve_profile_path(profile: str | Path | None) -> Path | None:
    if not profile:
        return None
    raw = Path(profile)
    if raw.exists():
        return raw
    if raw.suffix:
        return raw
    builtin = BUILTIN_PROFILE_DIR / f"{profile}.yml"
    return builtin if builtin.exists() else raw


def _resolve_profile_relative_path(profile_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (profile_path.parent / path).resolve()


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
