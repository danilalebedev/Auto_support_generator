from __future__ import annotations

import tempfile
import unittest
import sys
from argparse import Namespace
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.graph.state import GenerateSIRequest
from si_generator.graph.nodes.settings import load_settings_node
from si_generator.gui import _build_generate_request
from si_generator.domain.compound import Compound
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

    def test_document_model_uses_nucleus_specific_mnova_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            h1_image = root / "2a_1H.png"
            c13_image = root / "2a_13C.png"
            h1_mnova = root / "2a_1H.mnova"
            c13_mnova = root / "2a_13C.mnova"
            combined_mnova = root / "2a.mnova"
            for path in [h1_image, c13_image]:
                path.write_bytes(_tiny_png())
            for path in [h1_mnova, c13_mnova, combined_mnova]:
                path.write_bytes(b"mnova")
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Example",
                h1_spectrum_path="h1/fid",
                c13_spectrum_path="c13/fid",
                h1_image_path=str(h1_image),
                c13_image_path=str(c13_image),
                h1_mnova_path=str(h1_mnova),
                c13_mnova_path=str(c13_mnova),
                mnova_path=str(combined_mnova),
            )

            model = build_si_document_model([compound], spectra_embed_mode="mnova")

        spectra = next(section for section in model["sections"] if section["id"] == "spectra_appendix")
        paths_by_nucleus = {block["nucleus"]: block["mnova_path"] for block in spectra["blocks"]}
        self.assertEqual(paths_by_nucleus, {"1H": str(h1_mnova), "13C": str(c13_mnova)})

    @unittest.skipIf(sys.platform != "win32", "Mnova OLE storage generation uses Windows COM storage APIs")
    def test_docx_renderer_writes_native_mnova_ole_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "2a_1H.png"
            image.write_bytes(_tiny_png())
            mnova = root / "2a.mnova"
            mnova.write_bytes(b"mnova-native-content")
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
                ole_bytes = archive.read(embeddings[0])

        self.assertNotIn("[[MNOVA_PAGE:2a:1H]]", text)
        self.assertNotIn("[[MNOVA_OLE:", text)
        self.assertIn("[[SPECTRUM_STRUCTURE:2a:1H]]", text)
        self.assertEqual(len(media_files), 1)
        self.assertEqual(len(embeddings), 1)
        self.assertIn('ProgID="MestReNova.Document.1"', document_xml)
        self.assertNotIn("[[MNOVA_PAGE:2a:1H]]", document_xml)
        self.assertNotIn("[[MNOVA_OLE:", document_xml)
        self.assertTrue(_mnova_ole_storage_is_native(ole_bytes))

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
            h1_ppm_range=[-0.5, 11.5],
            c13_ppm_range=[205, -5],
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
        self.assertEqual(request.x_range_ppm_1h, (-0.5, 11.5))
        self.assertEqual(request.x_range_ppm_13c, (-5.0, 205.0))


def _tiny_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _mnova_ole_storage_is_native(data: bytes) -> bool:
    import olefile

    with tempfile.TemporaryDirectory() as tmp:
        ole_path = Path(tmp) / "oleObject.bin"
        ole_path.write_bytes(data)
        ole = olefile.OleFileIO(ole_path)
        try:
            return (
                str(ole.root.clsid).lower() == "24279019-4929-4f35-a663-68eb78a1d139"
                and ole.exists("MNOVA-CONTENTS")
                and ole.openstream("MNOVA-CONTENTS").read() == b"mnova-native-content"
                and not ole.exists("\x01Ole10Native")
            )
        finally:
            ole.close()


if __name__ == "__main__":
    unittest.main()
