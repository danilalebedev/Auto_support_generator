from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

import gemmi


MISSING = {"", ".", "?"}


def clean_cif_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if value in MISSING:
        return None
    if value.startswith(";"):
        return gemmi.cif.as_string(value).strip() or None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip() or None


def cif_number(value: str | None) -> float | None:
    value = clean_cif_value(value)
    if value is None:
        return None
    value = re.sub(r"\([^()]*(?:\)|$)", "", value).strip()
    try:
        return float(value)
    except ValueError:
        match = re.match(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", value)
        return float(match.group(0)) if match else None


@dataclass(slots=True)
class CifRecord:
    source: Path
    block_name: str
    scalars: dict[str, str]
    loops: list[list[dict[str, str]]] = field(default_factory=list)
    label: str | None = None
    ccdc: str | None = None
    parser_notes: list[str] = field(default_factory=list)

    def get(self, *tags: str) -> str | None:
        for tag in tags:
            value = clean_cif_value(self.scalars.get(tag.lower()))
            if value is not None:
                return value
        return None

    def rows_with(self, *tags: str) -> list[dict[str, str]]:
        wanted = {tag.lower() for tag in tags}
        for rows in self.loops:
            if rows and wanted.intersection(rows[0]):
                return rows
        return []

    @property
    def display_label(self) -> str:
        return self.label or self.block_name or self.source.stem

    @property
    def is_structure(self) -> bool:
        return all(self.get(f"_cell_length_{axis}", f"_cell.length_{axis}") is not None for axis in "abc")


def _quote(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    return value


def _repair_single_author_loops(text: str) -> tuple[str, bool]:
    """Repair a legacy one-column author loop whose values contain unquoted spaces."""
    lines = text.replace("\u00a0", " ").splitlines()
    repaired = False
    index = 0
    while index < len(lines):
        if lines[index].strip().lower() != "loop_":
            index += 1
            continue
        tag_index = index + 1
        tags: list[str] = []
        while tag_index < len(lines) and lines[tag_index].strip().startswith("_"):
            tags.append(lines[tag_index].strip().split()[0].lower())
            tag_index += 1
        if tags != ["_publ_author_name"]:
            index = tag_index
            continue
        value_index = tag_index
        while value_index < len(lines):
            stripped = lines[value_index].strip()
            lowered = stripped.lower()
            if lowered == "loop_" or lowered.startswith(("data_", "save_", "global_", "stop_", "_")):
                break
            if stripped and not stripped.startswith("#") and stripped[0] not in {"'", '"', ";"} and any(char.isspace() for char in stripped):
                leading = lines[value_index][: len(lines[value_index]) - len(lines[value_index].lstrip())]
                lines[value_index] = leading + _quote(stripped)
                repaired = True
            value_index += 1
        index = value_index
    suffix = "\n" if text.endswith(("\n", "\r")) else ""
    return "\n".join(lines) + suffix, repaired


def read_cif(path: str | Path) -> list[CifRecord]:
    source = Path(path).resolve()
    parser_notes: list[str] = []
    try:
        document = gemmi.cif.read_file(str(source))
    except ValueError as original_error:
        raw = source.read_text(encoding="utf-8-sig")
        repaired_text, repaired = _repair_single_author_loops(raw)
        if not repaired:
            raise original_error
        document = gemmi.cif.read_string(repaired_text)
        parser_notes.append("The input required an in-memory repair of unquoted _publ_author_name values; the source file was not modified.")
    records: list[CifRecord] = []
    for block in document:
        scalars: dict[str, str] = {}
        loops: list[list[dict[str, str]]] = []
        for item in block:
            if item.pair is not None:
                tag, value = item.pair
                scalars[tag.lower()] = value
            elif item.loop is not None:
                tags = [tag.lower() for tag in item.loop.tags]
                width = len(tags)
                values = list(item.loop.values)
                rows = [
                    dict(zip(tags, values[offset : offset + width], strict=True))
                    for offset in range(0, len(values), width)
                ]
                loops.append(rows)
        records.append(CifRecord(source, block.name, scalars, loops, parser_notes=list(parser_notes)))
    return records


def read_all(paths: list[str | Path]) -> list[CifRecord]:
    records: list[CifRecord] = []
    for path in paths:
        records.extend(record for record in read_cif(path) if record.is_structure)
    return records
