from __future__ import annotations

import re
from collections import OrderedDict


MONOISOTOPIC_MASS: dict[str, float] = {
    "H": 1.00782503223,
    "C": 12.00000000000,
    "N": 14.00307400443,
    "O": 15.99491461957,
    "F": 18.99840316273,
    "P": 30.97376199842,
    "S": 31.97207117440,
    "Cl": 34.968852682,
    "Br": 78.9183376,
    "I": 126.9044719,
    "B": 11.00930536,
    "Si": 27.97692653465,
    "Na": 22.9897692820,
    "K": 38.9637064864,
}

ELECTRON_MASS = 0.000548579909
_ADDUCT_RE = re.compile(
    r"^\[M(?:(?P<operation>[+-])(?P<component>\d*[A-Z][A-Za-z0-9]*))?\]"
    r"(?P<charge_count>\d*)(?P<charge_sign>[+-])$"
)


def parse_formula(formula: str) -> OrderedDict[str, int]:
    pattern = re.compile(r"([A-Z][a-z]?)(\d*)")
    elements: OrderedDict[str, int] = OrderedDict()
    pos = 0

    for match in pattern.finditer(formula.strip()):
        element, count_text = match.groups()
        if element not in MONOISOTOPIC_MASS:
            raise ValueError(f"Unsupported element in formula: {element}")
        count = int(count_text) if count_text else 1
        elements[element] = elements.get(element, 0) + count
        pos = match.end()

    if pos != len(formula.strip()):
        raise ValueError(f"Could not parse formula completely: {formula}")

    return elements


def formula_mass(formula: str) -> float:
    return sum(MONOISOTOPIC_MASS[element] * count for element, count in parse_formula(formula).items())


def calc_hrms_mz(formula: str, adduct: str) -> float:
    operation, component_multiplier, component_formula, charge = _parse_adduct(adduct)
    ion_mass = formula_mass(formula)
    if component_formula:
        direction = 1 if operation == "+" else -1
        ion_mass += direction * component_multiplier * formula_mass(component_formula)
    ion_mass -= charge * ELECTRON_MASS
    return round(ion_mass / abs(charge), 4)


def ion_formula(formula: str, adduct: str) -> str:
    operation, component_multiplier, component_formula, charge = _parse_adduct(adduct)
    elements = parse_formula(formula)
    if component_formula:
        direction = 1 if operation == "+" else -1
        for element, count in parse_formula(component_formula).items():
            elements[element] = elements.get(element, 0) + direction * component_multiplier * count
            if elements[element] < 0:
                raise ValueError(f"Adduct {adduct} removes more {element} atoms than formula {formula} contains.")
            if elements[element] == 0:
                del elements[element]
    charge_suffix = f"{'^' + str(abs(charge)) if abs(charge) != 1 else ''}{'+' if charge > 0 else '-'}"
    return "".join(element + (str(count) if count != 1 else "") for element, count in elements.items()) + charge_suffix


def _parse_adduct(adduct: str) -> tuple[str, int, str, int]:
    normalized = re.sub(r"\s+", "", adduct)
    match = _ADDUCT_RE.fullmatch(normalized)
    if not match:
        raise ValueError(
            f"Unsupported adduct format: {adduct}. Expected e.g. [M+H]+, [M-H]-, [M]+, or [M+2H]2+."
        )

    operation = match.group("operation") or "+"
    component = match.group("component") or ""
    component_match = re.fullmatch(r"(?:(\d+))?([A-Z][A-Za-z0-9]*)", component) if component else None
    component_multiplier = int(component_match.group(1) or 1) if component_match else 1
    component_formula = component_match.group(2) if component_match else ""
    charge_magnitude = int(match.group("charge_count") or 1)
    if charge_magnitude <= 0:
        raise ValueError(f"Adduct charge must be non-zero: {adduct}")
    charge = charge_magnitude if match.group("charge_sign") == "+" else -charge_magnitude
    return operation, component_multiplier, component_formula, charge
