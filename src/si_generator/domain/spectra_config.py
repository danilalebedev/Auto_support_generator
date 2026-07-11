from __future__ import annotations

from .types import BaselineMode, PeakPickingPolicy, SpectraConfig, SpectrumEmbedMode, SpectrumRenderSpec


DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION = 0.80
DEFAULT_H1_PEAK_THRESHOLD_FRACTION = 0.06
DEFAULT_C13_PEAK_THRESHOLD_FRACTION = 0.04
DEFAULT_BASELINE_MODE: BaselineMode = "auto"
DEFAULT_BASELINE_APPLY_1H = False
DEFAULT_BASELINE_APPLY_13C = True
DEFAULT_BASELINE_POLY_ORDER = 3
DEFAULT_WHITTAKER_LAMBDA = 100000.0
DEFAULT_WHITTAKER_ASYMMETRY = 0.001
DEFAULT_PEAK_THRESHOLD_FRACTION = DEFAULT_H1_PEAK_THRESHOLD_FRACTION
DEFAULT_PEAK_PICKING: PeakPickingPolicy = "normal"
DEFAULT_HIGHLIGHT_SOLVENT_PEAKS = False
DEFAULT_X_RANGES = {
    "1H": (-1.0, 12.0),
    "13C": (-10.0, 210.0),
}


def build_spectra_config(
    *,
    extract_nmr: bool = True,
    insert_spectra_as: SpectrumEmbedMode = "png",
    mnova_executable_path: str | None = None,
    mnova_graphics_profile_path: str | None = None,
    mnova_graphics_profile_1h_path: str | None = None,
    mnova_graphics_profile_13c_path: str | None = None,
    target_signal_height_fraction: float = DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
    peak_threshold_fraction: float | None = None,
    peak_threshold_fraction_1h: float | None = None,
    peak_threshold_fraction_13c: float | None = None,
    baseline_mode: BaselineMode | str = DEFAULT_BASELINE_MODE,
    baseline_apply_1h: bool = DEFAULT_BASELINE_APPLY_1H,
    baseline_apply_13c: bool = DEFAULT_BASELINE_APPLY_13C,
    baseline_poly_order: int = DEFAULT_BASELINE_POLY_ORDER,
    whittaker_lambda: float = DEFAULT_WHITTAKER_LAMBDA,
    whittaker_asymmetry: float = DEFAULT_WHITTAKER_ASYMMETRY,
    highlight_solvent_peaks: bool = DEFAULT_HIGHLIGHT_SOLVENT_PEAKS,
    x_range_ppm_1h: tuple[float, float] | None = None,
    x_range_ppm_13c: tuple[float, float] | None = None,
) -> SpectraConfig:
    config: SpectraConfig = {
        "extract_nmr": extract_nmr,
        "insert_spectra_as": insert_spectra_as,
        "target_signal_height_fraction": _target_signal_height_fraction(target_signal_height_fraction),
        "peak_threshold_fraction_1h": _normalized_fraction(
            peak_threshold_fraction_1h if peak_threshold_fraction_1h is not None else peak_threshold_fraction,
            DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
        ),
        "peak_threshold_fraction_13c": _normalized_fraction(
            peak_threshold_fraction_13c if peak_threshold_fraction_13c is not None else peak_threshold_fraction,
            DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
        ),
        "baseline_mode": _baseline_mode(baseline_mode),
        "baseline_apply_1h": bool(baseline_apply_1h),
        "baseline_apply_13c": bool(baseline_apply_13c),
        "baseline_poly_order": _positive_int(baseline_poly_order, DEFAULT_BASELINE_POLY_ORDER),
        "whittaker_lambda": _positive_float(whittaker_lambda, DEFAULT_WHITTAKER_LAMBDA),
        "whittaker_asymmetry": _normalized_fraction(whittaker_asymmetry, DEFAULT_WHITTAKER_ASYMMETRY),
        "x_ranges_ppm": {
            "1H": _x_range_ppm("1H", x_range_ppm_1h),
            "13C": _x_range_ppm("13C", x_range_ppm_13c),
        },
        "solvent_suppression": True,
        "highlight_solvent_peaks": bool(highlight_solvent_peaks),
        "ignore_regions_ppm": {},
        "peak_picking": DEFAULT_PEAK_PICKING,
        "keep_intermediate_reports": True,
    }
    if mnova_executable_path:
        config["mnova_executable_path"] = mnova_executable_path
    if mnova_graphics_profile_path:
        config["mnova_graphics_profile_path"] = mnova_graphics_profile_path
    if mnova_graphics_profile_1h_path:
        config["mnova_graphics_profile_1h_path"] = mnova_graphics_profile_1h_path
    if mnova_graphics_profile_13c_path:
        config["mnova_graphics_profile_13c_path"] = mnova_graphics_profile_13c_path
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
        "x_range_ppm": _render_x_range_ppm(nucleus, config),
        "target_signal_height_fraction": float(config.get("target_signal_height_fraction", DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)),
        "peak_threshold_fraction": _normalized_fraction(
            config.get(threshold_key, config.get("peak_threshold_fraction")),
            default_threshold,
        ),
        "peak_picking": config.get("peak_picking", DEFAULT_PEAK_PICKING),
        "baseline_mode": _baseline_mode(config.get("baseline_mode", DEFAULT_BASELINE_MODE)),
        "baseline_apply": _baseline_apply(nucleus, config),
        "baseline_poly_order": _positive_int(config.get("baseline_poly_order"), DEFAULT_BASELINE_POLY_ORDER),
        "whittaker_lambda": _positive_float(config.get("whittaker_lambda"), DEFAULT_WHITTAKER_LAMBDA),
        "whittaker_asymmetry": _normalized_fraction(config.get("whittaker_asymmetry"), DEFAULT_WHITTAKER_ASYMMETRY),
        "highlight_solvent_peaks": bool(config.get("highlight_solvent_peaks", DEFAULT_HIGHLIGHT_SOLVENT_PEAKS)),
    }
    ignore_regions = config.get("ignore_regions_ppm", {})
    if isinstance(ignore_regions, dict) and nucleus in ignore_regions:
        spec["ignore_regions_ppm"] = ignore_regions[nucleus]
    return spec


