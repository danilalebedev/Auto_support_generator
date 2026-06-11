from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from si_generator.chemistry import calc_hrms_mz
from si_generator.docx_builder import build_document_from_model
from si_generator.domain.bookmarks import bookmark_name_for_block_id
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
        compound_block = model["sections"][0]["blocks"][0]
        spectrum_block = model["sections"][1]["blocks"][0]
        self.assertEqual(compound_block["kind"], "compound_description")
        self.assertEqual(compound_block["block_id"], "compound:cmp_001")
        self.assertEqual(compound_block["bookmark"], bookmark_name_for_block_id("compound:cmp_001"))
        self.assertEqual(compound_block["display_number"], "2a")
        self.assertEqual(compound_block["title_text"], "Example (2a)")
        self.assertEqual(compound_block["structure_placeholder"], "STRUCTURE:2a")
        self.assertEqual(spectrum_block["kind"], "spectrum_page")
        self.assertEqual(spectrum_block["block_id"], "spectrum:cmp_001:1H")
        self.assertEqual(spectrum_block["bookmark"], bookmark_name_for_block_id("spectrum:cmp_001:1H"))
        self.assertEqual(spectrum_block["compound_id"], "cmp_001")
        self.assertEqual(spectrum_block["nucleus"], "1H")
        self.assertEqual(spectrum_block["structure_placeholder"], "SPECTRUM_STRUCTURE:2a:1H")
        self.assertEqual(spectrum_block["expected_artifact_path"], str(image_path))
        self.assertEqual(model["metadata"]["spectrum_count"], "1")
        self.assertEqual(model["metadata"]["references_count"], "0")

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

    def test_renders_docx_bookmarks_for_patch_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(id="cmp_001", number="2a", name="Example compound", color="white", state="solid")
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            with zipfile.ZipFile(output_path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
            visible_text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn('w:bookmarkStart', document_xml)
        self.assertIn(f'w:name="{bookmark_name_for_block_id("compound:cmp_001")}"', document_xml)
        self.assertLess(document_xml.index('w:bookmarkStart'), document_xml.index("Example compound"))
        self.assertLess(document_xml.index("white solid."), document_xml.index('w:bookmarkEnd'))
        self.assertNotIn("asig_compound", visible_text)

    def test_renders_hrms_isotope_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Bromide example",
                formula="C11H10BrFO2",
                hrms_found="272.9921",
                hrms_adduct="[M+H]+",
            )
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("79Br", text)
        self.assertIn("272.9921", text)

    def test_renders_hrms_from_structured_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            found = f"{calc_hrms_mz('C2H4O2', '[M+Na]+'):.4f}"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Sodium adduct example",
                formula="C2H4O2",
                hrms={"adduct": "[M+Na]+", "found_text": found},
            )
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("[M+Na]+", text)
        self.assertIn("C2H4O2Na+", text)
        self.assertIn(found, text)

    def test_renders_elemental_analysis_in_journal_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Analysis example",
                formula="C17H11FN2O3",
                elemental_analysis={"found": "C, 66.03; H, 3.55; N, 8.92"},
            )
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("Anal. Calcd for C17H11FN2O3: C, 65.81; H, 3.57; N, 9.03. Found: C, 66.03; H, 3.55; N, 8.92.", text)

    def test_renders_ir_method_from_input_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="IR example",
                ir="IR (ATR, cm-1): 3038, 2957, 1711.",
            )
            model = build_si_document_model([compound])

            build_document_from_model(model, output_path)

            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("IR (ATR, cm-1): 3038, 2957, 1711.", text)
        self.assertNotIn("IR (KBr, cm-1): IR", text)


if __name__ == "__main__":
    unittest.main()
