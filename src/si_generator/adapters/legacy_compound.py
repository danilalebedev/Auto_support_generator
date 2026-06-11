from __future__ import annotations

from ..domain.types import Compound as DomainCompound
from ..models import Compound as LegacyCompound

def make_compound_id(index: int) -> str:
    return f"cmp_{index:03d}"


def legacy_dataclass_to_compound_dict(old: LegacyCompound, compound_id: str | None = None) -> DomainCompound:
    compound_id = compound_id or make_compound_id(1)
    spectra = {}
    if old.h1_spectrum_path or old.h1_image_path or old.mnova_path:
        spectra["1H"] = {
            "source_path": old.h1_spectrum_path,
            "image_path": old.h1_image_path,
            "mnova_path": old.mnova_path,
            "embed_mode": "png",
            "render_spec": {"nucleus": "1H", "target_signal_height_fraction": 0.80, "peak_picking": "normal"},
        }
    if old.c13_spectrum_path or old.c13_image_path or old.mnova_path:
        spectra["13C"] = {
            "source_path": old.c13_spectrum_path,
            "image_path": old.c13_image_path,
            "mnova_path": old.mnova_path,
            "embed_mode": "png",
            "render_spec": {"nucleus": "13C", "target_signal_height_fraction": 0.80, "peak_picking": "normal"},
        }

    nmr_spectra = {}
    if old.h1_nmr or old.h1_conditions:
        nmr_spectra["1H"] = {"nucleus": "1H", "conditions": old.h1_conditions, "formatted_text": old.h1_nmr}
    if old.c13_nmr or old.c13_conditions:
        nmr_spectra["13C"] = {"nucleus": "13C", "conditions": old.c13_conditions, "formatted_text": old.c13_nmr}

    hrms = {
        "label": old.hrms_label,
        "adduct": old.hrms_adduct,
        "found_text": old.hrms_found,
        "isotope_policy": "monoisotopic",
    }
    try:
        hrms["found_mz"] = float(old.hrms_found)
    except (TypeError, ValueError):
        pass

    issues = []
    if old.nmr_check_warning:
        issues.append({"code": "LEGACY_SUPPORT_CHECK", "severity": "warning", "message": old.nmr_check_warning, "compound_id": compound_id})

    return {
        "id": compound_id,
        "number": old.number,
        "name": old.name,
        "formula": old.formula,
        "physical": {
            "color": old.color,
            "state": old.state,
            "melting_point": old.melting_point,
            "rf": old.rf,
            "yield_text": old.yield_text,
        },
        "structure": {
            "path": old.structure_path,
            "has_word_structure": old.has_word_structure,
        },
        "spectra": spectra,
        "nmr": {"spectra": nmr_spectra, "extra_text": old.extra_nmr},
        "hrms": hrms,
        "ir": {"formatted_text": old.ir},
        "reaction": {"preparation": old.preparation},
        "issues": issues,
    }


def compound_dict_to_legacy_dataclass(new: DomainCompound) -> LegacyCompound:
    physical = new.get("physical", {})
    structure = new.get("structure", {})
    spectra = new.get("spectra", {})
    nmr = new.get("nmr", {})
    nmr_spectra = nmr.get("spectra", {})
    h1_asset = spectra.get("1H", {})
    c13_asset = spectra.get("13C", {})
    h1_block = nmr_spectra.get("1H", {})
    c13_block = nmr_spectra.get("13C", {})
    hrms = new.get("hrms", {})
    ir = new.get("ir", {})
    reaction = new.get("reaction", {})
    issues = new.get("issues", [])

    return LegacyCompound(
        number=new.get("number", ""),
        name=new.get("name", ""),
        preparation=str(reaction.get("preparation", "")),
        yield_text=str(physical.get("yield_text", "")),
        color=str(physical.get("color", "")),
        state=str(physical.get("state", "")),
        melting_point=str(physical.get("melting_point", "")),
        rf=str(physical.get("rf", "")),
        formula=new.get("formula", ""),
        hrms_label=str(hrms.get("label", "HRMS (ESI-TOF) m/z")),
        hrms_adduct=str(hrms.get("adduct", "[M+H]+")),
        hrms_found=str(hrms.get("found_text", "")),
        h1_nmr=str(h1_block.get("formatted_text", "")),
        h1_conditions=str(h1_block.get("conditions", "")),
        h1_spectrum_path=str(h1_asset.get("source_path", "")),
        h1_image_path=str(h1_asset.get("image_path", "")),
        c13_nmr=str(c13_block.get("formatted_text", "")),
        c13_conditions=str(c13_block.get("conditions", "")),
        c13_spectrum_path=str(c13_asset.get("source_path", "")),
        c13_image_path=str(c13_asset.get("image_path", "")),
        mnova_path=str(h1_asset.get("mnova_path") or c13_asset.get("mnova_path") or ""),
        extra_nmr=str(nmr.get("extra_text", "")),
        ir=str(ir.get("formatted_text", "")),
        structure_path=str(structure.get("path", "")),
        has_word_structure=bool(structure.get("has_word_structure", False)),
        nmr_check_warning="; ".join(issue.get("message", "") for issue in issues if issue.get("message")),
    )


def legacy_compounds_to_domain(compounds: list[LegacyCompound]) -> tuple[dict[str, DomainCompound], list[str]]:
    converted: dict[str, DomainCompound] = {}
    order: list[str] = []
    for index, compound in enumerate(compounds, start=1):
        compound_id = make_compound_id(index)
        converted[compound_id] = legacy_dataclass_to_compound_dict(compound, compound_id=compound_id)
        order.append(compound_id)
    return converted, order


def domain_compounds_to_legacy(compounds: dict[str, DomainCompound], order: list[str]) -> list[LegacyCompound]:
    return [compound_dict_to_legacy_dataclass(compounds[compound_id]) for compound_id in order if compound_id in compounds]
