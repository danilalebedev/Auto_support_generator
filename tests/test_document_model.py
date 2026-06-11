from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.models import Compound
from si_generator.render.document_model import build_si_document_model


class DocumentModelTests(unittest.TestCase):
    def test_builds_compound_and_spectrum_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "2a_1H.png"
            image_path.write_bytes(b"not-a-real-image-for-model-only")
            compound = Compound(id="cmp_001", number="2a", name="Example", h1_image_path=str(image_path))

            model = build_si_document_model([compound])

        self.assertEqual(model["title"], "Supporting Information")
        self.assertEqual([section["id"] for section in model["sections"]], ["compound_descriptions", "spectra_appendix"])
        self.assertEqual(model["sections"][0]["blocks"][0]["kind"], "compound_description")
        self.assertEqual(model["sections"][1]["blocks"][0]["kind"], "spectrum_page")
        self.assertEqual(model["sections"][1]["blocks"][0]["compound_id"], "cmp_001")
        self.assertEqual(model["sections"][1]["blocks"][0]["nucleus"], "1H")

    def test_renders_docx_from_document_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(id="cmp_001", number="2a", name="Example compound", color="white", state="solid")
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("Example compound", text)
        self.assertIn("(2a)", text)
        self.assertIn("white solid.", text)


if __name__ == "__main__":
    unittest.main()
