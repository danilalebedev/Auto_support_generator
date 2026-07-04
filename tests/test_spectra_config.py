from __future__ import annotations

import unittest

from si_generator.domain.types import SpectraConfig, SpectraProcessingConfig
from si_generator.domain.spectra_config import (
    DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
    DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
    DEFAULT_PEAK_PICKING,
    DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
    DEFAULT_X_RANGES,
    build_spectrum_render_spec,
    build_spectra_config,
)


class SpectraConfigTests(unittest.TestCase):
    def test_legacy_spectra_processing_config_alias_matches_spectra_config(self) -> None:
        self.assertIs(SpectraProcessingConfig, SpectraConfig)

    def test_builds_default_spectra_processing_config(self) -> None:
        config = build_spectra_config()

        self.assertTrue(config["extract_nmr"])
        self.assertEqual(config["insert_spectra_as"], "png")
        self.assertEqual(config["target_signal_height_fraction"], DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)
        self.assertEqual(config["peak_threshold_fraction_1h"], DEFAULT_H1_PEAK_THRESHOLD_FRACTION)
        self.assertEqual(config["peak_threshold_fraction_13c"], DEFAULT_C13_PEAK_THRESHOLD_FRACTION)
        self.assertEqual(config["baseline_mode"], "auto")
        self.assertFalse(config["baseline_apply_1h"])
        self.assertTrue(config["baseline_apply_13c"])
        self.assertEqual(config["baseline_poly_order"], 3)
        self.assertEqual(config["whittaker_lambda"], 100000.0)
        self.assertEqual(config["whittaker_asymmetry"], 0.001)
        self.assertTrue(config["solvent_suppression"])
        self.assertEqual(config["ignore_regions_ppm"], {})
        self.assertEqual(config["peak_picking"], DEFAULT_PEAK_PICKING)
        self.assertTrue(config["keep_intermediate_reports"])
        self.assertNotIn("mnova_executable_path", config)

    def test_builds_spectra_processing_config_from_runtime_flags(self) -> None:
        config = build_spectra_config(
            extract_nmr=False,
            insert_spectra_as="mnova",
            mnova_executable_path="C:/Tools/MestReNova.exe",
            peak_threshold_fraction_1h=0.08,
            peak_threshold_fraction_13c=0.035,
            baseline_mode="whittaker",
            baseline_apply_1h=True,
            baseline_apply_13c=False,
            baseline_poly_order=5,
            whittaker_lambda=250000,
            whittaker_asymmetry=0.002,
        )

        self.assertFalse(config["extract_nmr"])
        self.assertEqual(config["insert_spectra_as"], "mnova")
        self.assertEqual(config["mnova_executable_path"], "C:/Tools/MestReNova.exe")
        self.assertEqual(config["peak_threshold_fraction_1h"], 0.08)
        self.assertEqual(config["peak_threshold_fraction_13c"], 0.035)
        self.assertEqual(config["baseline_mode"], "whittaker")
        self.assertTrue(config["baseline_apply_1h"])
        self.assertFalse(config["baseline_apply_13c"])
        self.assertEqual(config["baseline_poly_order"], 5)
        self.assertEqual(config["whittaker_lambda"], 250000.0)
        self.assertEqual(config["whittaker_asymmetry"], 0.002)

    def test_builds_spectrum_render_spec_from_spectra_config(self) -> None:
        spec = build_spectrum_render_spec(
            "13C",
            {
                "target_signal_height_fraction": 0.7,
                "peak_threshold_fraction_13c": 0.045,
                "peak_picking": "minimal",
                "ignore_regions_ppm": {"13C": [(76.0, 78.2)]},
                "baseline_mode": "whittaker",
                "baseline_apply_13c": True,
            },
        )

        self.assertEqual(spec["x_range_ppm"], DEFAULT_X_RANGES["13C"])
        self.assertEqual(spec["target_signal_height_fraction"], 0.7)
        self.assertEqual(spec["peak_threshold_fraction"], 0.045)
        self.assertEqual(spec["peak_picking"], "minimal")
        self.assertEqual(spec["ignore_regions_ppm"], [(76.0, 78.2)])
        self.assertEqual(spec["baseline_mode"], "whittaker")
        self.assertTrue(spec["baseline_apply"])

    def test_shared_peak_threshold_is_used_as_backward_compatible_fallback(self) -> None:
        config = build_spectra_config(peak_threshold_fraction=0.09)

        self.assertEqual(config["peak_threshold_fraction_1h"], 0.09)
        self.assertEqual(config["peak_threshold_fraction_13c"], 0.09)


if __name__ == "__main__":
    unittest.main()
