from __future__ import annotations

from .types import PeakPickingPolicy, SpectraProcessingConfig, SpectrumEmbedMode, SpectrumRenderSpec


DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION = 0.80
DEFAULT_PEAK_PICKING: PeakPickingPolicy = "normal"
DEFAULT_X_RANGES = {
    "1H": (-1.0, 12.0),
    "13C": (-10.0, 210.0),
}


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


def build_spectrum_render_spec(
    nucleus: str,
    spectra_config: SpectraProcessingConfig | dict | None = None,
) -> SpectrumRenderSpec:
    config = spectra_config or {}
    spec: SpectrumRenderSpec = {
        "nucleus": nucleus,
        "x_range_ppm": DEFAULT_X_RANGES[nucleus],
        "target_signal_height_fraction": float(config.get("target_signal_height_fraction", DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)),
        "peak_picking": config.get("peak_picking", DEFAULT_PEAK_PICKING),
    }
    ignore_regions = config.get("ignore_regions_ppm", {})
    if isinstance(ignore_regions, dict) and nucleus in ignore_regions:
        spec["ignore_regions_ppm"] = ignore_regions[nucleus]
    return spec
