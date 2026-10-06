from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, TypeVar


METHOD_MARKER_RE = re.compile(r"^\[AUTO SI:\s*METHOD\s+(.+?)\]$", re.IGNORECASE)
REACTION_MARKER_RE = re.compile(r"^\[AUTO SI:\s*REACTION\s+(.+?)\]$", re.IGNORECASE)
COMPOUND_TEMPLATE_MARKER = "[AUTO SI: COMPOUND TEMPLATE]"


class MethodSelectorError(ValueError):
    pass


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Selector:
    source: str
    numbers: frozenset[str]

    def matches(self, compound_number: str) -> bool:
        return _normalize_number(compound_number) in self.numbers


def parse_selector(source: str) -> Selector:
    text = source.strip()
    if not text:
        raise MethodSelectorError("Compound selector cannot be empty.")

    numbers: set[str] = set()
    for raw_token in re.split(r"[,;]", text.replace("\u2013", "-").replace("\u2014", "-")):
        token = raw_token.strip()
        if not token:
            continue
        numbers.update(_expand_token(token))
    if not numbers:
        raise MethodSelectorError(f"Compound selector contains no numbers: {source}")
    return Selector(source=text, numbers=frozenset(numbers))


def method_selector(text: str) -> Selector | None:
    match = METHOD_MARKER_RE.fullmatch(text.strip())
    return parse_selector(match.group(1)) if match else None


def reaction_selector(text: str) -> Selector | None:
    match = REACTION_MARKER_RE.fullmatch(text.strip())
    return parse_selector(match.group(1)) if match else None


def is_compound_template_marker(text: str) -> bool:
    return text.strip().casefold() == COMPOUND_TEMPLATE_MARKER.casefold()


def select_for_compound(items: Iterable[tuple[Selector | None, T]], compound_number: str) -> T | None:
    selected: T | None = None
    fallback: T | None = None
    for selector, value in items:
        if selector is None:
            fallback = value
            continue
        if not selector.matches(compound_number):
            continue
        if selected is not None:
            raise MethodSelectorError(
                f"Compound {compound_number} is assigned to more than one method selector."
            )
        selected = value
    return selected if selected is not None else fallback


def _expand_token(token: str) -> set[str]:
    if "-" not in token:
        return {_normalize_number(token)}

    start_text, end_text = (part.strip() for part in token.split("-", 1))
    start = _number_parts(start_text)
    if re.fullmatch(r"[A-Za-z]", end_text) and start[1]:
        end = (start[0], end_text.casefold())
    else:
        end = _number_parts(end_text)

    if start[0] == end[0] and len(start[1]) == len(end[1]) == 1:
        first, last = ord(start[1]), ord(end[1])
        if first > last:
            raise MethodSelectorError(f"Descending compound range is not supported: {token}")
        return {f"{start[0]}{chr(code)}" for code in range(first, last + 1)}
    if not start[1] and not end[1]:
        first, last = int(start[0]), int(end[0])
        if first > last:
            raise MethodSelectorError(f"Descending compound range is not supported: {token}")
        return {str(value) for value in range(first, last + 1)}
    raise MethodSelectorError(f"Unsupported compound range: {token}")


def _number_parts(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d+)([A-Za-z]*)", value.strip())
    if not match:
        raise MethodSelectorError(f"Invalid compound number: {value}")
    return match.group(1), match.group(2).casefold()


def _normalize_number(value: str) -> str:
    prefix, suffix = _number_parts(value)
    return f"{prefix}{suffix}"
