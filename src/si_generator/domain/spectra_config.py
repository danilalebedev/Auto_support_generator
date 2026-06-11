from __future__ import annotations

from .types import PeakPickingPolicy, SpectraConfig, SpectrumEmbedMode, SpectrumRenderSpec


DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION = 0.80
DEFAULT_H1_PEAK_THRESHOLD_FRACTION = 0.06
DEFAULT_C13_PEAK_THRESHOLD_FRACTION = 0.04
DEFAULT_PEAK_THRESHOLD_FRACTION = DEFAULT_H1_PEAK_THRESHOLD_FRACTION
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
    peak_threshold_fraction: float | None = None,
    peak_threshold_fraction_1h: float | None = None,
    peak_threshold_fraction_13c: float | None = None,
) -> SpectraConfig:
    config: SpectraConfig = {
        "extract_nmr": extract_nmr,
        "insert_spectra_as": insert_spectra_as,
        "target_signal_height_fraction": DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
        "peak_threshold_fraction_1h": _normalized_fraction(
            peak_threshold_fraction_1h if peak_threshold_fraction_1h is not None else peak_threshold_fraction,
            DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
        ),
        "peak_threshold_fraction_13c": _normalized_fraction(
            peak_threshold_fraction_13c if peak_threshold_fraction_13c is not None else peak_threshold_fraction,
            DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
        ),
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
    spectra_config: SpectraConfig | dict | None = None,
) -> SpectrumRenderSpec:
    config = spectra_config or {}
    default_threshold = _default_peak_threshold(nucleus)
    threshold_key = "peak_threshold_fraction_1h" if nucleus == "1H" else "peak_threshold_fraction_13c"
    spec: SpectrumRenderSpec = {
        "nucleus": nucleus,
        "x_range_ppm": DEFAULT_X_RANGES[nucleus],
        "target_signal_height_fraction": float(config.get("target_signal_height_fraction", DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)),
        "peak_threshold_fraction": _normalized_fraction(
            config.get(threshold_key, config.get("peak_threshold_fraction")),
            default_threshold,
        ),
        "peak_picking": config.get("peak_picking", DEFAULT_PEAK_PICKING),
    }
    ignore_regions = config.get("ignore_regions_ppm", {})
    if isinstance(ignore_regions, dict) and nucleus in ignore_regions:
        spec["ignore_regions_ppm"] = ignore_regions[nucleus]
    return spec


def _default_peak_threshold(nucleus: str) -> float:
    return DEFAULT_C13_PEAK_THRESHOLD_FRACTION if nucleus == "13C" else DEFAULT_H1_PEAK_THRESHOLD_FRACTION


def _normalized_fraction(value, fallback: float) -> float:
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        return fallback
    if fraction < 0:
        return 0
    if fraction > 1:
        return 1
    return fraction
