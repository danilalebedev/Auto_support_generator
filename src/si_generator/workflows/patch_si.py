from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..domain.patching import parse_renumber_map
from ..graph.graphs import build_patch_si_graph
from ..graph.state import PatchSIRequest, PatchSIState, make_run_id


def make_initial_patch_state(request: PatchSIRequest) -> PatchSIState:
    return {"run_id": make_run_id(), "request": request, "artifacts": {}, "issues": []}


def run_patch_si(request: PatchSIRequest) -> PatchSIState:
    graph = build_patch_si_graph()
    return graph.invoke(make_initial_patch_state(request))


def patch_request_from_args(args: Namespace) -> PatchSIRequest:
    return PatchSIRequest(
        manifest_path=Path(args.patch_manifest),
        renumber=parse_renumber_map(args.renumber or ""),
        support_docx=Path(args.support_docx) if getattr(args, "support_docx", None) else None,
        output_docx=Path(args.patched_output) if getattr(args, "patched_output", None) else None,
        output_manifest=Path(args.patched_manifest_output) if getattr(args, "patched_manifest_output", None) else None,
        strict_artifacts=not bool(getattr(args, "no_strict_artifacts", False)),
    )
