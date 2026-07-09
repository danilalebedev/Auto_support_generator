from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.domain.compound import Compound
from si_generator.render.document_model import build_si_document_model


class TemplateRendererTests(unittest.TestCase):
    def test_replaces_split_placeholder_and_preserves_template_run_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "template.docx"
            output = root / "support.docx"
            document = Document()
            paragraph = document.add_paragraph("Name ")
            paragraph.add_run("{").italic = True
            paragraph.add_run("compound.name").italic = True
            paragraph.add_run("}").italic = True
            document.save(template)

            compound = Compound(id="cmp_001", number="2a", name="Example compound")
            model = build_si_document_model([compound], spectra_embed_mode="none")
            build_document_from_model(model, output, template_path=template)
            rendered = Document(output)

        self.assertEqual(rendered.paragraphs[0].text, "Name Example compound")
        replacement_runs = [run for run in rendered.paragraphs[0].runs if "Example compound" in run.text]
        self.assertEqual(len(replacement_runs), 1)
        self.assertTrue(replacement_runs[0].italic)

    def test_new_spectrum_picture_alias_renders_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "2a_1H.png"
            image.write_bytes(_tiny_png())
            template = root / "template.docx"
            output = root / "support.docx"
            document = Document()
            document.add_paragraph("{compound.name} ({compound.number})")
            document.add_page_break()
            document.add_paragraph("{compound.name} ({compound.number})")
            document.add_paragraph("{compound.number.nmr.1h.picture}")
            document.save(template)

            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Example compound",
                h1_image_path=str(image),
                h1_spectrum_path="fid",
            )
            model = build_si_document_model([compound], spectra_embed_mode="png")
            build_document_from_model(model, output, template_path=template)
            text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
            with ZipFile(output) as archive:
                media_files = [name for name in archive.namelist() if name.startswith("word/media/")]

        self.assertNotIn("{compound.number.nmr.1h.picture}", text)
        self.assertEqual(len(media_files), 1)


def _tiny_png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGA"
        "WjR9awAAAABJRU5ErkJggg=="
    )


if __name__ == "__main__":
    unittest.main()
