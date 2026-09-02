from __future__ import annotations

from dataclasses import replace

from ..state import GenerateSIState
from ...unified_word_input import default_unified_staging_dir, materialize_unified_input


def prepare_unified_input_node(state: GenerateSIState) -> dict:
    request = state["request"]
    if not request.unified_input_docx:
        return {}

    bundle = materialize_unified_input(
        request.unified_input_docx,
        default_unified_staging_dir(state.get("run_id", "")),
    )
    issues = list(state.get("issues", []))
    has_schema = bundle.reaction_schema is not None
    has_scope = bundle.scope is not None
    if has_schema != has_scope:
        missing = "Scope" if has_schema else "Reaction schema"
        issues.append(
            {
                "code": "UNIFIED_INPUT_LOADINGS_INCOMPLETE",
                "severity": "warning",
                "message": (
                    f"The all-in-one input contains only one reagent-loadings section; {missing} is missing. "
                    "Reagent loadings were skipped."
                ),
                "path": str(bundle.source),
            }
        )

    resolved_request = replace(
        request,
        resolved_compound_table_docx=bundle.compound_table,
        template_docx=bundle.si_template or request.template_docx,
        loadings_schema_docx=bundle.reaction_schema if bundle.has_complete_loadings else None,
        loadings_scope_docx=bundle.scope if bundle.has_complete_loadings else None,
        generate_loadings=bundle.has_complete_loadings,
    )
    return {
        "request": resolved_request,
        "issues": issues,
        "unified_input_components": {
            "source": str(bundle.source),
            "compound_table": str(bundle.compound_table),
            "reaction_schema": str(bundle.reaction_schema) if bundle.reaction_schema else "",
            "scope": str(bundle.scope) if bundle.scope else "",
            "si_template": str(bundle.si_template) if bundle.si_template else "",
        },
    }
