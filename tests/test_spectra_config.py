from __future__ import annotations

import unittest

from si_generator.domain.spectra_config import (
    DEFAULT_PEAK_PICKING,
    DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
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


if __name__ == "__main__":
    unittest.main()
