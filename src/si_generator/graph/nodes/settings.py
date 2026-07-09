from __future__ import annotations

from ..state import GenerateSIState
from ...domain.generation_config import build_generation_config
from ...domain.references import load_reference_store
from ...domain.runtime_config import build_runtime_config
from ...domain.spectra_config import build_spectra_config


def load_settings_node(state: GenerateSIState) -> dict:
    request = state["request"]
    return {
        "reference_store": load_reference_store(request.references_path),
        "spectra_config": build_spectra_config(
            extract_nmr=not request.no_extract_nmr,
            insert_spectra_as=request.insert_spectra_as,
            mnova_executable_path=str(request.mnova_exe) if request.mnova_exe else None,
            mnova_graphics_profile_path=str(request.mnova_graphics_profile) if request.mnova_graphics_profile else None,
            target_signal_height_fraction=request.target_signal_height_fraction,
            peak_threshold_fraction=request.peak_threshold_fraction,
            peak_threshold_fraction_1h=request.peak_threshold_fraction_1h,
            peak_threshold_fraction_13c=request.peak_threshold_fraction_13c,
            x_range_ppm_1h=request.x_range_ppm_1h,
            x_range_ppm_13c=request.x_range_ppm_13c,
            baseline_mode=request.baseline_mode,
            baseline_apply_1h=request.baseline_apply_1h,
            baseline_apply_13c=request.baseline_apply_13c,
            baseline_poly_order=request.baseline_poly_order,
            whittaker_lambda=request.whittaker_lambda,
            whittaker_asymmetry=request.whittaker_asymmetry,
            highlight_solvent_peaks=request.highlight_solvent_peaks,
        ),
        "generation_config": build_generation_config(
            generate_loadings=request.generate_loadings,
            calculate_elemental_analysis=request.calculate_elemental_analysis,
            has_references=bool(request.references_path),
            check_support=not request.no_check_support,
        ),
        "runtime_config": build_runtime_config(),
    }

