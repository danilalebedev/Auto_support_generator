from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..domain.patching import parse_remove_list, parse_renumber_map, parse_reorder_list, parse_swap_pairs
from ..domain.requests import PatchSIRequest
from ..graph.graphs import build_patch_si_graph
from ..graph.state import PatchSIState, make_run_id


def make_initial_patch_state(request: PatchSIRequest) -> PatchSIState:
    return {"run_id": make_run_id(), "request": request, "artifacts": {}, "issues": []}


def run_patch_si(request: PatchSIRequest) -> PatchSIState:
    graph = build_patch_si_graph()
    return graph.invoke(make_initial_patch_state(request))


def patch_request_from_args(args: Namespace) -> PatchSIRequest:
    return PatchSIRequest(
        manifest_path=Path(args.patch_manifest),
        renumber=parse_renumber_map(args.renumber) if getattr(args, "renumber", None) else {},
        remove=parse_remove_list(getattr(args, "remove", "") or ""),
        reorder=parse_reorder_list(getattr(args, "reorder", "") or ""),
        swap=parse_swap_pairs(getattr(args, "swap", "") or "") if getattr(args, "swap", None) else (),
        support_docx=Path(args.support_docx) if getattr(args, "support_docx", None) else None,
        output_folder=Path(args.patch_output_folder) if getattr(args, "patch_output_folder", None) else None,
        strict_artifacts=not bool(getattr(args, "no_strict_artifacts", False)),
    )
