from __future__ import annotations

import unittest

from si_generator.domain.spectra_config import build_spectra_config, build_spectrum_render_spec


class BaselineConfigTests(unittest.TestCase):
    def test_default_baseline_config_applies_only_to_13c(self) -> None:
        config = build_spectra_config()

        h1 = build_spectrum_render_spec("1H", config)
        c13 = build_spectrum_render_spec("13C", config)

        self.assertEqual(config["baseline_mode"], "auto")
        self.assertFalse(config["baseline_apply_1h"])
        self.assertTrue(config["baseline_apply_13c"])
        self.assertEqual(config["baseline_poly_order"], 3)
        self.assertEqual(config["whittaker_lambda"], 100000.0)
        self.assertEqual(config["whittaker_asymmetry"], 0.001)
        self.assertEqual(h1["baseline_mode"], "auto")
        self.assertFalse(h1["baseline_apply"])
        self.assertEqual(c13["baseline_mode"], "auto")
        self.assertTrue(c13["baseline_apply"])

    def test_baseline_mode_off_is_propagated_to_render_specs(self) -> None:
        config = build_spectra_config(baseline_mode="off", baseline_apply_13c=True)

        c13 = build_spectrum_render_spec("13C", config)

        self.assertEqual(config["baseline_mode"], "off")
        self.assertEqual(c13["baseline_mode"], "off")
        self.assertTrue(c13["baseline_apply"])

    def test_baseline_mode_bernstein_keeps_polynomial_order(self) -> None:
        config = build_spectra_config(baseline_mode="bernstein", baseline_poly_order=5)

        c13 = build_spectrum_render_spec("13C", config)

        self.assertEqual(config["baseline_mode"], "bernstein")
        self.assertEqual(config["baseline_poly_order"], 5)
        self.assertEqual(c13["baseline_mode"], "bernstein")
        self.assertEqual(c13["baseline_poly_order"], 5)

    def test_baseline_mode_whittaker_keeps_expert_parameters(self) -> None:
        config = build_spectra_config(
            baseline_mode="whittaker",
            baseline_apply_1h=True,
            baseline_apply_13c=False,
            whittaker_lambda=250000,
            whittaker_asymmetry=0.002,
        )

        h1 = build_spectrum_render_spec("1H", config)
        c13 = build_spectrum_render_spec("13C", config)

        self.assertEqual(config["baseline_mode"], "whittaker")
        self.assertTrue(config["baseline_apply_1h"])
        self.assertFalse(config["baseline_apply_13c"])
        self.assertEqual(config["whittaker_lambda"], 250000.0)
        self.assertEqual(config["whittaker_asymmetry"], 0.002)
        self.assertEqual(h1["baseline_mode"], "whittaker")
        self.assertTrue(h1["baseline_apply"])
        self.assertEqual(h1["whittaker_lambda"], 250000.0)
        self.assertEqual(h1["whittaker_asymmetry"], 0.002)
        self.assertFalse(c13["baseline_apply"])


if __name__ == "__main__":
    unittest.main()
