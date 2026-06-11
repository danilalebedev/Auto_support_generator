from __future__ import annotations

from pathlib import Path

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...domain.spectra_config import DEFAULT_PEAK_PICKING, DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION
from ...domain.types import SpectrumRenderSpec
from ...nmr_fill import fill_nmr_from_mnova
from ...spectra_zip import assign_spectra_from_folder, prepare_spectra_zip


DEFAULT_X_RANGES = {
    "1H": (-1.0, 12.0),
    "13C": (-10.0, 210.0),
}


def prepare_spectra_zip_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    if not request.spectra_zip:
        return {}

    spectra_root = prepare_spectra_zip(request.spectra_zip, request.output_dir / "logs" / "_spectra_zip")
    assign_spectra_from_folder(compounds, spectra_root)
    return {"compounds": state.get("compounds", {}), "artifacts": {**state.get("artifacts", {}), "spectra_root": str(spectra_root)}}


def plan_nmr_processing_node(state: GenerateSIState) -> dict:
    spectra_plan: dict[str, dict[str, SpectrumRenderSpec]] = {}
    spectra_config = state.get("spectra_config", {})

    for compound in ordered_compounds(state):
        compound_plan: dict[str, SpectrumRenderSpec] = {}
        if compound.h1_spectrum_path:
            compound_plan["1H"] = _default_render_spec("1H", spectra_config)
        if compound.c13_spectrum_path:
            compound_plan["13C"] = _default_render_spec("13C", spectra_config)
        if compound_plan:
            compound_id = compound.id or compound.number
            spectra_plan[compound_id] = compound_plan

    return {"spectra_plan": spectra_plan}


def route_nmr_processing(state: GenerateSIState) -> str:
    request = state["request"]
    spectra_config = state.get("spectra_config", {})
    extract_nmr = bool(spectra_config.get("extract_nmr", not request.no_extract_nmr))
    if not extract_nmr:
        return "skip_mnova"
    for compound in ordered_compounds(state):
        if compound.h1_spectrum_path or compound.c13_spectrum_path:
            return "run_mnova"
    return "skip_mnova"


def mnova_batch_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    spectra_config = state.get("spectra_config", {})
    mnova_exe = request.mnova_exe
    if not mnova_exe and spectra_config.get("mnova_executable_path"):
        mnova_exe = Path(str(spectra_config["mnova_executable_path"]))
    fill_nmr_from_mnova(
        compounds,
        request.input_base_dir,
        request.output_dir / "logs" / "mnova_batch",
        output_root=request.output_dir,
        mnova_exe=mnova_exe,
        render_specs_by_compound=state.get("spectra_plan"),
    )
    return {"compounds": state.get("compounds", {})}


def _default_render_spec(nucleus: str, spectra_config: dict) -> SpectrumRenderSpec:
    spec: SpectrumRenderSpec = {
        "nucleus": nucleus,
        "x_range_ppm": DEFAULT_X_RANGES[nucleus],
        "target_signal_height_fraction": float(spectra_config.get("target_signal_height_fraction", DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)),
        "peak_picking": spectra_config.get("peak_picking", DEFAULT_PEAK_PICKING),
    }
    ignore_regions = spectra_config.get("ignore_regions_ppm", {})
    if isinstance(ignore_regions, dict) and nucleus in ignore_regions:
        spec["ignore_regions_ppm"] = ignore_regions[nucleus]
    return spec

