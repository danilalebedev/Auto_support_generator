from __future__ import annotations

import csv
from pathlib import Path

from .models import Compound


FIELD_ALIASES = {
    "yield": "yield_text",
    "yield_text": "yield_text",
}


def read_compounds(path: str | Path) -> list[Compound]:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("This prototype reads CSV files. Use Excel's 'Save as CSV' for now.")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        compounds: list[Compound] = []
        for row_number, raw_row in enumerate(reader, start=2):
            row = {FIELD_ALIASES.get(key, key): (value or "").strip() for key, value in raw_row.items() if key}
            try:
                compounds.append(Compound(**{key: row.get(key, "") for key in Compound.__dataclass_fields__}))
            except TypeError as exc:
                raise ValueError(f"Invalid columns near CSV row {row_number}: {exc}") from exc

    return compounds

