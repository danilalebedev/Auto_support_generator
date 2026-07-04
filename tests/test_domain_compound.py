from __future__ import annotations

import unittest

from si_generator.domain.compound import Compound as DomainCompound
from si_generator.domain.compound import compound_to_domain_dict
from si_generator.models import Compound as CompatibilityCompound


class DomainCompoundTests(unittest.TestCase):
    def test_legacy_models_import_reexports_domain_compound(self) -> None:
        self.assertIs(CompatibilityCompound, DomainCompound)

    def test_compound_domain_snapshot_preserves_structured_blocks(self) -> None:
        compound = DomainCompound(
            id="cmp_001",
            number="2a",
            name="Example",
            formula="C2H6O",
            color="white",
            state="solid",
            h1_nmr="δ = 1.23 (s, 6H).",
            h1_conditions="CDCl3, 600 MHz",
            hrms_found="47.0491",
            ir="IR (ATR, cm-1): 3038, 2957.",
            xrd={"ccdc_number": "2350001", "cif_path": "2a.cif"},
            references=["ref1"],
        )

        snapshot = compound_to_domain_dict(compound)

        self.assertEqual(snapshot["id"], "cmp_001")
        self.assertEqual(snapshot["number"], "2a")
        self.assertEqual(snapshot["physical"]["color"], "white")
        self.assertEqual(snapshot["nmr"]["spectra"]["1H"]["formatted_text"], "δ = 1.23 (s, 6H).")
        self.assertEqual(snapshot["hrms"]["found_text"], "47.0491")
        self.assertEqual(snapshot["ir"]["method"], "ATR")
        self.assertEqual(snapshot["xrd"]["ccdc_number"], "2350001")
        self.assertEqual(snapshot["xrd"]["cif_path"], "2a.cif")
        self.assertEqual(snapshot["references"], ["ref1"])

    def test_compound_domain_snapshot_omits_empty_default_hrms(self) -> None:
        snapshot = compound_to_domain_dict(DomainCompound(id="cmp_001", number="2a", name="Example"))

        self.assertNotIn("hrms", snapshot)


if __name__ == "__main__":
    unittest.main()
