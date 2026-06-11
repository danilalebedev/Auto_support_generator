from __future__ import annotations

from .types import PeakPickingPolicy, SpectraProcessingConfig, SpectrumEmbedMode


DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION = 0.80
DEFAULT_PEAK_PICKING: PeakPickingPolicy = "normal"


def build_spectra_config(
    *,
    extract_nmr: bool = True,
    insert_spectra_as: SpectrumEmbedMode = "png",
    mnova_executable_path: str | None = None,
) -> SpectraProcessingConfig:
    config: SpectraProcessingConfig = {
        "extract_nmr": extract_nmr,
        "insert_spectra_as": insert_spectra_as,
        "target_signal_height_fraction": DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
        "solvent_suppression": True,
        "ignore_regions_ppm": {},
        "peak_picking": DEFAULT_PEAK_PICKING,
        "keep_intermediate_reports": True,
    }
    if mnova_executable_path:
        config["mnova_executable_path"] = mnova_executable_path
    return config
