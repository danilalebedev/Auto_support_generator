from __future__ import annotations

import re

from .chemistry import parse_formula
from .domain.elemental_analysis import calculate_elemental_analysis_block, found_from_block
from .domain.massspec import calculate_hrms
from .domain.types import Issue
from .models import Compound


def validate_support(compounds: list[Compound]) -> None:
    _reset_validation(compounds)
    validate_nmr_counts(compounds)
    validate_hrms(compounds)
    validate_elemental_analysis(compounds)


def validate_nmr_counts(compounds: list[Compound]) -> None:
    for compound in compounds:
        if not compound.formula:
            continue

        try:
            formula = parse_formula(compound.formula)
        except ValueError as exc:
            _append_validation_issue(compound, "FORMULA_CHECK_FAILED", f"Formula could not be checked: {exc}")
            continue
        expected_h = formula.get("H", 0)
        expected_c = formula.get("C", 0)

        if compound.h1_nmr:
            found_h = count_h_from_1h_nmr(compound.h1_nmr)
            if found_h != expected_h:
                _append_validation_issue(compound, "NMR_H_COUNT_MISMATCH", f"H expected {expected_h}, found {found_h}")

        if compound.c13_nmr:
            found_c = count_c_from_13c_nmr(compound.c13_nmr)
            fluorine_split_allowance = formula.get("F", 0)
            if found_c < expected_c:
                _append_validation_issue(compound, "NMR_C_COUNT_MISMATCH", f"C expected {expected_c}, found {found_c}")
            elif found_c > expected_c + fluorine_split_allowance:
                _append_validation_issue(compound, "NMR_C_COUNT_MISMATCH", f"C expected {expected_c}, found {found_c}")


def validate_hrms(compounds: list[Compound], tolerance_da: float = 0.005) -> None:
    for compound in compounds:
        found_text = _hrms_found_text(compound)
        if not compound.formula or not found_text:
            continue
        try:
            calcd = compound.hrms_calculated or float(compound.hrms.get("calculated_mz") or 0) or calculate_hrms(compound.formula, _hrms_adduct(compound)).calculated_mz
            found = float(found_text)
        except (ValueError, TypeError):
            _append_validation_issue(compound, "HRMS_CHECK_FAILED", "HRMS could not be checked")
            continue
        if abs(found - calcd) > tolerance_da:
            _append_validation_issue(compound, "HRMS_MISMATCH", f"HRMS calcd {calcd:.4f}, found {found:.4f}")


def validate_elemental_analysis(compounds: list[Compound], tolerance_percent: float = 0.4) -> None:
    for compound in compounds:
        if not compound.formula or not compound.elemental_analysis:
            continue
        found = found_from_block(compound.elemental_analysis)
        if not found:
            continue
        try:
            block = calculate_elemental_analysis_block(compound.formula, found=found)
        except ValueError as exc:
            _append_validation_issue(compound, "ELEMENTAL_ANALYSIS_CHECK_FAILED", f"Elemental analysis could not be checked: {exc}")
            continue
        compound.elemental_analysis = block
        for element, found_value in block.get("found", {}).items():
            calculated_value = block.get("calculated", {}).get(element)
            if calculated_value is None:
                continue
            if abs(found_value - calculated_value) > tolerance_percent:
                _append_validation_issue(compound, "ELEMENTAL_ANALYSIS_MISMATCH", f"EA {element} calcd {calculated_value:.2f}, found {found_value:.2f}")


def _reset_validation(compounds: list[Compound]) -> None:
    for compound in compounds:
        compound.nmr_check_warning = ""
        compound.validation_issues = []


def _append_validation_issue(compound: Compound, code: str, text: str) -> None:
    issue: Issue = {
        "code": code,
        "severity": "warning",
        "message": text,
        "compound_id": compound.id or compound.number,
    }
    compound.validation_issues.append(issue)
    _append_warning(compound, text)


def _append_warning(compound: Compound, text: str) -> None:
    if compound.nmr_check_warning:
        compound.nmr_check_warning += "; " + text
    else:
        compound.nmr_check_warning = text


def _hrms_found_text(compound: Compound) -> str:
    value = compound.hrms_found or compound.hrms.get("found_text") or compound.hrms.get("found_mz") or ""
    return str(value).strip()


def _hrms_adduct(compound: Compound) -> str:
    return str(compound.hrms.get("adduct") or compound.hrms_adduct)


def count_h_from_1h_nmr(text: str) -> int:
    text = _normalize_chem_letters(text)
    # Match integral labels like "1H", "2H", including "2H+2H".
    total = 0
    for match in re.finditer(r"(?<![A-Za-z0-9.])(\d+)\s*H\b", text, flags=re.IGNORECASE):
        total += int(match.group(1))
    return total


def count_c_from_13c_nmr(text: str) -> int:
    text = _normalize_chem_letters(text)
    data = _strip_delta_prefix(text)
    assignments = _top_level_parens(data)
    assigned_count = sum(_count_c_assignment(env) for env in assignments)
    if assigned_count:
        return assigned_count
    return _count_13c_peak_items(data)


def _count_c_assignment(env: str) -> int:
    env = re.sub(r"\b\d+J[^,)]*", "", env)

    plain = re.search(r"\b(\d+)\s*C\b", env, flags=re.IGNORECASE)
    if plain:
        return int(plain.group(1))

    total = 0
    for raw_token in env.split(","):
        token = raw_token.strip()
        if not token:
            continue

        mult_match = re.match(r"(\d+)\s*[xX*]\s*(.+)", token)
        if mult_match:
            mult = int(mult_match.group(1))
            body = mult_match.group(2)
        else:
            mult = 1
            body = token

        body_upper = body.upper()
        if "CO2ME" in body_upper or "CO2CH3" in body_upper or "ME" in body_upper:
            total += mult
            continue

        matches = re.findall(r"C(?!O2ME|O2CH3)", body_upper)
        total += mult * len(matches)

    return total


def _count_13c_peak_items(data: str) -> int:
    total = 0
    for item in _split_top_level_commas(data):
        item = item.strip()
        if not re.match(r"^-?\d+(?:\.\d+)?\b", item):
            continue
        mult = 1
        mult_match = re.search(r"\(\s*(\d+)\s*C\b", item, flags=re.IGNORECASE)
        if mult_match:
            mult = int(mult_match.group(1))
        total += mult
    return total


def _strip_delta_prefix(text: str) -> str:
    text = re.sub(r"^.*?\u03b4\s*=?\s*", "", text)
    return re.sub(r"^\s*=?\s*", "", text)


def _top_level_parens(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = None
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                result.append(text[start:index])
                start = None
    return result


def _split_top_level_commas(text: str) -> list[str]:
    result = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index])
            start = index + 1
    result.append(text[start:])
    return [item for item in result if item.strip()]


def _normalize_chem_letters(text: str) -> str:
    return text.translate(str.maketrans({"С": "C", "с": "c", "Н": "H", "н": "h"}))
