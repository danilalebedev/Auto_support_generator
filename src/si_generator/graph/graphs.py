from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes.add_compounds import (
    append_new_blocks_node,
    check_duplicate_compound_numbers_node,
    generate_new_support_node,
    load_add_manifest_node,
    prepare_add_output_layout_node,
    read_new_compounds_node,
    resolve_add_method_config_node,
    route_add_compounds_after_duplicate_check,
    route_add_compounds_after_generation,
    route_add_compounds_after_load,
    write_add_compounds_report_node,
    write_add_manifest_node,
)
from .nodes.elemental_analysis import calculate_elemental_analysis_node
from .nodes.check import check_manifest_node, load_manifest_node
from .nodes.ingest import read_input_table_node
from .nodes.hrms import calculate_hrms_node
from .nodes.loadings import calculate_loadings_node
from .nodes.nmr import apply_peak_picking_policy_node, parse_nmr_reports_node
from .nodes.normalize import normalize_compounds_node
from .nodes.packaging import write_manifest_node
from .nodes.patching import (
    apply_patch_node,
    check_patched_manifest_node,
    load_patch_manifest_node,
    prepare_patch_output_layout_node,
)
from .nodes.render import build_document_model_node, postprocess_word_objects_node, render_docx_node
from .nodes.settings import load_settings_node
from .nodes.spectra import mnova_batch_node, plan_nmr_processing_node, prepare_spectra_source_node, route_nmr_processing
from .nodes.validation import validate_input_node, validate_support_node
from .state import AddCompoundsState, CheckSIState, GenerateSIState, PatchSIState


FATAL_INPUT_MISMATCH_CODES = {
    "SPECTRA_SOURCE_INPUT_MISMATCH",
    "LOADINGS_FILES_INCOMPLETE",
    "LOADINGS_SCOPE_INPUT_MISMATCH",
}


def build_generate_si_graph():
    builder = StateGraph(GenerateSIState)

    builder.add_node("load_settings", load_settings_node)
    builder.add_node("read_input_table", read_input_table_node)
    builder.add_node("normalize_compounds", normalize_compounds_node)
    builder.add_node("prepare_spectra_source", prepare_spectra_source_node)
    builder.add_node("plan_nmr_processing", plan_nmr_processing_node)
    builder.add_node("validate_input", validate_input_node)
    builder.add_node("mnova_batch", mnova_batch_node)
    builder.add_node("parse_nmr_reports", parse_nmr_reports_node)
    builder.add_node("apply_peak_picking_policy", apply_peak_picking_policy_node)
    builder.add_node("calculate_hrms", calculate_hrms_node)
    builder.add_node("calculate_loadings", calculate_loadings_node)
    builder.add_node("calculate_elemental_analysis", calculate_elemental_analysis_node)
    builder.add_node("validate_support", validate_support_node)
    builder.add_node("build_document_model", build_document_model_node)
    builder.add_node("render_docx", render_docx_node)
    builder.add_node("postprocess_word_objects", postprocess_word_objects_node)
    builder.add_node("write_manifest", write_manifest_node)

    builder.add_edge(START, "load_settings")
    builder.add_edge("load_settings", "read_input_table")
    builder.add_edge("read_input_table", "normalize_compounds")
    builder.add_edge("normalize_compounds", "prepare_spectra_source")
    builder.add_conditional_edges(
        "prepare_spectra_source",
        route_generate_after_required_input_check,
        {
            "continue": "plan_nmr_processing",
            "fail": "write_manifest",
        },
    )
    builder.add_edge("plan_nmr_processing", "validate_input")
    builder.add_conditional_edges(
        "validate_input",
        route_nmr_processing,
        {
            "run_mnova": "mnova_batch",
            "skip_mnova": "parse_nmr_reports",
        },
    )
    builder.add_edge("mnova_batch", "parse_nmr_reports")
    builder.add_edge("parse_nmr_reports", "apply_peak_picking_policy")
    builder.add_edge("apply_peak_picking_policy", "calculate_hrms")
    builder.add_edge("calculate_hrms", "calculate_loadings")
    builder.add_conditional_edges(
        "calculate_loadings",
        route_generate_after_required_input_check,
        {
            "continue": "calculate_elemental_analysis",
            "fail": "write_manifest",
        },
    )
    builder.add_edge("calculate_elemental_analysis", "validate_support")
    builder.add_edge("validate_support", "build_document_model")
    builder.add_edge("build_document_model", "render_docx")
    builder.add_edge("render_docx", "postprocess_word_objects")
    builder.add_edge("postprocess_word_objects", "write_manifest")
    builder.add_edge("write_manifest", END)

    return builder.compile()


