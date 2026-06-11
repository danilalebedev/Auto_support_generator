from __future__ import annotations

from ..state import GenerateSIState, Issue
from ...input_validation import validate_compound_inputs
from ...nmr_validation import validate_support


def validate_input_node(state: GenerateSIState) -> dict:
    request = state["request"]
    warnings = validate_compound_inputs(state.get("compounds", []), require_structure=request.input_kind == "word")
    issues: list[Issue] = list(state.get("issues", []))
    for warning in warnings:
        print(f"[Input warning] {warning}", flush=True)
        issues.append({"code": "INPUT_WARNING", "severity": "warning", "message": warning})
    return {"issues": issues}


def validate_support_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = state.get("compounds", [])
    if not request.no_check_support:
        validate_support(compounds)
    return {"compounds": compounds}

