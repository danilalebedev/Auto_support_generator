from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.loadings_workflow import LoadingsWorkflowPaths
from ...domain.loadings_workflow import apply_loadings_workflow
from ...domain.reactions import calculate_reaction_loadings
from ...domain.requests import GenerateSIRequest
from ...domain.types import Issue
from ...journal_profiles import list_journal_profiles


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
                issues = apply_loadings_workflow(
                    compounds,
                    request.input_base_dir,
                    paths=paths,
                    template_docx=_method_template_from_request(request),
                )
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
    paths = [request.loadings_schema_docx, request.loadings_scope_docx]
    if not any(paths):
        return None, []
    if not all(paths):
        return (
            None,
            [
                {
                    "code": "LOADINGS_FILES_INCOMPLETE",
                    "severity": "error",
                    "message": "Choose both reagent loadings files or leave both fields empty for auto-detect.",
                }
            ],
        )
    return LoadingsWorkflowPaths(paths[0], paths[1], _adjacent_method_template(paths[0], paths[1])), []


def _method_template_from_request(request: GenerateSIRequest):
    template = request.template_docx
    if template is None:
        return None
    try:
        selected = template.resolve()
    except OSError:
        selected = template
    for profile in list_journal_profiles(include_hidden=True):
        try:
            if selected == profile.template_path.resolve():
                return None
        except OSError:
            continue
    return template


def _adjacent_method_template(schema_docx, scope_docx):
    for source in (scope_docx, schema_docx):
        suffix = _workflow_suffix(source.stem)
        for filename in (f"SI_template{suffix}.docx", "SI_template.docx"):
            candidate = source.parent / filename
            if candidate.exists():
                return candidate
    directories = {source.parent for source in (scope_docx, schema_docx)}
    candidates = {path for directory in directories for path in directory.glob("SI_template*.docx")}
    if len(candidates) == 1:
        return candidates.pop()
    return None


def _workflow_suffix(stem: str) -> str:
    for prefix in ("Scope", "Reaction_schema"):
        if stem.casefold().startswith(prefix.casefold()):
            return stem[len(prefix) :]
    return ""
