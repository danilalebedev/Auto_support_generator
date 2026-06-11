from __future__ import annotations

import re

from .types import NMRSpectrumBlock, NMRSignal, PeakPickingPolicy


def parse_nmr_spectrum(nucleus: str, conditions: str, text: str) -> NMRSpectrumBlock:
    return {
        "nucleus": nucleus,
        "conditions": conditions,
        "signals": parse_nmr_signals(text),
        "formatted_text": text,
    }


def parse_nmr_signals(text: str) -> list[NMRSignal]:
    body = _strip_delta_prefix(text)
    return [signal for item in _split_top_level_commas(body) if (signal := _parse_signal_item(item))]


def apply_peak_picking_policy(spectrum: NMRSpectrumBlock, policy: PeakPickingPolicy) -> NMRSpectrumBlock:
    updated = dict(spectrum)
    updated["peak_picking"] = policy
    return updated


def _parse_signal_item(item: str) -> NMRSignal | None:
    item = item.strip().rstrip(".")
    if not item:
        return None

    signal: NMRSignal = {}
    range_match = re.match(r"^=?\s*(-?\d+(?:\.\d+)?)\s*(?:\u2013|-)\s*(-?\d+(?:\.\d+)?)\b", item)
    if range_match:
        signal["shift_range"] = (float(range_match.group(1)), float(range_match.group(2)))
    else:
        shift_match = re.match(r"^=?\s*(-?\d+(?:\.\d+)?)\b", item)
        if not shift_match:
            return None
        signal["shift"] = float(shift_match.group(1))

    envelopes = _top_level_parentheses(item)
    if envelopes:
        _parse_assignment_envelope(envelopes[-1], signal)
    return signal


def _parse_assignment_envelope(envelope: str, signal: NMRSignal) -> None:
    parts = [part.strip() for part in envelope.split(",") if part.strip()]
    if parts:
        signal["multiplicity"] = parts[0]

    j_values: list[float] = []
    for match in re.finditer(r"\bJ[A-Za-z0-9]*\s*=\s*([0-9.]+)", envelope):
        j_values.append(float(match.group(1)))
    if j_values:
        signal["j_values"] = j_values

    integral_match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*H\b", envelope, flags=re.IGNORECASE)
    if integral_match:
        signal["integral"] = float(integral_match.group(1))
        assignment_parts = parts[parts.index(integral_match.group(0)) + 1 :] if integral_match.group(0) in parts else []
        if assignment_parts:
            signal["assignment"] = ", ".join(assignment_parts)
    elif len(parts) > 1:
        signal["assignment"] = ", ".join(parts[1:])


def _strip_delta_prefix(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^.*?\u03b4\s*", "", text)
    return re.sub(r"^=\s*", "", text).strip()


def _split_top_level_commas(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index])
            start = index + 1
    result.append(text[start:])
    return [item.strip() for item in result if item.strip()]


def _top_level_parentheses(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = None
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                result.append(text[start:index])
                start = None
    return result
