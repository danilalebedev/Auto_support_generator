from __future__ import annotations

import unittest

from si_generator.chemistry import calc_hrms_mz
from si_generator.domain.compound import Compound
from si_generator.nmr_validation import count_c_from_13c_nmr, count_h_from_1h_nmr, validate_elemental_analysis, validate_hrms, validate_support


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
        self.assertEqual(compound.validation_issues[0]["code"], "HRMS_MISMATCH")

    def test_hrms_validation_uses_five_ppm_organic_letters_limit(self) -> None:
        compound = Compound(
            number="2d",
            name="Wrong HRMS example",
            formula="C11H10BrNO4",
            hrms={"adduct": "[M+H]+", "calculated_mz": 299.9866, "found_text": "299.9900"},
        )

        validate_hrms([compound])

        self.assertEqual(compound.validation_issues[0]["code"], "HRMS_MISMATCH")
        self.assertIn("error 11.3 ppm; limit 5 ppm", compound.nmr_check_warning)

    def test_hrms_validation_accepts_value_within_five_ppm(self) -> None:
        compound = Compound(
            number="2d",
            name="Valid HRMS example",
            formula="C11H10BrNO4",
            hrms={"adduct": "[M+H]+", "calculated_mz": 299.9866, "found_text": "299.9879"},
        )

        validate_hrms([compound])

        self.assertEqual(compound.validation_issues, [])
        self.assertEqual(compound.nmr_check_warning, "")

    def test_hrms_validation_uses_structured_block_adduct(self) -> None:
        found = f"{calc_hrms_mz('C2H4O2', '[M+Na]+'):.4f}"
        compound = Compound(number="x", name="X", formula="C2H4O2", hrms={"adduct": "[M+Na]+", "found_text": found})

        validate_hrms([compound])

        self.assertEqual(compound.nmr_check_warning, "")
        self.assertEqual(compound.validation_issues, [])

    def test_hrms_validation_accepts_decimal_comma(self) -> None:
        found = f"{calc_hrms_mz('C2H6O', '[M+H]+'):.4f}".replace(".", ",")
        compound = Compound(number="x", name="X", formula="C2H6O", hrms_found=found)

        validate_hrms([compound])

        self.assertEqual(compound.nmr_check_warning, "")
        self.assertEqual(compound.validation_issues, [])

    def test_support_validation_accepts_matching_nmr_hrms_and_elemental_analysis(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C2H6O",
            h1_nmr="δ = 3.70 (q, J = 7.0 Hz, 2H), 1.20 (t, J = 7.0 Hz, 3H), 2.00 (br s, 1H).",
            c13_nmr="δ = 58.0, 18.0.",
            hrms_found="47.0491",
            hrms_adduct="[M+H]+",
            elemental_analysis={"found": {"C": 52.10, "H": 13.20}},
        )

        validate_support([compound])

        self.assertEqual(compound.nmr_check_warning, "")
        self.assertEqual(compound.validation_issues, [])

    def test_13c_validation_allows_fluorine_coupling_peak_overcount(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C11H10BrFO2",
            c13_nmr=(
                "δ = 166.8, 161.8, 160.2, 139.7, 139.6, 136.0, 130.4, 130.3, "
                "124.4, 124.3, 123.0, 123.0, 122.2, 117.0, 116.9, 52.1, 21.6, 21.6."
            ),
        )

        validate_support([compound])

        self.assertEqual(compound.nmr_check_warning, "")
        self.assertEqual(compound.validation_issues, [])

    def test_13c_validation_still_warns_when_fluorinated_spectrum_misses_carbons(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C11H10BrFO2",
            c13_nmr="δ = 166.8, 139.7, 136.0, 130.4, 124.4, 52.1, 21.6.",
        )

        validate_support([compound])

        self.assertIn("C expected 11, found 7", compound.nmr_check_warning)
        self.assertEqual(compound.validation_issues[0]["code"], "NMR_C_COUNT_MISMATCH")

    def test_mnova_derived_1h_mismatch_adds_actionable_review_issue(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C2H6O",
            h1_nmr="delta = 3.70 (q, J = 7.0 Hz, 2H).",
            h1_mnova_path="x_1H.mnova",
        )

        validate_support([compound])

        issues_by_code = {issue["code"]: issue for issue in compound.validation_issues}
        self.assertIn("NMR_H_COUNT_MISMATCH", issues_by_code)
        self.assertIn("MNOVA_1H_REPORT_REVIEW_REQUIRED", issues_by_code)
        self.assertIn("auto integration", issues_by_code["MNOVA_1H_REPORT_REVIEW_REQUIRED"]["detail"])
        self.assertIn("H expected 6, found 2", compound.nmr_check_warning)
        self.assertNotIn("auto integration", compound.nmr_check_warning)

    def test_manual_1h_mismatch_does_not_add_mnova_review_issue(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C2H6O",
            h1_nmr="delta = 3.70 (q, J = 7.0 Hz, 2H).",
        )

        validate_support([compound])

        self.assertEqual({issue["code"] for issue in compound.validation_issues}, {"NMR_H_COUNT_MISMATCH"})

    def test_support_validation_warns_for_nmr_elemental_analysis_and_hrms_mismatch(self) -> None:
        compound = Compound(
            number="x",
            name="X",
            formula="C2H6O",
            h1_nmr="δ = 3.70 (q, J = 7.0 Hz, 2H).",
            c13_nmr="δ = 58.0.",
            hrms_found="999.0000",
            elemental_analysis={"found": {"C": 60.00, "H": 13.20}},
        )

        validate_support([compound])

        self.assertIn("H expected 6, found 2", compound.nmr_check_warning)
        self.assertIn("C expected 2, found 1", compound.nmr_check_warning)
        self.assertIn("HRMS calcd", compound.nmr_check_warning)
        self.assertIn("EA C calcd 52.14, found 60.00", compound.nmr_check_warning)
        self.assertEqual(
            {issue["code"] for issue in compound.validation_issues},
            {"NMR_H_COUNT_MISMATCH", "NMR_C_COUNT_MISMATCH", "HRMS_MISMATCH", "ELEMENTAL_ANALYSIS_MISMATCH"},
        )

    def test_elemental_analysis_validation_updates_block(self) -> None:
        compound = Compound(number="x", name="X", formula="C17H11FN2O3", elemental_analysis={"found": "C, 66.03; H, 3.55; N, 8.92"})

        validate_elemental_analysis([compound])

        self.assertEqual(compound.elemental_analysis["calculated"]["C"], 65.81)
        self.assertEqual(compound.elemental_analysis["found"]["N"], 8.92)
        self.assertEqual(compound.validation_issues, [])

    def test_elemental_analysis_accepts_difference_at_organic_letters_limit(self) -> None:
        compound = Compound(
            number="x",
            name="EA boundary",
            formula="C17H11FN2O3",
            elemental_analysis={"found": {"C": 66.21, "H": 3.57, "N": 9.03}},
        )

        validate_elemental_analysis([compound])

        self.assertEqual(compound.validation_issues, [])

    def test_elemental_analysis_warns_above_organic_letters_limit(self) -> None:
        compound = Compound(
            number="x",
            name="EA outside limit",
            formula="C17H11FN2O3",
            elemental_analysis={"found": {"C": 66.22, "H": 3.57, "N": 9.03}},
        )

        validate_elemental_analysis([compound])

        self.assertEqual(compound.validation_issues[0]["code"], "ELEMENTAL_ANALYSIS_MISMATCH")
        self.assertIn("EA C calcd 65.81, found 66.22", compound.nmr_check_warning)

    def test_elemental_analysis_validation_warns_for_unexpected_element(self) -> None:
        compound = Compound(number="x", name="X", formula="C2H6O", elemental_analysis={"found": {"C": 52.10, "N": 1.25}})

        validate_elemental_analysis([compound])

        self.assertIn("EA N found 1.25", compound.nmr_check_warning)
        self.assertEqual(compound.validation_issues[0]["code"], "ELEMENTAL_ANALYSIS_UNEXPECTED_ELEMENT")

    def test_elemental_analysis_validation_warns_for_missing_expected_element(self) -> None:
        compound = Compound(number="x", name="X", formula="C2H6O", elemental_analysis={"found": {"C": 52.10}})

        validate_elemental_analysis([compound])

        self.assertIn("EA H is missing from found values", compound.nmr_check_warning)
        self.assertEqual(compound.validation_issues[0]["code"], "ELEMENTAL_ANALYSIS_MISSING_ELEMENT")


if __name__ == "__main__":
    unittest.main()

