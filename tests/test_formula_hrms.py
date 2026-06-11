from __future__ import annotations

import unittest

from si_generator.chemistry import calc_hrms_mz, ion_formula, parse_formula
from si_generator.domain.massspec import calculate_hrms


class FormulaHrmsTests(unittest.TestCase):
    def test_parse_formula_preserves_order_and_counts(self) -> None:
        self.assertEqual(dict(parse_formula("C11H11BrFO2")), {"C": 11, "H": 11, "Br": 1, "F": 1, "O": 2})

    def test_calculates_example_hrms(self) -> None:
        self.assertEqual(calc_hrms_mz("C11H10BrFO2", "[M+H]+"), 272.9921)

    def test_ion_formula_adds_adduct(self) -> None:
        self.assertEqual(ion_formula("C2H4O2", "[M+Na]+"), "C2H4O2Na+")

    def test_domain_hrms_result_groups_calculated_values(self) -> None:
        result = calculate_hrms("C11H10BrFO2", "[M+H]+")

        self.assertEqual(result.calculated_mz, 272.9921)
        self.assertEqual(result.ion_formula, "C11H11BrFO2+")


if __name__ == "__main__":
    unittest.main()

