from __future__ import annotations

from ..state import GenerateSIState
from ...input_table import read_compounds
from ...word_input import read_word_compounds


def read_input_table_node(state: GenerateSIState) -> dict:
    request = state["request"]
    if request.input_kind == "word":
        compounds = read_word_compounds(request.input_path, extract_structure_metadata=request.extract_structure_metadata)
    else:
        compounds = read_compounds(request.input_path)

    if request.only:
        wanted = set(request.only)
        compounds = [compound for compound in compounds if compound.number in wanted]

    return {"input_compounds": compounds}

