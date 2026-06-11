from __future__ import annotations

from dataclasses import dataclass, field

from .domain.types import ElementalAnalysisBlock, HRMSBlock, Issue, NMRSpectrumBlock, ReactionBlock


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
    hrms_calculated: float = 0.0
    hrms_ion_formula: str = ""
    hrms: HRMSBlock = field(default_factory=dict)
    h1_nmr: str = ""
    h1_conditions: str = ""
    h1_spectrum_path: str = ""
    h1_image_path: str = ""
    c13_nmr: str = ""
    c13_conditions: str = ""
    c13_spectrum_path: str = ""
    c13_image_path: str = ""
    nmr_spectra: dict[str, NMRSpectrumBlock] = field(default_factory=dict)
    mnova_path: str = ""
    extra_nmr: str = ""
    ir: str = ""
    elemental_analysis: ElementalAnalysisBlock = field(default_factory=dict)
    reaction: ReactionBlock = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    structure_path: str = ""
    has_word_structure: bool = False
    nmr_check_warning: str = ""
    validation_issues: list[Issue] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"({self.number})"
