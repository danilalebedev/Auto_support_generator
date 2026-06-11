from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...input_validation import validate_compound_inputs
from ...nmr_validation import validate_support


def validate_input_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    warnings = validate_compound_inputs(compounds, require_structure=request.input_kind == "word")
    warnings.extend(_reference_warnings(compounds, state))
    issues: list[Issue] = list(state.get("issues", []))
    for warning in warnings:
        print(f"[Input warning] {warning}", flush=True)
        issues.append({"code": "INPUT_WARNING", "severity": "warning", "message": warning})
    return {"issues": issues}


def _reference_warnings(compounds, state: GenerateSIState) -> list[str]:
    warnings: list[str] = []
    reference_store = state.get("reference_store", {})
    references = reference_store.get("references", {}) if isinstance(reference_store, dict) else {}
    any_reference_keys = any(compound.references for compound in compounds)
    if any_reference_keys and not references:
        return ["references are listed in the input table, but no references file was loaded."]
    for compound in compounds:
        for key in compound.references:
            if key not in references:
                warnings.append(f"{compound.number}: reference '{key}' was not found in the references file.")
    return warnings


def validate_support_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    if not request.no_check_support:
        validate_support(compounds)
    return {"compounds": state.get("compounds", {})}

