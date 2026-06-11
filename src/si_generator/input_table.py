from __future__ import annotations

import csv
from pathlib import Path

from .domain.references import parse_reference_keys
from .domain.reactions import reaction_from_fields
from .domain.compound import Compound


FIELD_ALIASES = {
    "yield": "yield_text",
    "yield_text": "yield_text",
    "refs": "references",
    "reference_keys": "references",
    "referencekeys": "references",
    "anal": "elemental_analysis",
    "analysis": "elemental_analysis",
    "ea": "elemental_analysis",
    "elementalanalysis": "elemental_analysis",
}


def read_compounds(path: str | Path) -> list[Compound]:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("This prototype reads CSV files. Use Excel's 'Save as CSV' for now.")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV input has no header row.")
        compounds: list[Compound] = []
        for row_number, raw_row in enumerate(reader, start=2):
            row = {FIELD_ALIASES.get(key, key): (value or "").strip() for key, value in raw_row.items() if key}
            try:
                kwargs = {key: value for key, value in row.items() if key in Compound.__dataclass_fields__}
                kwargs.setdefault("number", "")
                kwargs.setdefault("name", "")
                kwargs["references"] = parse_reference_keys(row.get("references", ""))
                if "elemental_analysis" in row:
                    kwargs["elemental_analysis"] = {"found": row.get("elemental_analysis", "")}
                reaction = reaction_from_fields(row)
                if reaction:
                    kwargs["reaction"] = reaction
                compound = Compound(**kwargs)
                compound.source_row = row_number
                compounds.append(compound)
            except TypeError as exc:
                raise ValueError(f"Invalid columns near CSV row {row_number}: {exc}") from exc

    return compounds
