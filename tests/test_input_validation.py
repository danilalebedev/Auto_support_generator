from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.input_validation import validate_compound_inputs
from si_generator.models import Compound


class InputValidationTests(unittest.TestCase):
    def test_solid_state_variants_require_melting_point(self) -> None:
        cases = [
            {"state": "solid", "color": ""},
            {"state": "white solid", "color": ""},
            {"state": "", "color": "белый порошок"},
            {"state": "кристаллический порошок", "color": "yellow"},
        ]
        for case in cases:
            with self.subTest(case=case):
                compound = _complete_compound(**case)

                warnings = validate_compound_inputs([compound])

                self.assertIn("2a: state looks solid, but melting point is missing.", warnings)

    def test_melting_point_suppresses_solid_state_warning(self) -> None:
        compound = _complete_compound(state="твёрдое вещество", color="white", melting_point="168-170")

        warnings = validate_compound_inputs([compound])

        self.assertNotIn("2a: state looks solid, but melting point is missing.", warnings)

    def test_invalid_formula_is_reported_as_input_warning(self) -> None:
        compound = _complete_compound(state="oil", color="yellow", formula="C2H6Xx")

        warnings = validate_compound_inputs([compound])

        self.assertTrue(any("2a: formula could not be parsed" in warning for warning in warnings))

    def test_missing_relative_spectrum_path_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            compound = _complete_compound(state="oil", color="yellow")
            compound.h1_spectrum_path = "spectra/2a/1H"

            warnings = validate_compound_inputs([compound], base_dir=Path(tmp))

        self.assertTrue(any("2a: 1H spectrum path does not exist:" in warning for warning in warnings))

    def test_spectrum_folder_without_fid_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "spectra" / "2a" / "1H"
            folder.mkdir(parents=True)
            compound = _complete_compound(state="oil", color="yellow")
            compound.h1_spectrum_path = str(folder)

            warnings = validate_compound_inputs([compound])

        self.assertTrue(any("2a: 1H spectrum folder does not contain a Bruker fid file:" in warning for warning in warnings))

    def test_spectrum_folder_with_nested_fid_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "spectra" / "2a"
            experiment = folder / "1H"
            experiment.mkdir(parents=True)
            (experiment / "fid").write_text("", encoding="utf-8")
            compound = _complete_compound(state="oil", color="yellow")
            compound.h1_spectrum_path = str(folder)

            warnings = validate_compound_inputs([compound])

        self.assertFalse(any("1H spectrum" in warning for warning in warnings))


def _complete_compound(*, state: str, color: str, melting_point: str = "", formula: str = "C2H6O") -> Compound:
    return Compound(
        number="2a",
        name="Example compound",
        formula=formula,
        hrms_found="47.0491",
        color=color,
        state=state,
        melting_point=melting_point,
        h1_nmr="1.23 (s, 6H)",
        c13_nmr="58.0",
    )


if __name__ == "__main__":
    unittest.main()
