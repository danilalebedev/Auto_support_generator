from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.graph.state import GenerateSIRequest
from si_generator.graph.nodes.settings import load_settings_node
from si_generator.gui import _build_generate_request
from si_generator.models import Compound
from si_generator.render.document_model import build_si_document_model
from si_generator.workflows.generate_si import request_from_args


class SpectrumEmbedModeTests(unittest.TestCase):
    def test_document_model_omits_spectra_appendix_for_none_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "2a_1H.png"
            image.write_bytes(_tiny_png())
            compound = Compound(id="cmp_001", number="2a", name="Example", h1_image_path=str(image))

            model = build_si_document_model([compound], spectra_embed_mode="none")

        self.assertEqual([section["id"] for section in model["sections"]], ["compound_descriptions"])
        self.assertEqual(model["metadata"]["spectrum_count"], "0")

    def test_document_model_uses_mnova_blocks_with_page_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mnova = Path(tmp) / "2a.mnova"
            image = Path(tmp) / "2a_1H.png"
            mnova.write_bytes(b"mnova")
            image.write_bytes(_tiny_png())
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Example",
                h1_spectrum_path="fid",
                mnova_path=str(mnova),
                h1_image_path=str(image),
            )

            model = build_si_document_model([compound], spectra_embed_mode="mnova")

        spectra = next(section for section in model["sections"] if section["id"] == "spectra_appendix")
        self.assertEqual(len(spectra["blocks"]), 1)
        self.assertEqual(spectra["blocks"][0]["embed_mode"], "mnova")
        self.assertEqual(spectra["blocks"][0]["mnova_path"], str(mnova))

    def test_docx_renderer_writes_mnova_page_image_without_mnova_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "2a_1H.png"
            image.write_bytes(_tiny_png())
            mnova = root / "2a.mnova"
            mnova.write_bytes(b"mnova")
            output = root / "support_information.docx"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Example",
                h1_image_path=str(image),
                h1_spectrum_path="fid",
                mnova_path=str(mnova),
            )

            model = build_si_document_model([compound], spectra_embed_mode="mnova")
            build_document_from_model(model, output)
            text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
            with ZipFile(output) as archive:
                media_files = [name for name in archive.namelist() if name.startswith("word/media/")]
                embeddings = [name for name in archive.namelist() if name.startswith("word/embeddings/")]
                document_xml = archive.read("word/document.xml").decode("utf-8")

        self.assertNotIn("[[MNOVA_PAGE:2a:1H]]", text)
        self.assertIn("[[SPECTRUM_STRUCTURE:2a:1H]]", text)
        self.assertEqual(len(media_files), 1)
        self.assertEqual(embeddings, [])
        self.assertNotIn("[[MNOVA_PAGE:2a:1H]]", document_xml)

    def test_request_and_settings_carry_insert_spectra_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "input.docx"
            table.write_text("placeholder", encoding="utf-8")
            output = Path(tmp) / "support_information.docx"

            request = _build_generate_request(
                input_kind="word",
                input_path_text=str(table),
                output_docx_text=str(output),
                insert_spectra_as="mnova",
            )

        self.assertEqual(request.insert_spectra_as, "mnova")
        state = load_settings_node({"request": request, "run_id": "run", "artifacts": {}, "issues": []})
        self.assertEqual(state["spectra_config"]["insert_spectra_as"], "mnova")

    def test_cli_args_accept_insert_spectra_mode(self) -> None:
        args = Namespace(
            word_input="input.docx",
            input=None,
            output="out.docx",
            template_docx=None,
            references=None,
            spectra_zip=None,
            mnova_exe=None,
            no_extract_nmr=True,
            insert_spectra_as="mnova",
            peak_threshold=None,
            peak_threshold_1h=6,
            peak_threshold_13c=4,
            extract_structure_metadata=False,
            only="",
            insert_chemdraw=False,
            no_check_support=True,
        )

        request = request_from_args(args)

        self.assertIsInstance(request, GenerateSIRequest)
        self.assertEqual(request.insert_spectra_as, "mnova")
        self.assertEqual(request.peak_threshold_fraction_1h, 0.06)
        self.assertEqual(request.peak_threshold_fraction_13c, 0.04)


def _tiny_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


if __name__ == "__main__":
    unittest.main()
