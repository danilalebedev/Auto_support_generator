from __future__ import annotations

import unittest

from si_generator.chemistry import calc_hrms_mz, ion_formula, parse_formula
from si_generator.domain.massspec import (
    build_hrms_block,
    calculate_hrms,
    extract_mz_text,
    hrms_adduct_text,
    hrms_found_text,
    hrms_label_text,
    parse_mz_value,
)


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
        self.assertEqual(result.isotope_labels, {"Br": 79})

    def test_builds_structured_hrms_block_with_halogen_isotopes(self) -> None:
        block = build_hrms_block(
            formula="C7H5ClO",
            label="HRMS (ESI-TOF) m/z",
            adduct="[M+H]+",
            found_text="141.0102",
        )

        self.assertEqual(block["adduct"], "[M+H]+")
        self.assertEqual(block["isotope_policy"], "auto_halogen")
        self.assertEqual(block["isotope_labels"], {"Cl": 35})
        self.assertEqual(block["ion_formula"], "C7H6ClO+")
        self.assertEqual(block["found_mz"], 141.0102)

    def test_hrms_decimal_comma_is_accepted(self) -> None:
        self.assertEqual(parse_mz_value("272,9921"), 272.9921)
        self.assertEqual(extract_mz_text("calcd 100.0000. Found 272,9921"), "272.9921")
        block = build_hrms_block(
            formula="C11H10BrFO2",
            label="HRMS (ESI/Q-TOF) m/z",
            adduct="[M+H]+",
            found_text="272,9921",
        )

        self.assertEqual(block["found_mz"], 272.9921)

    def test_hrms_block_helpers_prefer_legacy_found_and_structured_adduct(self) -> None:
        block = {"adduct": "[M+Na]+", "found_text": "83.0104", "label": "HRMS (ESI/Q-TOF) m/z"}

        self.assertEqual(hrms_found_text(block, legacy_found="84.0000"), "84.0000")
        self.assertEqual(hrms_found_text(block), "83.0104")
        self.assertEqual(hrms_adduct_text(block, "[M+H]+"), "[M+Na]+")
        self.assertEqual(hrms_label_text(block, "HRMS"), "HRMS (ESI/Q-TOF) m/z")


if __name__ == "__main__":
    unittest.main()

