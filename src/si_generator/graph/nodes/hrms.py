from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.massspec import build_hrms_block


def calculate_hrms_node(state: GenerateSIState) -> dict:
    issues: list[Issue] = list(state.get("issues", []))

    for compound in ordered_compounds(state):
        found_text = _hrms_found_text(compound)
        if not compound.formula or not found_text:
            continue
        try:
            result = build_hrms_block(
                formula=compound.formula,
                label=str(compound.hrms.get("label") or compound.hrms_label),
                adduct=str(compound.hrms.get("adduct") or compound.hrms_adduct),
                found_text=found_text,
                isotope_policy=str(compound.hrms.get("isotope_policy", "auto_halogen")),
                isotope_labels=compound.hrms.get("isotope_labels"),
            )
        except ValueError as exc:
            issues.append(
                {
                    "code": "HRMS_CALCULATION_FAILED",
                    "severity": "warning",
                    "compound_id": compound.id,
                    "message": str(exc),
                }
            )
            continue
        compound.hrms = result
        if not compound.hrms_found:
            compound.hrms_found = found_text
        compound.hrms_calculated = float(result["calculated_mz"])
        compound.hrms_ion_formula = str(result["ion_formula"])

    return {"compounds": state.get("compounds", {}), "issues": issues}


def _hrms_found_text(compound) -> str:
    value = compound.hrms_found or compound.hrms.get("found_text") or compound.hrms.get("found_mz") or ""
    return str(value).strip()
