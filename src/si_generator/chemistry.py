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
    match = re.fullmatch(r"\[M([+-])([A-Za-z0-9]+)\]\+", adduct.strip())
    if not match:
        raise ValueError(f"Unsupported adduct format: {adduct}. Expected e.g. [M+H]+ or [M+Na]+.")

    sign_text, adduct_formula = match.groups()
    sign = 1 if sign_text == "+" else -1
    ion_mass = formula_mass(formula) + sign * formula_mass(adduct_formula) - ELECTRON_MASS
    return round(ion_mass, 4)


def ion_formula(formula: str, adduct: str) -> str:
    match = re.fullmatch(r"\[M([+-])([A-Za-z0-9]+)\]\+", adduct.strip())
    if not match:
        return formula

    sign_text, adduct_formula = match.groups()
    elements = parse_formula(formula)
    for element, count in parse_formula(adduct_formula).items():
        elements[element] = elements.get(element, 0) + (count if sign_text == "+" else -count)
        if elements[element] == 0:
            del elements[element]
    return "".join(element + (str(count) if count != 1 else "") for element, count in elements.items()) + "+"
