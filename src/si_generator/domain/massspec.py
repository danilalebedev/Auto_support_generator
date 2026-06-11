from __future__ import annotations

from dataclasses import dataclass

from ..chemistry import calc_hrms_mz, ion_formula


@dataclass(slots=True)
class HRMSCalculation:
    calculated_mz: float
    ion_formula: str


def calculate_hrms(formula: str, adduct: str) -> HRMSCalculation:
    return HRMSCalculation(
        calculated_mz=calc_hrms_mz(formula, adduct),
        ion_formula=ion_formula(formula, adduct),
    )
