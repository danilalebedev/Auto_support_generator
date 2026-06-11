from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from ..graph.graphs import build_check_si_graph
from ..graph.state import CheckSIRequest, CheckSIState, make_run_id


def make_initial_check_state(request: CheckSIRequest) -> CheckSIState:
    return {"run_id": make_run_id(), "request": request, "artifacts": {}, "issues": []}


def run_check_si(request: CheckSIRequest) -> CheckSIState:
    graph = build_check_si_graph()
    return graph.invoke(make_initial_check_state(request))


def check_request_from_args(args: Namespace) -> CheckSIRequest:
    return CheckSIRequest(
        manifest_path=Path(args.check_manifest),
        support_docx=Path(args.support_docx) if getattr(args, "support_docx", None) else None,
        strict_artifacts=not bool(getattr(args, "no_strict_artifacts", False)),
    )
