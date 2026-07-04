from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ir import parse_ir_block
from .massspec import hrms_found_text
from .types import Compound as CompoundSnapshot
from .types import ElementalAnalysisBlock, HRMSBlock, IRBlock, Issue, NMRSpectrumBlock, ReactionBlock


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
    h1_mnova_path: str = ""
    c13_nmr: str = ""
    c13_conditions: str = ""
    c13_spectrum_path: str = ""
    c13_image_path: str = ""
    c13_mnova_path: str = ""
    nmr_spectra: dict[str, NMRSpectrumBlock] = field(default_factory=dict)
    mnova_path: str = ""
    extra_nmr: str = ""
    ir: str | IRBlock = ""
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

    def to_domain_dict(self) -> CompoundSnapshot:
        return compound_to_domain_dict(self)


def compound_to_domain_dict(compound: Compound) -> CompoundSnapshot:
    data: CompoundSnapshot = {
        "id": compound.id,
        "number": compound.number,
        "name": compound.name,
    }
    _put(data, "formula", compound.formula)
    _put(data, "physical", _physical_block(compound))
    _put(data, "structure", _structure_block(compound))
    _put(data, "spectra", _spectra_block(compound))
    _put(data, "nmr", _nmr_block(compound))
    _put(data, "hrms", _hrms_block(compound))
    _put(data, "ir", _ir_block(compound.ir))
    _put(data, "elemental_analysis", compound.elemental_analysis)
    _put(data, "reaction", compound.reaction)
    _put(data, "references", list(compound.references))
    _put(data, "issues", list(compound.validation_issues))
    return data


def _physical_block(compound: Compound) -> dict[str, str]:
    return _compact(
        {
            "color": compound.color,
            "state": compound.state,
            "melting_point": compound.melting_point,
            "rf": compound.rf,
            "yield_text": compound.yield_text,
        }
    )


def _structure_block(compound: Compound) -> dict[str, Any]:
    return _compact(
        {
            "path": compound.structure_path,
            "has_word_structure": compound.has_word_structure,
            "formula": compound.formula,
        }
    )


def _spectra_block(compound: Compound) -> dict[str, dict[str, str]]:
    spectra: dict[str, dict[str, str]] = {}
    h1 = _compact(
        {
            "source_path": compound.h1_spectrum_path,
            "image_path": compound.h1_image_path,
            "mnova_path": compound.h1_mnova_path or (compound.mnova_path if compound.h1_spectrum_path or compound.h1_image_path else ""),
        }
    )
    if h1:
        spectra["1H"] = h1
    c13 = _compact(
        {
            "source_path": compound.c13_spectrum_path,
            "image_path": compound.c13_image_path,
            "mnova_path": compound.c13_mnova_path or (compound.mnova_path if compound.c13_spectrum_path or compound.c13_image_path else ""),
        }
    )
    if c13:
        spectra["13C"] = c13
    return spectra


def _nmr_block(compound: Compound) -> dict[str, Any]:
    spectra: dict[str, NMRSpectrumBlock] = dict(compound.nmr_spectra)
    if compound.h1_nmr and "1H" not in spectra:
        spectra["1H"] = _compact(
            {
                "nucleus": "1H",
                "conditions": compound.h1_conditions,
                "formatted_text": compound.h1_nmr,
            }
        )
    if compound.c13_nmr and "13C" not in spectra:
        spectra["13C"] = _compact(
            {
                "nucleus": "13C",
                "conditions": compound.c13_conditions,
                "formatted_text": compound.c13_nmr,
            }
        )
    return _compact(
        {
            "spectra": spectra,
            "extra_text": compound.extra_nmr,
            "warnings": [compound.nmr_check_warning] if compound.nmr_check_warning else [],
        }
    )


def _hrms_block(compound: Compound) -> HRMSBlock:
    if not (compound.hrms or compound.hrms_found or compound.hrms_calculated or compound.hrms_ion_formula):
        return {}
    block: HRMSBlock = dict(compound.hrms)
    if compound.hrms_label and not block.get("label"):
        block["label"] = compound.hrms_label
    if compound.hrms_adduct and not block.get("adduct"):
        block["adduct"] = compound.hrms_adduct
    found_text = hrms_found_text(block, compound.hrms_found)
    if found_text and not block.get("found_text"):
        block["found_text"] = found_text
    if compound.hrms_calculated and not block.get("calculated_mz"):
        block["calculated_mz"] = compound.hrms_calculated
    if compound.hrms_ion_formula and not block.get("ion_formula"):
        block["ion_formula"] = compound.hrms_ion_formula
    return _compact(block)


def _ir_block(value: str | IRBlock) -> IRBlock:
    if isinstance(value, dict):
        return _compact(dict(value))
    text = value.strip()
    if not text:
        return {}
    block = parse_ir_block(text)
    if block:
        return block
    return {"formatted_text": text}


def _put(target: dict[str, Any], key: str, value: Any) -> None:
    if value:
        target[key] = value


def _compact(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value not in ("", None, {}, [])}
