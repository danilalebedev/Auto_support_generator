from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..domain.requests import GenerateSIRequest
from ..domain.types import SpectrumEmbedMode
from ..graph.graphs import build_generate_si_graph
from ..graph.state import GenerateSIState, make_run_id


def make_initial_generate_state(request: GenerateSIRequest) -> GenerateSIState:
    return {"run_id": make_run_id(), "request": request, "artifacts": {}, "issues": []}


def run_generate_si(request: GenerateSIRequest) -> GenerateSIState:
    graph = build_generate_si_graph()
    return graph.invoke(make_initial_generate_state(request))


def output_path_from_state(state: GenerateSIState) -> Path:
    output_path = state.get("output_path")
    if output_path is None:
        return state["request"].output_path
    return Path(output_path)


def request_from_args(args: Namespace) -> GenerateSIRequest:
    input_path = Path(args.word_input or args.input)
    return GenerateSIRequest(
        input_path=input_path,
        input_kind="word" if args.word_input else "csv",
        output_path=Path(args.output),
        template_docx=Path(args.template_docx) if args.template_docx else None,
        references_path=Path(args.references) if args.references else None,
        spectra_zip=Path(args.spectra_zip) if args.spectra_zip else None,
        loadings_schema_docx=Path(args.loadings_schema_docx) if getattr(args, "loadings_schema_docx", None) else None,
        loadings_scope_docx=Path(args.loadings_scope_docx) if getattr(args, "loadings_scope_docx", None) else None,
        mnova_exe=Path(args.mnova_exe) if args.mnova_exe else None,
        no_extract_nmr=bool(args.no_extract_nmr),
        insert_spectra_as=_spectrum_embed_mode(getattr(args, "insert_spectra_as", "png")),
        peak_threshold_fraction=_peak_threshold_arg(getattr(args, "peak_threshold", None)),
        peak_threshold_fraction_1h=_peak_threshold_arg(getattr(args, "peak_threshold_1h", None)),
        peak_threshold_fraction_13c=_peak_threshold_arg(getattr(args, "peak_threshold_13c", None)),
        generate_loadings=bool(getattr(args, "generate_loadings", False)),
        extract_structure_metadata=bool(args.extract_structure_metadata),
        only=tuple(item.strip() for item in (args.only or "").split(",") if item.strip()),
        insert_chemdraw=bool(args.insert_chemdraw),
        no_check_support=bool(args.no_check_support),
    )


def _spectrum_embed_mode(value: str | None) -> SpectrumEmbedMode:
    if value in {"png", "mnova", "both", "none"}:
        return value
    return "png"


def _peak_threshold_arg(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if value > 1 else value
