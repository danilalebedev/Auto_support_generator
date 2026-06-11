from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..graph.graphs import build_generate_si_graph
from ..graph.state import GenerateSIRequest, GenerateSIState, make_run_id


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
        style_config_path=Path(args.style_config) if args.style_config else None,
        journal_profile=args.journal_profile or None,
        references_path=Path(args.references) if args.references else None,
        spectra_zip=Path(args.spectra_zip) if args.spectra_zip else None,
        mnova_exe=Path(args.mnova_exe) if args.mnova_exe else None,
        no_extract_nmr=bool(args.no_extract_nmr),
        extract_structure_metadata=bool(args.extract_structure_metadata),
        only=tuple(item.strip() for item in (args.only or "").split(",") if item.strip()),
        insert_chemdraw=bool(args.insert_chemdraw),
        no_check_support=bool(args.no_check_support),
    )
