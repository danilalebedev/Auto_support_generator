from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


TRACE_FILE_NAME = "word_ole_trace.jsonl"


def trace_word_ole_event(anchor_path: str | Path | None, event: str, **details: Any) -> None:
    """Append a best-effort trace event for Word/OLE operations.

    Word can show modal OLE dialogs before Python receives a COM exception. This
    trace makes the last attempted operation visible in the run logs.
    """
    try:
        trace_path = _trace_path(anchor_path)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
            "event": event,
            **{key: _json_value(value) for key, value in details.items()},
        }
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def _trace_path(anchor_path: str | Path | None) -> Path:
    explicit_dir = os.environ.get("AUTO_SUPPORT_TRACE_DIR", "").strip()
    if explicit_dir:
        return Path(explicit_dir) / TRACE_FILE_NAME
    if anchor_path:
        path = Path(anchor_path)
        directory = path if path.suffix == "" else path.parent
        return directory / "logs" / TRACE_FILE_NAME
    return Path.cwd() / "logs" / TRACE_FILE_NAME


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
