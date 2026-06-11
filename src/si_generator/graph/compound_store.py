from __future__ import annotations

from collections.abc import Iterable

from .state import GenerateSIState
from ..domain.references import parse_reference_keys
from ..models import Compound


def make_compound_store(compounds: Iterable[Compound]) -> tuple[dict[str, Compound], list[str]]:
    store: dict[str, Compound] = {}
    order: list[str] = []
    used_ids: set[str] = set()

    for index, compound in enumerate(compounds, start=1):
        compound_id = _unique_compound_id(compound.id, index, used_ids)
        compound.id = compound_id
        compound.references = parse_reference_keys(compound.references)
        if not compound.source_row:
            compound.source_row = index
        store[compound_id] = compound
        order.append(compound_id)
        used_ids.add(compound_id)

    return store, order


def ordered_compounds(state: GenerateSIState) -> list[Compound]:
    compounds = state.get("compounds", {})
    return [compounds[compound_id] for compound_id in state.get("order", []) if compound_id in compounds]


def _unique_compound_id(raw_id: str, index: int, used_ids: set[str]) -> str:
    base_id = raw_id.strip() if raw_id else f"cmp_{index:03d}"
    compound_id = base_id
    suffix = 2
    while compound_id in used_ids:
        compound_id = f"{base_id}_{suffix}"
        suffix += 1
    return compound_id
