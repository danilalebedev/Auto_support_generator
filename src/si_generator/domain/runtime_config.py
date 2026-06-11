from __future__ import annotations

from .types import RuntimeConfig


def build_runtime_config(
    *,
    gui: bool = False,
    debug: bool = False,
    dry_run: bool = False,
) -> RuntimeConfig:
    return {
        "gui": gui,
        "debug": debug,
        "dry_run": dry_run,
    }
