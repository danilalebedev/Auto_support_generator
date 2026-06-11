from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Compound:
    number: str
    name: str
    id: str = ""
    source_row: int = 0
    preparation: str = ""
    yield_text: str = ""
    color: str = ""
    state: str = ""
    melting_point: str = ""
    rf: str = ""
    formula: str = ""
    hrms_label: str = "HRMS (ESI-TOF) m/z"
    hrms_adduct: str = "[M+H]+"
    hrms_found: str = ""
    h1_nmr: str = ""
    h1_conditions: str = ""
    h1_spectrum_path: str = ""
    h1_image_path: str = ""
    c13_nmr: str = ""
    c13_conditions: str = ""
    c13_spectrum_path: str = ""
    c13_image_path: str = ""
    mnova_path: str = ""
    extra_nmr: str = ""
    ir: str = ""
    structure_path: str = ""
    has_word_structure: bool = False
    nmr_check_warning: str = ""

    @property
    def label(self) -> str:
        return f"({self.number})"