def route_generate_after_required_input_check(state: GenerateSIState) -> str:
    fatal_codes = {
        issue.get("code")
        for issue in state.get("issues", [])
        if issue.get("severity") == "error" and issue.get("code") in FATAL_INPUT_MISMATCH_CODES
    }
    if fatal_codes or state.get("status") == "fail":
        return "fail"
    return "continue"


def build_check_si_graph():
    builder = StateGraph(CheckSIState)

    builder.add_node("load_manifest", load_manifest_node)
    builder.add_node("check_manifest", check_manifest_node)

    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "check_manifest")
    builder.add_edge("check_manifest", END)

    return builder.compile()


def build_patch_si_graph():
    builder = StateGraph(PatchSIState)

    builder.add_node("prepare_output_layout", prepare_patch_output_layout_node)
    builder.add_node("load_manifest", load_patch_manifest_node)
    builder.add_node("apply_patch", apply_patch_node)
    builder.add_node("check_patched_manifest", check_patched_manifest_node)

    builder.add_edge(START, "prepare_output_layout")
    builder.add_edge("prepare_output_layout", "load_manifest")
    builder.add_edge("load_manifest", "apply_patch")
    builder.add_edge("apply_patch", "check_patched_manifest")
    builder.add_edge("check_patched_manifest", END)

    return builder.compile()


def build_add_compounds_graph():
    builder = StateGraph(AddCompoundsState)

    builder.add_node("load_manifest", load_add_manifest_node)
    builder.add_node("prepare_output_layout", prepare_add_output_layout_node)
    builder.add_node("read_new_compounds", read_new_compounds_node)
    builder.add_node("check_duplicate_numbers", check_duplicate_compound_numbers_node)
    builder.add_node("resolve_method_config", resolve_add_method_config_node)
    builder.add_node("generate_new_support", generate_new_support_node)
    builder.add_node("append_new_blocks", append_new_blocks_node)
    builder.add_node("write_manifest", write_add_manifest_node)
    builder.add_node("write_report", write_add_compounds_report_node)

    builder.add_edge(START, "prepare_output_layout")
    builder.add_edge("prepare_output_layout", "load_manifest")
    builder.add_conditional_edges(
        "load_manifest",
        route_add_compounds_after_load,
        {
            "continue": "read_new_compounds",
            "fail": "write_report",
        },
    )
    builder.add_edge("read_new_compounds", "check_duplicate_numbers")
    builder.add_conditional_edges(
        "check_duplicate_numbers",
        route_add_compounds_after_duplicate_check,
        {
            "continue": "resolve_method_config",
            "fail": "write_report",
        },
    )
    builder.add_conditional_edges(
        "resolve_method_config",
        route_add_compounds_after_generation,
        {
            "continue": "generate_new_support",
            "fail": "write_report",
        },
    )
    builder.add_conditional_edges(
        "generate_new_support",
        route_add_compounds_after_generation,
        {
            "continue": "append_new_blocks",
            "fail": "write_report",
        },
    )
    builder.add_edge("append_new_blocks", "write_manifest")
    builder.add_edge("write_manifest", "write_report")
    builder.add_edge("write_report", END)

    return builder.compile()
