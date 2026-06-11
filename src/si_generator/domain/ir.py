from __future__ import annotations

import re
from typing import Any

from .types import IRBlock


DEFAULT_IR_METHOD = "KBr"


def parse_ir_block(value: IRBlock | str | None, default_method: str = DEFAULT_IR_METHOD) -> IRBlock:
    if not value:
        return {}
    if isinstance(value, dict):
        block: IRBlock = {
            "method": str(value.get("method") or default_method),
            "peaks_cm1": _coerce_peaks(value.get("peaks_cm1", [])),
        }
        if value.get("formatted_text"):
            block["formatted_text"] = str(value["formatted_text"])
        else:
            block["formatted_text"] = format_ir_block(block)
        return block

    text = str(value).strip()
    method = _method_from_text(text) or default_method
    peaks = _peaks_from_text(text)
    block = {"method": method, "peaks_cm1": peaks}
    block["formatted_text"] = format_ir_block(block)
    return block


def format_ir_block(block: IRBlock) -> str:
    method = str(block.get("method") or DEFAULT_IR_METHOD)
    peaks = _coerce_peaks(block.get("peaks_cm1", []))
    if not peaks:
        return ""
    return f"IR ({method}, cm-1): {', '.join(str(peak) for peak in peaks)}."


def _method_from_text(text: str) -> str:
    match = re.search(r"\bIR\s*\(\s*([^,)]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.match(r"\s*([A-Za-z][A-Za-z0-9 /+-]*)\s*:", text)
    if match and not re.search(r"\d", match.group(1)):
        return match.group(1).strip()
    return ""


def _peaks_from_text(text: str) -> list[int]:
    data = text.split(":", 1)[1] if ":" in text else text
    return [int(match.group(0)) for match in re.finditer(r"(?<![-\d])\d{3,4}(?!\d)", data)]


def _coerce_peaks(value: Any) -> list[int]:
    if isinstance(value, str):
        return _peaks_from_text(value)
    if isinstance(value, list | tuple):
        peaks: list[int] = []
        for item in value:
            try:
                peaks.append(int(item))
            except (TypeError, ValueError):
                continue
        return peaks
    return []
