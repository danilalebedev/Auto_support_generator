from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..domain.requests import AddCompoundsRequest
from ..domain.types import SpectrumEmbedMode
from ..graph.graphs import build_add_compounds_graph
from ..graph.state import AddCompoundsState, make_run_id


def make_initial_add_compounds_state(request: AddCompoundsRequest) -> AddCompoundsState:
    return {"run_id": make_run_id(), "request": request, "artifacts": {}, "issues": []}


def run_add_compounds(request: AddCompoundsRequest) -> AddCompoundsState:
    graph = build_add_compounds_graph()
    return graph.invoke(make_initial_add_compounds_state(request))


def add_compounds_request_from_args(args: Namespace) -> AddCompoundsRequest:
    input_path = Path(getattr(args, "add_word_input", None) or getattr(args, "add_input", None))
    return AddCompoundsRequest(
        manifest_path=Path(args.add_compounds_manifest),
        support_docx=Path(args.support_docx) if getattr(args, "support_docx", None) else None,
        input_path=input_path,
        input_kind="word" if getattr(args, "add_word_input", None) else "csv",
        output_docx=Path(getattr(args, "add_output", None) or getattr(args, "output", None)),
        template_docx=Path(args.template_docx) if getattr(args, "template_docx", None) else None,
        references_path=Path(args.references) if getattr(args, "references", None) else None,
        spectra_source=Path(args.spectra_source) if getattr(args, "spectra_source", None) else None,
        spectra_zip=Path(args.spectra_zip) if getattr(args, "spectra_zip", None) else None,
        mnova_exe=Path(args.mnova_exe) if getattr(args, "mnova_exe", None) else None,
        mnova_graphics_profile=Path(args.mnova_graphics_profile) if getattr(args, "mnova_graphics_profile", None) else None,
        no_extract_nmr=bool(getattr(args, "no_extract_nmr", False)),
        insert_spectra_as=_spectrum_embed_mode(getattr(args, "insert_spectra_as", "png")),
        target_signal_height_fraction=_fraction_arg(
            getattr(args, "target_signal_height", None),
            default=0.80,
        ),
        peak_threshold_fraction=_peak_threshold_arg(getattr(args, "peak_threshold", None)),
        peak_threshold_fraction_1h=_peak_threshold_arg(getattr(args, "peak_threshold_1h", None)),
        peak_threshold_fraction_13c=_peak_threshold_arg(getattr(args, "peak_threshold_13c", None)),
        baseline_mode=getattr(args, "baseline_mode", "auto"),
        baseline_apply_1h=bool(getattr(args, "baseline_apply_1h", False)),
        baseline_apply_13c=not bool(getattr(args, "no_baseline_13c", False)),
        baseline_poly_order=int(getattr(args, "baseline_poly_order", 3) or 3),
        whittaker_lambda=float(getattr(args, "whittaker_lambda", 100000.0) or 100000.0),
        whittaker_asymmetry=float(getattr(args, "whittaker_asymmetry", 0.001) or 0.001),
        generate_loadings=bool(getattr(args, "generate_loadings", False)),
        calculate_elemental_analysis=bool(getattr(args, "calculate_elemental_analysis", False)),
        no_check_support=bool(getattr(args, "no_check_support", False)),
        strict_artifacts=not bool(getattr(args, "no_strict_artifacts", False)),
    )


def _spectrum_embed_mode(value: str | None) -> SpectrumEmbedMode:
    if value in {"png", "mnova", "none"}:
        return value
    return "png"


def _peak_threshold_arg(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if value > 1 else value


def _fraction_arg(value: float | None, *, default: float) -> float:
    if value is None:
        return default
    return value / 100 if value > 1 else value
