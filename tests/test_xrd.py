from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.domain.xrd import xrd_formatted_text, xrd_from_fields
from si_generator.input_table import read_compounds
from si_generator.word_input import _map_row


class XRDTests(unittest.TestCase):
    def test_xrd_formatted_text_prefers_explicit_text(self) -> None:
        self.assertEqual(
            xrd_formatted_text({"formatted_text": "X-ray diffraction data confirmed the structure"}),
            "X-ray diffraction data confirmed the structure.",
        )

    def test_csv_input_reads_xrd_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text(
                "number,name,formula,ccdc,cif,checkcif,xrd_figures\n"
                "2a,Example,C2H6O,2350001,2a.cif,2a_checkcif.pdf,fig1.png; fig2.png\n",
                encoding="utf-8",
            )

            compounds = read_compounds(path)

        self.assertEqual(compounds[0].xrd["ccdc_number"], "2350001")
        self.assertEqual(compounds[0].xrd["cif_path"], "2a.cif")
        self.assertEqual(compounds[0].xrd["checkcif_path"], "2a_checkcif.pdf")
        self.assertEqual(compounds[0].xrd["figure_paths"], ["fig1.png", "fig2.png"])

    def test_word_header_mapping_reads_xrd_fields(self) -> None:
        fields = _map_row(
            ["No", "Name", "XRD", "CCDC", "CIF", "checkCIF report", "XRD figures"],
            ["2a", "Example", "XRD data were collected", "2350001", "2a.cif", "2a_checkcif.pdf", "fig1.png; fig2.png"],
        )

        block = xrd_from_fields(fields)

        self.assertEqual(block["formatted_text"], "XRD data were collected")
        self.assertEqual(block["ccdc_number"], "2350001")
        self.assertEqual(block["cif_path"], "2a.cif")
        self.assertEqual(block["checkcif_path"], "2a_checkcif.pdf")
        self.assertEqual(block["figure_paths"], ["fig1.png", "fig2.png"])


if __name__ == "__main__":
    unittest.main()
