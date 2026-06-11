from __future__ import annotations

import unittest

from si_generator.domain.nmr import apply_peak_picking_policy, parse_nmr_spectrum, parse_nmr_signals


class NmrDomainTests(unittest.TestCase):
    def test_parses_proton_ranges_integrals_and_j_values(self) -> None:
        signals = parse_nmr_signals(
            "δ = 8.07 (d, J = 15.8 Hz, 1H, CH), 7.61 - 7.55 (m, 1H, Ar), "
            "4.59 (s, 2H, CH2Br)."
        )

        self.assertEqual(signals[0]["shift"], 8.07)
        self.assertEqual(signals[0]["multiplicity"], "d")
        self.assertEqual(signals[0]["j_values"], [15.8])
        self.assertEqual(signals[0]["integral"], 1.0)
        self.assertEqual(signals[0]["assignment"], "CH")
        self.assertEqual(signals[1]["shift_range"], (7.61, 7.55))
        self.assertEqual(signals[2]["integral"], 2.0)

    def test_parses_carbon_peak_list(self) -> None:
        spectrum = parse_nmr_spectrum("13C", "CDCl3, 150 MHz", "δ = 167.2, 140.9, 52.0.")

        self.assertEqual(spectrum["nucleus"], "13C")
        self.assertEqual(spectrum["conditions"], "CDCl3, 150 MHz")
        self.assertEqual([signal["shift"] for signal in spectrum["signals"]], [167.2, 140.9, 52.0])
        self.assertEqual(spectrum["formatted_text"], "δ = 167.2, 140.9, 52.0.")

    def test_peak_policy_keeps_formatted_text_and_marks_policy(self) -> None:
        spectrum = parse_nmr_spectrum("1H", "CDCl3, 600 MHz", "δ = 1.00 (s, 1H).")

        updated = apply_peak_picking_policy(spectrum, "minimal")

        self.assertEqual(updated["formatted_text"], spectrum["formatted_text"])
        self.assertEqual(updated["peak_picking"], "minimal")


if __name__ == "__main__":
    unittest.main()
