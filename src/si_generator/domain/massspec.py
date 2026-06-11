from __future__ import annotations

from dataclasses import dataclass

from ..chemistry import calc_hrms_mz, ion_formula
from ..chemistry import parse_formula
from .types import HRMSBlock


DEFAULT_HALOGEN_ISOTOPES = {
    "Cl": 35,
    "Br": 79,
}


@dataclass(slots=True)
class HRMSCalculation:
    calculated_mz: float
    ion_formula: str
    isotope_policy: str = "auto_halogen"
    isotope_labels: dict[str, int] | None = None


def calculate_hrms(
    formula: str,
    adduct: str,
    *,
    isotope_policy: str = "auto_halogen",
    isotope_labels: dict[str, int] | None = None,
) -> HRMSCalculation:
    labels = isotope_labels or _isotope_labels_for_policy(formula, isotope_policy)
    return HRMSCalculation(
        calculated_mz=calc_hrms_mz(formula, adduct),
        ion_formula=ion_formula(formula, adduct),
        isotope_policy=isotope_policy,
        isotope_labels=labels,
    )


def build_hrms_block(
    *,
    formula: str,
    label: str,
    adduct: str,
    found_text: str,
    isotope_policy: str = "auto_halogen",
    isotope_labels: dict[str, int] | None = None,
) -> HRMSBlock:
    calculation = calculate_hrms(
        formula,
        adduct,
        isotope_policy=isotope_policy,
        isotope_labels=isotope_labels,
    )
    block: HRMSBlock = {
        "label": label,
        "adduct": adduct,
        "found_text": found_text,
        "calculated_mz": calculation.calculated_mz,
        "ion_formula": calculation.ion_formula,
        "isotope_policy": calculation.isotope_policy,
        "isotope_labels": calculation.isotope_labels or {},
    }
    try:
        block["found_mz"] = parse_mz_value(found_text)
    except (TypeError, ValueError):
        pass
    return block


def parse_mz_value(value: object) -> float:
    return float(str(value).strip().replace(",", "."))


def hrms_found_text(block: HRMSBlock | None, legacy_found: str = "") -> str:
    block = block or {}
    value = legacy_found or block.get("found_text") or block.get("found_mz") or ""
    return str(value).strip()


def hrms_adduct_text(block: HRMSBlock | None, legacy_adduct: str) -> str:
    block = block or {}
    return str(block.get("adduct") or legacy_adduct)


def hrms_label_text(block: HRMSBlock | None, legacy_label: str) -> str:
    block = block or {}
    return str(block.get("label") or legacy_label)


def _isotope_labels_for_policy(formula: str, isotope_policy: str) -> dict[str, int]:
    if isotope_policy != "auto_halogen":
        return {}
    elements = parse_formula(formula)
    return {element: mass_number for element, mass_number in DEFAULT_HALOGEN_ISOTOPES.items() if elements.get(element, 0)}
