from __future__ import annotations

import unittest

from si_generator.domain.spectra_config import (
    DEFAULT_PEAK_PICKING,
    DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
    DEFAULT_X_RANGES,
    build_spectrum_render_spec,
    build_spectra_config,
)


class SpectraConfigTests(unittest.TestCase):
    def test_builds_default_spectra_processing_config(self) -> None:
        config = build_spectra_config()

        self.assertTrue(config["extract_nmr"])
        self.assertEqual(config["insert_spectra_as"], "png")
        self.assertEqual(config["target_signal_height_fraction"], DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION)
        self.assertTrue(config["solvent_suppression"])
        self.assertEqual(config["ignore_regions_ppm"], {})
        self.assertEqual(config["peak_picking"], DEFAULT_PEAK_PICKING)
        self.assertTrue(config["keep_intermediate_reports"])
        self.assertNotIn("mnova_executable_path", config)

    def test_builds_spectra_processing_config_from_runtime_flags(self) -> None:
        config = build_spectra_config(
            extract_nmr=False,
            insert_spectra_as="both",
            mnova_executable_path="C:/Tools/MestReNova.exe",
        )

        self.assertFalse(config["extract_nmr"])
        self.assertEqual(config["insert_spectra_as"], "both")
        self.assertEqual(config["mnova_executable_path"], "C:/Tools/MestReNova.exe")

    def test_builds_spectrum_render_spec_from_spectra_config(self) -> None:
        spec = build_spectrum_render_spec(
            "13C",
            {
                "target_signal_height_fraction": 0.7,
                "peak_picking": "minimal",
                "ignore_regions_ppm": {"13C": [(76.0, 78.2)]},
            },
        )

        self.assertEqual(spec["x_range_ppm"], DEFAULT_X_RANGES["13C"])
        self.assertEqual(spec["target_signal_height_fraction"], 0.7)
        self.assertEqual(spec["peak_picking"], "minimal")
        self.assertEqual(spec["ignore_regions_ppm"], [(76.0, 78.2)])


if __name__ == "__main__":
    unittest.main()
