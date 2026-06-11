from __future__ import annotations

import re
from typing import Any

from ..chemistry import parse_formula
from .types import ElementalAnalysisBlock


DEFAULT_ELEMENTS = ("C", "H", "N")
AVERAGE_ATOMIC_WEIGHT = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "P": 30.974,
    "S": 32.06,
    "Cl": 35.45,
    "Br": 79.904,
    "I": 126.904,
    "B": 10.81,
    "Si": 28.085,
    "Na": 22.990,
    "K": 39.098,
}


def calculate_elemental_analysis_block(
    formula: str,
    found: dict[str, float] | str | None = None,
    elements: tuple[str, ...] = DEFAULT_ELEMENTS,
) -> ElementalAnalysisBlock:
    found_percentages = parse_found_percentages(found)
    calculated = calculate_elemental_percentages(formula, _analysis_elements(elements, found_percentages))
    block: ElementalAnalysisBlock = {
        "formula": formula,
        "calculated": calculated,
        "found": found_percentages,
    }
    block["formatted_text"] = format_elemental_analysis(block)
    return block


def calculate_elemental_percentages(formula: str, elements: tuple[str, ...] = DEFAULT_ELEMENTS) -> dict[str, float]:
    formula_elements = parse_formula(formula)
    total_mass = sum(AVERAGE_ATOMIC_WEIGHT[element] * count for element, count in formula_elements.items())
    percentages: dict[str, float] = {}
    for element in elements:
        count = formula_elements.get(element, 0)
        if count:
            percentages[element] = round(AVERAGE_ATOMIC_WEIGHT[element] * count / total_mass * 100, 2)
    return percentages


def parse_found_percentages(value: dict[str, float] | str | None) -> dict[str, float]:
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(element): round(float(percent), 2) for element, percent in value.items()}

    found: dict[str, float] = {}
    for match in re.finditer(r"([A-Z][a-z]?)\s*[:,=]?\s*(\d+(?:[\.,]\d+)?)", str(value)):
        found[match.group(1)] = round(float(match.group(2).replace(",", ".")), 2)
    return found


def format_elemental_analysis(block: ElementalAnalysisBlock) -> str:
    formula = str(block.get("formula", "")).strip()
    calculated = block.get("calculated", {})
    found = block.get("found", {})
    elements = _format_elements(calculated, found)
    if not elements:
        return ""

    calculated_text = "; ".join(f"{element}, {calculated[element]:.2f}" for element in elements if element in calculated)
    formula_text = f" for {formula}" if formula else ""
    if found:
        found_text = "; ".join(f"{element}, {found[element]:.2f}" for element in elements if element in found)
        return f"Anal. Calcd{formula_text}: {calculated_text}. Found: {found_text}."
    return f"Anal. Calcd{formula_text}: {calculated_text}."


def found_from_block(value: Any) -> dict[str, float] | str | None:
    if isinstance(value, dict):
        return value.get("found", {})
    if isinstance(value, str):
        return value
    return None


def _analysis_elements(default_elements: tuple[str, ...], found: dict[str, float]) -> tuple[str, ...]:
    elements: list[str] = list(default_elements)
    for element in found:
        if element not in elements:
            elements.append(element)
    return tuple(elements)


def _format_elements(calculated: dict[str, float], found: dict[str, float]) -> list[str]:
    elements = list(calculated)
    for element in found:
        if element not in elements:
            elements.append(element)
    return elements
