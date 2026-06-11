from __future__ import annotations

import unittest

from si_generator.models import Compound
from si_generator.nmr_validation import count_c_from_13c_nmr, count_h_from_1h_nmr, validate_hrms


class NmrValidationTests(unittest.TestCase):
    def test_counts_1h_integrals(self) -> None:
        text = "δ = 8.07 (d, J = 15.8 Hz, 1H), 4.59 (s, 2H), 3.83 (s, 3H)."
        self.assertEqual(count_h_from_1h_nmr(text), 6)

    def test_counts_13c_peak_list(self) -> None:
        text = "δ = 167.2, 140.9, 136.7, 52.0, 30.7."
        self.assertEqual(count_c_from_13c_nmr(text), 5)

    def test_hrms_warning_for_bad_found_value(self) -> None:
        compound = Compound(number="x", name="X", formula="C2H6O", hrms_found="999.0000")
        validate_hrms([compound])
        self.assertIn("HRMS calcd", compound.nmr_check_warning)


if __name__ == "__main__":
    unittest.main()

