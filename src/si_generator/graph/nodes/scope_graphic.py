from pathlib import Path

from ...domain.loadings_workflow import discover_loadings_workflow
from ..compound_store import ordered_compounds


def generate_scope_graphic_node(state):
    request = state["request"]
    if not request.show_scope:
        return {}
    artifacts = dict(state.get("artifacts", {}))
    try:
        workflow = discover_loadings_workflow(request.input_base_dir)
        scope = request.loadings_scope_docx or (workflow.scope_docx if workflow else None)
        schema = request.loadings_schema_docx or (workflow.schema_docx if workflow else None)
        if not scope or not schema:
            raise ValueError("Show scope requires Scope.docx and Reaction_schema.docx, "
                             "or both sections in the all-in-one input.")
        from ...scope_graphic.generator import generate
        model = generate(ordered_compounds(state), scope, schema,
                         Path(artifacts["output_root"]) / "scope",
                         conditions=request.scope_conditions, title=request.scope_title)
        artifacts["scope_graphic"] = str(model)
        return {"artifacts": artifacts}
    except Exception as exc:
        return {"status": "fail", "issues": [*state.get("issues", []), {
            "code": "SCOPE_GRAPHIC_FAILED", "severity": "error", "message": str(exc)}]}
