from __future__ import annotations

import unittest

from si_generator.domain.compound import Compound as DomainCompound
from si_generator.domain.compound import compound_from_domain_dict, compound_to_domain_dict


class DomainCompoundTests(unittest.TestCase):
    def test_compound_domain_snapshot_preserves_structured_blocks(self) -> None:
        compound = DomainCompound(
            id="cmp_001",
            number="2a",
            name="Example",
            formula="C2H6O",
            smiles="CCO",
            color="white",
            state="solid",
            h1_nmr="δ = 1.23 (s, 6H).",
            h1_conditions="CDCl3, 600 MHz",
            cif_folder="input/2a/cif",
            cif_files=["input/2a/cif/2a.cif"],
            spectra_1d_folder="input/2a/spectra/1d",
            spectra_1d_files=["input/2a/spectra/1d/2a_1H"],
            spectra_2d_folder="input/2a/spectra/2d",
            spectra_2d_files=["input/2a/spectra/2d/2a_HSQC"],
            hrms_found="47.0491",
            ir="IR (ATR, cm-1): 3038, 2957.",
            references=["ref1"],
        )

        snapshot = compound_to_domain_dict(compound)

        self.assertEqual(snapshot["id"], "cmp_001")
        self.assertEqual(snapshot["number"], "2a")
        self.assertEqual(snapshot["structure"]["smiles"], "CCO")
        self.assertEqual(snapshot["physical"]["color"], "white")
        self.assertEqual(snapshot["structure"]["cif_folder"], "input/2a/cif")
        self.assertEqual(snapshot["structure"]["cif_files"], ["input/2a/cif/2a.cif"])
        self.assertTrue(snapshot["structure"]["has_cif"])
        self.assertEqual(snapshot["spectra"]["1D"]["source_folder"], "input/2a/spectra/1d")
        self.assertEqual(snapshot["spectra"]["2D"]["source_folder"], "input/2a/spectra/2d")
        self.assertEqual(snapshot["spectra"]["2D"]["files"], ["input/2a/spectra/2d/2a_HSQC"])
        self.assertEqual(snapshot["nmr"]["spectra"]["1H"]["formatted_text"], "δ = 1.23 (s, 6H).")
        self.assertEqual(snapshot["hrms"]["found_text"], "47.0491")
        self.assertEqual(snapshot["ir"]["method"], "ATR")
        self.assertEqual(snapshot["references"], ["ref1"])

    def test_compound_domain_snapshot_omits_empty_default_hrms(self) -> None:
        snapshot = compound_to_domain_dict(DomainCompound(id="cmp_001", number="2a", name="Example"))

        self.assertNotIn("hrms", snapshot)

    def test_compound_domain_round_trip_preserves_smiles(self) -> None:
        original = DomainCompound(
            id="cmp_001",
            number="2a",
            name="Example",
            formula="C2H6O",
            smiles="CCO",
            cif_folder="input/2a/cif",
            cif_files=["input/2a/cif/2a.cif"],
            spectra_2d_folder="input/2a/spectra/2d",
            spectra_2d_files=["input/2a/spectra/2d/2a_HSQC"],
        )

        restored = compound_from_domain_dict(compound_to_domain_dict(original))

        self.assertEqual(restored.smiles, "CCO")
        self.assertEqual(restored.cif_folder, "input/2a/cif")
        self.assertEqual(restored.cif_files, ["input/2a/cif/2a.cif"])
        self.assertEqual(restored.spectra_2d_folder, "input/2a/spectra/2d")
        self.assertEqual(restored.spectra_2d_files, ["input/2a/spectra/2d/2a_HSQC"])


if __name__ == "__main__":
    unittest.main()
