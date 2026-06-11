from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.input_validation import validate_compound_inputs
from ...nmr_validation import validate_support


def validate_input_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    warnings = validate_compound_inputs(
        compounds,
        require_structure=request.input_kind == "word",
        base_dir=request.input_base_dir,
    )
    warnings.extend(_reference_warnings(compounds, state))
    issues: list[Issue] = list(state.get("issues", []))
    for warning in warnings:
        print(f"[Input warning] {warning}", flush=True)
        issues.append(_input_warning_issue(warning, state))
    result = {"issues": issues}
    if warnings:
        log_path = request.output_dir / "logs" / "input_warnings.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        result["artifacts"] = {**state.get("artifacts", {}), "input_warnings": str(log_path)}
    return result


def _input_warning_issue(warning: str, state: GenerateSIState) -> Issue:
    issue: Issue = {"code": "INPUT_WARNING", "severity": "warning", "message": warning}
    compound_id = _compound_id_from_warning(warning, state)
    if compound_id:
        issue["compound_id"] = compound_id
    return issue


def _compound_id_from_warning(warning: str, state: GenerateSIState) -> str:
    label = warning.split(":", 1)[0].strip()
    if not label or label == warning:
        return ""
    for compound_id, compound in state.get("compounds", {}).items():
        if compound.number == label:
            return compound_id
    return ""


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
    generation_config = state.get("generation_config", {})
    check_support = bool(generation_config.get("check_support", not request.no_check_support))
    if check_support:
        validate_support(compounds)
    issues: list[Issue] = list(state.get("issues", []))
    warnings = []
    for compound in compounds:
        if compound.nmr_check_warning:
            message = f"{compound.number}: {compound.nmr_check_warning}" if compound.number else compound.nmr_check_warning
            warnings.append(message)
            validation_issues = getattr(compound, "validation_issues", [])
            if validation_issues:
                issues.extend(validation_issues)
            else:
                issues.append(
                    {
                        "code": "SUPPORT_CHECK_WARNING",
                        "severity": "warning",
                        "message": message,
                        "compound_id": compound.id or compound.number,
                    }
                )

    result = {"compounds": state.get("compounds", {}), "issues": issues}
    if warnings:
        log_path = request.output_dir / "logs" / "support_warnings.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        result["artifacts"] = {**state.get("artifacts", {}), "support_warnings": str(log_path)}
    return result