def _default_peak_threshold(nucleus: str) -> float:
    return DEFAULT_C13_PEAK_THRESHOLD_FRACTION if nucleus == "13C" else DEFAULT_H1_PEAK_THRESHOLD_FRACTION


def _render_x_range_ppm(nucleus: str, config: SpectraConfig | dict) -> tuple[float, float]:
    ranges = config.get("x_ranges_ppm", {})
    if isinstance(ranges, dict):
        return _x_range_ppm(nucleus, ranges.get(nucleus))
    return DEFAULT_X_RANGES[nucleus]


def _x_range_ppm(nucleus: str, value) -> tuple[float, float]:
    fallback = DEFAULT_X_RANGES[nucleus]
    if value is None:
        return fallback
    try:
        lower, upper = value
        first = float(lower)
        second = float(upper)
    except (TypeError, ValueError):
        return fallback
    if first == second:
        return fallback
    return (min(first, second), max(first, second))


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


def _target_signal_height_fraction(value) -> float:
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        fraction = DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION
    if fraction > 1:
        fraction /= 100
    if fraction < 0.20:
        return 0.20
    if fraction > 0.95:
        return 0.95
    return fraction


def _baseline_mode(value) -> BaselineMode:
    text = str(value or DEFAULT_BASELINE_MODE).strip().lower()
    if text in {"auto", "off", "bernstein", "whittaker"}:
        return text  # type: ignore[return-value]
    return DEFAULT_BASELINE_MODE


def _baseline_apply(nucleus: str, config: SpectraConfig | dict) -> bool:
    key = "baseline_apply_1h" if nucleus == "1H" else "baseline_apply_13c"
    if key in config:
        return bool(config[key])
    return DEFAULT_BASELINE_APPLY_1H if nucleus == "1H" else DEFAULT_BASELINE_APPLY_13C


def _positive_int(value, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _positive_float(value, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
