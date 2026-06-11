from __future__ import annotations

import unittest

from si_generator.adapters.legacy_compound import (
    compound_dict_to_legacy_dataclass,
    legacy_compounds_to_domain,
    legacy_dataclass_to_compound_dict,
)
from si_generator.models import Compound


class LegacyCompoundAdapterTests(unittest.TestCase):
    def test_round_trips_legacy_compound_fields(self) -> None:
        original = Compound(
            number="2a",
            name="Methyl acrylate",
            preparation="Prepared from test reagents",
            yield_text="100 mg (50%)",
            color="white",
            state="solid",
            melting_point="80-82 C",
            rf="Rf = 0.4",
            formula="C11H11BrFO2",
            hrms_found="272.9921",
            h1_nmr="δ = 1.00 (s, 1H).",
            h1_conditions="CDCl3, 600 MHz",
            h1_spectrum_path="2a/1H",
            c13_nmr="δ = 10.0.",
            c13_conditions="CDCl3, 150 MHz",
            c13_spectrum_path="2a/13C",
            mnova_path="2a/2a.mnova",
            extra_nmr="19F NMR text",
            ir="IR text",
            has_word_structure=True,
            nmr_check_warning="warning",
        )
        converted = legacy_dataclass_to_compound_dict(original, compound_id="cmp_123")
        restored = compound_dict_to_legacy_dataclass(converted)

        self.assertEqual(converted["id"], "cmp_123")
        self.assertEqual(converted["number"], "2a")
        self.assertEqual(converted["physical"]["state"], "solid")
        self.assertEqual(converted["spectra"]["1H"]["source_path"], "2a/1H")
        self.assertEqual(restored.number, original.number)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.h1_nmr, original.h1_nmr)
        self.assertEqual(restored.mnova_path, original.mnova_path)
        self.assertEqual(restored.has_word_structure, original.has_word_structure)

    def test_assigns_stable_ids_and_order(self) -> None:
        compounds, order = legacy_compounds_to_domain(
            [Compound(number="2a", name="A"), Compound(number="2b", name="B")]
        )
        self.assertEqual(order, ["cmp_001", "cmp_002"])
        self.assertEqual(compounds["cmp_002"]["number"], "2b")


if __name__ == "__main__":
    unittest.main()
