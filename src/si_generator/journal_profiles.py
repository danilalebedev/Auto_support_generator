from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


PROFILE_CATALOG_NAME = "profiles.json"
DEFAULT_JOURNAL_PROFILE_ID = "organic.default"
LEGACY_PROFILE_LABELS = {
    "ACS - Journal of Organic Chemistry": "acs.joc",
    "ACS - Organic Letters": "acs.orglett",
}


@dataclass(frozen=True, slots=True)
class JournalProfile:
    id: str
    label: str
    publisher: str
    version: str
    checked_date: str
    visible: bool
    data: dict[str, Any]
    resource_dir: Path

    @property
    def template_path(self) -> Path:
        filename = str(self.data.get("document", {}).get("template_docx") or "").strip()
        return self.resource_dir / filename if filename else Path()

    @property
    def source_urls(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.data.get("source_urls", []) if str(item).strip())

    @property
    def spectra(self) -> dict[str, Any]:
        return dict(self.data.get("spectra", {}) or {})

    @property
    def validation(self) -> dict[str, Any]:
        return dict(self.data.get("validation", {}) or {})

    @property
    def packaging(self) -> dict[str, Any]:
        return dict(self.data.get("packaging", {}) or {})

    def mngp_path(self, nucleus: str) -> Path | None:
        key = "mngp_1h" if nucleus.upper() == "1H" else "mngp_13c"
        filename = str(self.spectra.get(key) or "").strip()
        if not filename:
            return None
        return _mngp_resource_dir() / filename


def list_journal_profiles(*, include_hidden: bool = False) -> tuple[JournalProfile, ...]:
    profiles = tuple(_load_profiles().values())
    if not include_hidden:
        profiles = tuple(profile for profile in profiles if profile.visible)
    return tuple(sorted(profiles, key=lambda profile: (profile.publisher.lower(), profile.label.lower())))


def get_journal_profile(profile_id: str | None) -> JournalProfile:
    requested = str(profile_id or DEFAULT_JOURNAL_PROFILE_ID).strip().lower()
    profiles = _load_profiles()
    if requested not in profiles:
        available = ", ".join(profile.id for profile in list_journal_profiles())
        raise ValueError(f"Unknown journal profile '{requested}'. Available profiles: {available}")
    return profiles[requested]


def journal_profile_labels() -> dict[str, str]:
    return {profile.label: profile.id for profile in list_journal_profiles()}


def journal_profile_label(profile_id: str | None) -> str:
    return get_journal_profile(profile_id).label


def resolve_journal_profile_id(label_or_id: str | None) -> str:
    raw = str(label_or_id or "").strip()
    if not raw:
        return DEFAULT_JOURNAL_PROFILE_ID
    labels = journal_profile_labels()
    return labels.get(raw, LEGACY_PROFILE_LABELS.get(raw, raw))


def journal_profile_manifest_block(profile_id: str | None, *, user_overrides: Iterable[str] = ()) -> dict[str, Any]:
    profile = get_journal_profile(profile_id)
    return {
        "id": profile.id,
        "label": profile.label,
        "publisher": profile.publisher,
        "profile_version": profile.version,
        "requirements_checked": profile.checked_date,
        "source_urls": list(profile.source_urls),
        "template_docx": profile.template_path.name,
        "visual_style_status": str(profile.data.get("document", {}).get("visual_style_status") or "house_default"),
        "user_overrides": sorted({str(item) for item in user_overrides if str(item).strip()}),
    }


def journal_profile_defaults(profile_id: str | None) -> dict[str, Any]:
    profile = get_journal_profile(profile_id)
    spectra = profile.spectra
    return {
        "template_docx": profile.template_path,
        "mnova_graphics_profile_1h": profile.mngp_path("1H"),
        "mnova_graphics_profile_13c": profile.mngp_path("13C"),
        "x_range_ppm_1h": _float_pair(spectra.get("x_range_ppm_1h"), (-1.0, 12.0)),
        "x_range_ppm_13c": _float_pair(spectra.get("x_range_ppm_13c"), (-10.0, 210.0)),
        "insert_spectra_as": str(spectra.get("insert_spectra_as") or "png"),
        "target_signal_height_fraction": float(spectra.get("target_signal_height_fraction", 0.80)),
    }


def validate_profile_resources(profile: JournalProfile) -> list[str]:
    problems: list[str] = []
    if not profile.template_path.exists():
        problems.append(f"template does not exist: {profile.template_path}")
    for nucleus in ("1H", "13C"):
        mngp = profile.mngp_path(nucleus)
        if mngp and not mngp.exists():
            problems.append(f"{nucleus} mngp does not exist: {mngp}")
    return problems


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, JournalProfile]:
    resource_dir = _profile_resource_dir()
    catalog_path = resource_dir / PROFILE_CATALOG_NAME
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    definitions = raw.get("profiles", {})
    if not isinstance(definitions, dict):
        raise ValueError(f"{catalog_path}: 'profiles' must be an object")

    resolved: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()

    def resolve(profile_id: str) -> dict[str, Any]:
        if profile_id in resolved:
            return resolved[profile_id]
        if profile_id in visiting:
            raise ValueError(f"Journal profile inheritance cycle at '{profile_id}'")
        definition = definitions.get(profile_id)
        if not isinstance(definition, dict):
            raise ValueError(f"Unknown inherited journal profile '{profile_id}'")
        visiting.add(profile_id)
        parent_id = str(definition.get("inherits") or "").strip()
        base = resolve(parent_id) if parent_id else {}
        merged = _deep_merge(base, definition)
        merged["id"] = profile_id
        visiting.remove(profile_id)
        resolved[profile_id] = merged
        return merged

    result: dict[str, JournalProfile] = {}
    for profile_id in definitions:
        data = resolve(str(profile_id))
        result[str(profile_id)] = JournalProfile(
            id=str(profile_id),
            label=str(data.get("label") or profile_id),
            publisher=str(data.get("publisher") or "Other"),
            version=str(data.get("version") or raw.get("catalog_version") or "1"),
            checked_date=str(data.get("checked_date") or raw.get("checked_date") or ""),
            visible=bool(data.get("visible", True)),
            data=data,
            resource_dir=resource_dir,
        )
    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if key == "inherits":
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _float_pair(value: Any, fallback: tuple[float, float]) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return fallback
    return float(value[0]), float(value[1])


def _profile_resource_dir() -> Path:
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "si_generator" / "templates" / "journals")
    candidates.extend(
        [
            Path(__file__).resolve().parent / "templates" / "journals",
            Path(__file__).resolve().parents[2] / "src" / "si_generator" / "templates" / "journals",
        ]
    )
    return next((path for path in candidates if (path / PROFILE_CATALOG_NAME).exists()), candidates[0])


def _mngp_resource_dir() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    candidates = []
    if bundle_root:
        candidates.append(Path(bundle_root) / "mngp_styles")
    candidates.extend(
        [
            Path(__file__).resolve().parent / "resources" / "mngp_styles",
            Path(__file__).resolve().parents[2] / "src" / "si_generator" / "resources" / "mngp_styles",
        ]
    )
    return next((path for path in candidates if path.exists()), candidates[0])
