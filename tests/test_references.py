from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.domain.references import format_reference, load_reference_store, parse_reference_keys
from si_generator.input_table import read_compounds
from si_generator.models import Compound
from si_generator.render.document_model import build_si_document_model
from si_generator.workflows.generate_si import request_from_args


class ReferenceTests(unittest.TestCase):
    def test_loads_reference_store_and_formats_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            references_path = Path(tmp) / "references.yml"
            references_path.write_text(
                "references:\n"
                "  data_automation:\n"
                "    authors: [Doe J., Smith A.]\n"
                "    title: Automation in chemistry\n"
                "    journal: J. Chem. Inf. Model.\n"
                "    year: 2024\n"
                "    volume: 64\n"
                "    pages: 1-5\n"
                "    doi: 10.0000/example\n"
                "order: [data_automation]\n",
                encoding="utf-8",
            )

            store = load_reference_store(references_path)

        reference = store["references"]["data_automation"]
        self.assertEqual(store["order"], ["data_automation"])
        self.assertEqual(reference["authors"], ["Doe J.", "Smith A."])
        self.assertEqual(
            format_reference(reference, 1),
            "[1] Doe J., Smith A. Automation in chemistry. J. Chem. Inf. Model., 2024, 64, 1-5. DOI: 10.0000/example.",
        )

    def test_csv_reference_aliases_are_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.csv"
            input_path.write_text("number,name,refs\n2a,Compound A,ref1; ref2\n", encoding="utf-8")

            compounds = read_compounds(input_path)

        self.assertEqual(compounds[0].references, ["ref1", "ref2"])
        self.assertEqual(compounds[0].source_row, 2)

    def test_csv_missing_name_column_reaches_validation_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.csv"
            input_path.write_text("number,refs\n2a,ref1\n", encoding="utf-8")

            compounds = read_compounds(input_path)

        self.assertEqual(compounds[0].name, "")
        self.assertEqual(compounds[0].references, ["ref1"])

    def test_document_model_and_docx_include_references(self) -> None:
        compound = Compound(id="cmp_001", number="2a", name="Example", references=["ref1"])
        store = {
            "references": {
                "ref1": {
                    "key": "ref1",
                    "authors": ["Doe J."],
                    "title": "Helpful chemistry data",
                    "journal": "Chem. Data",
                    "year": 2025,
                }
            },
            "order": ["ref1"],
        }

        model = build_si_document_model([compound], reference_store=store)

        self.assertEqual([section["id"] for section in model["sections"]], ["compound_descriptions", "references"])
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            build_document_from_model(model, output_path)
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("References", text)
        self.assertIn("Helpful chemistry data", text)

    def test_cli_args_accept_references_file(self) -> None:
        args = Namespace(
            word_input="input.docx",
            input=None,
            output="out.docx",
            template_docx=None,
            references="references.yml",
            spectra_zip=None,
            mnova_exe=None,
            no_extract_nmr=True,
            extract_structure_metadata=False,
            only="",
            insert_chemdraw=False,
            no_check_support=True,
        )

        request = request_from_args(args)

        self.assertEqual(request.references_path, Path("references.yml"))

    def test_parse_reference_keys_accepts_common_delimiters(self) -> None:
        self.assertEqual(parse_reference_keys("ref1, ref2;ref3"), ["ref1", "ref2", "ref3"])


if __name__ == "__main__":
    unittest.main()
