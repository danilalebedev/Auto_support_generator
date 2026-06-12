from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.loadings_workflow import LoadingsWorkflowPaths
from ...domain.loadings_workflow import apply_loadings_workflow
from ...domain.reactions import calculate_reaction_loadings
from ...domain.requests import GenerateSIRequest
from ...domain.types import Issue


def calculate_loadings_node(state: GenerateSIState) -> dict:
    generation_config = state.get("generation_config", {})
    compounds = ordered_compounds(state)
    changed = False

    if generation_config.get("generate_loadings", False):
        request = state.get("request")
        if request is not None:
            paths, path_issues = _loadings_paths_from_request(request)
            if path_issues:
                state.setdefault("issues", []).extend(path_issues)
                issues = []
            else:
                issues = apply_loadings_workflow(compounds, request.input_base_dir, paths=paths)
            if issues:
                state.setdefault("issues", []).extend(issues)
            changed = bool(issues) or any(compound.reaction.get("source") == "loadings_workflow" for compound in compounds)

    if not generation_config.get("generate_loadings", False) and not any(compound.reaction for compound in compounds):
        return {}

    for compound in compounds:
        if compound.reaction:
            compound.reaction = calculate_reaction_loadings(compound.reaction)
            changed = True

    result: dict = {}
    if changed:
        result["compounds"] = state.get("compounds", {})
    if state.get("issues"):
        result["issues"] = state.get("issues", [])
    return result


def _loadings_paths_from_request(request: GenerateSIRequest) -> tuple[LoadingsWorkflowPaths | None, list[Issue]]:
    paths = [request.loadings_schema_docx, request.loadings_scope_docx, request.loadings_template_docx]
    if not any(paths):
        return None, []
    if not all(paths):
        return (
            None,
            [
                {
                    "code": "LOADINGS_FILES_INCOMPLETE",
                    "severity": "error",
                    "message": "Choose all three reagent loadings files or leave all fields empty for auto-detect.",
                }
            ],
        )
    return LoadingsWorkflowPaths(paths[0], paths[1], paths[2]), []
