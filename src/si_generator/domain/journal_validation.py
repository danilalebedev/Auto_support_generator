from __future__ import annotations

import re
from collections.abc import Iterable

from ..chemistry import parse_formula
from ..journal_profiles import get_journal_profile
from .compound import Compound
from .types import Issue


_MISSING_VALUES = {"", "-", "--", "n/a", "na", "none"}


def validate_compounds_for_journal(
    compounds: Iterable[Compound],
    profile_id: str | None,
) -> list[Issue]:
    profile = get_journal_profile(profile_id)
    validation = profile.validation
    issues: list[Issue] = []
    for compound in compounds:
        issues.extend(_validate_compound(compound, profile.label, validation))
    return issues


def _validate_compound(compound: Compound, profile_label: str, validation: dict) -> list[Issue]:
    issues: list[Issue] = []
    for nucleus in validation.get("required_nuclei", []):
        if not _has_nucleus(compound, str(nucleus)):
            issues.append(_warning(compound, "JOURNAL_NMR_REQUIRED", f"{profile_label} requires {nucleus} NMR data."))

    formula_elements = _formula_elements(compound.formula)
    for element, nuclei in dict(validation.get("required_nuclei_by_element", {}) or {}).items():
        if formula_elements.get(str(element), 0) <= 0:
            continue
        for nucleus in nuclei:
            if not _has_nucleus(compound, str(nucleus)):
                issues.append(
                    _warning(
                        compound,
                        "JOURNAL_HETERO_NMR_REQUIRED",
                        f"{profile_label} requires {nucleus} NMR for compounds containing {element}.",
                    )
                )

    formula_evidence = dict(validation.get("formula_evidence", {}) or {})
    if formula_evidence.get("enforcement") == "required_for_new_compounds" and not _has_formula_evidence(compound):
        accepted = ", ".join(str(item).replace("_", " ") for item in formula_evidence.get("any_of", []))
        issues.append(
            _warning(
                compound,
                "JOURNAL_FORMULA_EVIDENCE_REQUIRED",
                f"{profile_label} requires formula/identity evidence for new compounds ({accepted or 'HRMS or elemental analysis'}).",
            )
        )

    if validation.get("require_melting_point_for_crystalline") or validation.get("require_melting_point_when_applicable"):
        if _looks_solid(compound) and _is_missing(compound.melting_point):
            issues.append(_warning(compound, "JOURNAL_MP_REQUIRED", f"{profile_label} requires a melting point when applicable."))

    if validation.get("require_important_ir") and _is_missing_ir(compound.ir):
        issues.append(_warning(compound, "JOURNAL_IR_RECOMMENDED", f"{profile_label} expects important IR absorptions when applicable."))

    issues.extend(_validate_hrms_tolerance(compound, profile_label, validation))
    issues.extend(_validate_elemental_tolerance(compound, profile_label, validation))
    return issues


def _has_nucleus(compound: Compound, nucleus: str) -> bool:
    normalized = nucleus.upper().replace("{1H}", "")
    if normalized == "1H":
        return bool(compound.h1_nmr.strip() or compound.h1_spectrum_path.strip() or compound.h1_image_path.strip())
    if normalized == "13C":
        return bool(compound.c13_nmr.strip() or compound.c13_spectrum_path.strip() or compound.c13_image_path.strip())
    for key, spectrum in compound.nmr_spectra.items():
        candidate = str(spectrum.get("nucleus") or key).upper().replace("{1H}", "")
        if candidate == normalized:
            return True
    return bool(re.search(rf"(?<!\d){re.escape(normalized)}\b", compound.extra_nmr.upper()))


def _has_formula_evidence(compound: Compound) -> bool:
    has_hrms = bool(
        str(compound.hrms.get("found_text") or compound.hrms.get("found_mz") or compound.hrms_found).strip()
    )
    found = dict(compound.elemental_analysis.get("found", {}) or {})
    has_elemental = bool(found or str(compound.elemental_analysis.get("formatted_text") or "").strip())
    return has_hrms or has_elemental


def _validate_hrms_tolerance(compound: Compound, profile_label: str, validation: dict) -> list[Issue]:
    found = _float_or_none(compound.hrms.get("found_mz") or compound.hrms_found)
    calculated = _float_or_none(compound.hrms.get("calculated_mz") or compound.hrms_calculated)
    if found is None or calculated is None or calculated <= 0:
        return []
    delta = abs(found - calculated)
    tolerance_da = validation.get("hrms_tolerance_absolute_da_below_1000")
    tolerance_ppm_high = validation.get("hrms_tolerance_ppm_at_or_above_1000")
    tolerance_ppm = validation.get("hrms_tolerance_ppm")
    exceeded = False
    limit_text = ""
    if calculated < 1000 and tolerance_da is not None:
        exceeded = delta > float(tolerance_da)
        limit_text = f"{float(tolerance_da):g} Da"
    elif calculated >= 1000 and tolerance_ppm_high is not None:
        ppm_error = delta / calculated * 1_000_000
        exceeded = ppm_error > float(tolerance_ppm_high)
        limit_text = f"{float(tolerance_ppm_high):g} ppm"
    elif tolerance_ppm is not None:
        ppm_error = delta / calculated * 1_000_000
        exceeded = ppm_error > float(tolerance_ppm)
        limit_text = f"{float(tolerance_ppm):g} ppm"
    if not exceeded:
        return []
    return [_warning(compound, "JOURNAL_HRMS_TOLERANCE", f"HRMS exceeds the {profile_label} tolerance ({limit_text}).")]


def _validate_elemental_tolerance(compound: Compound, profile_label: str, validation: dict) -> list[Issue]:
    tolerance = validation.get("elemental_analysis_tolerance_percent")
    if tolerance is None:
        return []
    calculated = dict(compound.elemental_analysis.get("calculated", {}) or {})
    found = dict(compound.elemental_analysis.get("found", {}) or {})
    deviations = []
    for element in calculated.keys() & found.keys():
        calc_value = _float_or_none(calculated[element])
        found_value = _float_or_none(found[element])
        if calc_value is not None and found_value is not None and abs(calc_value - found_value) > float(tolerance):
            deviations.append(str(element))
    if not deviations:
        return []
    return [
        _warning(
            compound,
            "JOURNAL_ELEMENTAL_TOLERANCE",
            f"Elemental analysis exceeds the {profile_label} +/-{float(tolerance):g}% tolerance for {', '.join(deviations)}.",
        )
    ]


def _formula_elements(formula: str) -> dict[str, int]:
    if _is_missing(formula):
        return {}
    try:
        return dict(parse_formula(formula))
    except ValueError:
        return {}


def _looks_solid(compound: Compound) -> bool:
    value = f"{compound.color} {compound.state}".lower()
    return any(marker in value for marker in ("solid", "powder", "crystal", "тверд", "твёрд", "порош", "кристалл"))


def _is_missing(value: object) -> bool:
    return str(value or "").strip().lower() in _MISSING_VALUES


def _is_missing_ir(value: object) -> bool:
    if isinstance(value, dict):
        return not bool(value)
    return _is_missing(value)


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _warning(compound: Compound, code: str, message: str) -> Issue:
    return {
        "code": code,
        "severity": "warning",
        "message": f"{compound.number}: {message}" if compound.number else message,
        "compound_id": compound.id or compound.number,
    }
