from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...chemdraw_ole import insert_chemdraw_placeholders
from ...docx_builder import build_document_from_model
from ...render.document_model import build_si_document_model
from ...style_config import config_get
from ...word_input import paste_word_structures


def build_document_model_node(state: GenerateSIState) -> dict:
    return {"document_model": build_si_document_model(ordered_compounds(state))}


def render_docx_node(state: GenerateSIState) -> dict:
    request = state["request"]
    document_model = state.get("document_model") or build_si_document_model(ordered_compounds(state))
    output_path = build_document_from_model(
        document_model,
        request.output_path,
        style_config=state.get("style_config"),
        template_path=request.template_docx,
    )
    artifacts = {**state.get("artifacts", {}), "support_docx": str(output_path)}
    return {"output_path": output_path, "artifacts": artifacts}


def postprocess_word_objects_node(state: GenerateSIState) -> dict:
    request = state["request"]
    output_path = state["output_path"]
    compounds = ordered_compounds(state)
    style_config = state.get("style_config", {})

    if request.input_kind == "word":
        paste_word_structures(
            request.input_path,
            output_path,
            compounds,
            main_top_offset_pt=float(config_get(style_config, "compound.structure.top_offset_pt", 12)),
            appendix_top_offset_pt=float(config_get(style_config, "appendix.structure.top_offset_pt", 0)),
        )
    elif request.insert_chemdraw:
        structure_map = {compound.number: compound.structure_path for compound in compounds if compound.structure_path}
        if structure_map:
            insert_chemdraw_placeholders(output_path, structure_map)

    return {"output_path": output_path}
