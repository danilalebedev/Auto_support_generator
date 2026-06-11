from __future__ import annotations

from ..state import GenerateSIState
from ...nmr_fill import fill_nmr_from_mnova
from ...spectra_zip import assign_spectra_from_folder, prepare_spectra_zip


def prepare_spectra_zip_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = state.get("compounds", [])
    if not request.spectra_zip:
        return {"compounds": compounds}

    spectra_root = prepare_spectra_zip(request.spectra_zip, request.output_dir / "logs" / "_spectra_zip")
    assign_spectra_from_folder(compounds, spectra_root)
    return {"compounds": compounds, "artifacts": {**state.get("artifacts", {}), "spectra_root": str(spectra_root)}}


def route_nmr_processing(state: GenerateSIState) -> str:
    request = state["request"]
    if request.no_extract_nmr:
        return "skip_mnova"
    for compound in state.get("compounds", []):
        if compound.h1_spectrum_path or compound.c13_spectrum_path:
            return "run_mnova"
    return "skip_mnova"


def mnova_batch_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = state.get("compounds", [])
    fill_nmr_from_mnova(
        compounds,
        request.input_base_dir,
        request.output_dir / "logs" / "mnova_batch",
        output_root=request.output_dir,
        mnova_exe=request.mnova_exe,
    )
    return {"compounds": compounds}

