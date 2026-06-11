from __future__ import annotations

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.nmr import apply_peak_picking_policy, parse_nmr_spectrum


def parse_nmr_reports_node(state: GenerateSIState) -> dict:
    for compound in ordered_compounds(state):
        spectra = {}
        if compound.h1_nmr:
            spectra["1H"] = parse_nmr_spectrum("1H", compound.h1_conditions, compound.h1_nmr)
        if compound.c13_nmr:
            spectra["13C"] = parse_nmr_spectrum("13C", compound.c13_conditions, compound.c13_nmr)
        compound.nmr_spectra = spectra
    return {"compounds": state.get("compounds", {})}


def apply_peak_picking_policy_node(state: GenerateSIState) -> dict:
    spectra_plan = state.get("spectra_plan", {})
    for compound in ordered_compounds(state):
        compound_plan = spectra_plan.get(compound.id or compound.number, {})
        updated_spectra = {}
        for nucleus, spectrum in compound.nmr_spectra.items():
            policy = compound_plan.get(nucleus, {}).get("peak_picking", "normal")
            updated_spectra[nucleus] = apply_peak_picking_policy(spectrum, policy)
        compound.nmr_spectra = updated_spectra
    return {"compounds": state.get("compounds", {})}
