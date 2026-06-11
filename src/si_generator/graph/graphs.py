from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes.ingest import read_input_table_node
from .nodes.normalize import normalize_compounds_node
from .nodes.packaging import write_manifest_node
from .nodes.render import postprocess_word_objects_node, render_docx_node
from .nodes.settings import load_settings_node
from .nodes.spectra import mnova_batch_node, prepare_spectra_zip_node, route_nmr_processing
from .nodes.validation import validate_input_node, validate_support_node
from .state import GenerateSIState


def build_generate_si_graph():
    builder = StateGraph(GenerateSIState)

    builder.add_node("load_settings", load_settings_node)
    builder.add_node("read_input_table", read_input_table_node)
    builder.add_node("normalize_compounds", normalize_compounds_node)
    builder.add_node("prepare_spectra_zip", prepare_spectra_zip_node)
    builder.add_node("validate_input", validate_input_node)
    builder.add_node("mnova_batch", mnova_batch_node)
    builder.add_node("validate_support", validate_support_node)
    builder.add_node("render_docx", render_docx_node)
    builder.add_node("postprocess_word_objects", postprocess_word_objects_node)
    builder.add_node("write_manifest", write_manifest_node)

    builder.add_edge(START, "load_settings")
    builder.add_edge("load_settings", "read_input_table")
    builder.add_edge("read_input_table", "normalize_compounds")
    builder.add_edge("normalize_compounds", "prepare_spectra_zip")
    builder.add_edge("prepare_spectra_zip", "validate_input")
    builder.add_conditional_edges(
        "validate_input",
        route_nmr_processing,
        {
            "run_mnova": "mnova_batch",
            "skip_mnova": "validate_support",
        },
    )
    builder.add_edge("mnova_batch", "validate_support")
    builder.add_edge("validate_support", "render_docx")
    builder.add_edge("render_docx", "postprocess_word_objects")
    builder.add_edge("postprocess_word_objects", "write_manifest")
    builder.add_edge("write_manifest", END)

    return builder.compile()
