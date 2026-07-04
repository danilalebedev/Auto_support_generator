from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.domain.bookmarks import bookmark_name_for_block_id
from si_generator.domain.requests import AddCompoundsRequest
from si_generator.graph.nodes.add_compounds import _append_generated_docx_blocks, _new_compound_id_map
from si_generator.domain.compound import Compound
from si_generator.render.document_model import build_si_document_model
from si_generator.workflows.add_compounds import run_add_compounds


class AddCompoundsWorkflowTests(unittest.TestCase):
    def test_duplicate_compound_number_blocks_before_output_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = _write_manifest(root, number="2a")
            new_table = root / "new_compounds.csv"
            new_table.write_text("number,name\n2a,Duplicate\n", encoding="utf-8")
            output_docx = root / "patched_support.docx"

            state = run_add_compounds(
                AddCompoundsRequest(
                    manifest_path=manifest_path,
                    input_path=new_table,
                    input_kind="csv",
                    output_docx=output_docx,
                )
            )
            report = json.loads(output_docx.with_suffix(".add_report.json").read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "fail")
        self.assertIn("DUPLICATE_COMPOUND_NUMBER", {issue["code"] for issue in state["issues"]})
        self.assertEqual(state["add_result"]["duplicate_numbers"], ["2a"])
        self.assertFalse(output_docx.exists())
        self.assertNotIn("generated_support_docx", state.get("artifacts", {}))
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["add_result"]["duplicate_numbers"], ["2a"])

    def test_non_duplicate_adds_docx_blocks_and_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = _write_manifest(root, number="2a", valid_docx=True)
            new_table = root / "new_compounds.csv"
            new_table.write_text("number,name,color,state\n2b,Added,white,solid\n", encoding="utf-8")
            output_docx = root / "patched_support.docx"

            state = run_add_compounds(
                AddCompoundsRequest(
                    manifest_path=manifest_path,
                    input_path=new_table,
                    input_kind="csv",
                    output_docx=output_docx,
                    no_extract_nmr=True,
                    no_check_support=True,
                )
            )
            merged_manifest = json.loads(output_docx.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            report = json.loads(output_docx.with_suffix(".add_report.json").read_text(encoding="utf-8"))
            text = "\n".join(paragraph.text for paragraph in Document(output_docx).paragraphs)
            output_exists = output_docx.exists()
            document_xml = _docx_text(output_docx, "word/document.xml")

        self.assertEqual(state["status"], "pass")
        self.assertTrue(output_exists)
        self.assertEqual([merged_manifest["compounds"][compound_id]["number"] for compound_id in merged_manifest["order"]], ["2a", "2b"])
        self.assertIn("Existing compound (2a)", text)
        self.assertIn("Added (2b)", text)
        self.assertTrue(merged_manifest["compounds"]["added_cmp_001_1"]["docx_bookmark"])
        self.assertIn(merged_manifest["compounds"]["added_cmp_001_1"]["docx_bookmark"], document_xml)
        self.assertEqual(report["status"], "pass")
        self.assertNotIn("ADD_COMPOUNDS_TEXT_ONLY_MERGE", {issue["code"] for issue in report["issues"]})

    def test_docx_block_merge_preserves_media_and_remaps_bookmarks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "spectrum.png"
            image_path.write_bytes(_tiny_png())
            old_docx = root / "old.docx"
            new_docx = root / "new.docx"
            output_docx = root / "merged.docx"

            old_manifest = _build_support_docx_and_manifest(old_docx, Compound(id="cmp_001", number="2a", name="Existing"))
            new_manifest = _build_support_docx_and_manifest(
                new_docx,
                Compound(
                    id="cmp_001",
                    number="2b",
                    name="Added",
                    h1_spectrum_path="fid",
                    h1_image_path=str(image_path),
                ),
                spectra_embed_mode="png",
            )
            id_map = _new_compound_id_map(old_manifest, new_manifest)

            _append_generated_docx_blocks(old_docx, new_docx, output_docx, old_manifest=old_manifest, new_manifest=new_manifest, id_map=id_map)

            document_xml = _docx_text(output_docx, "word/document.xml")
            rels_xml = _docx_text(output_docx, "word/_rels/document.xml.rels")
            with ZipFile(output_docx) as archive:
                media_files = [name for name in archive.namelist() if name.startswith("word/media/")]

        added_id = "added_cmp_001_1"
        self.assertEqual(id_map, {"cmp_001": added_id})
        self.assertIn(bookmark_name_for_block_id("compound:cmp_001"), document_xml)
        self.assertIn(bookmark_name_for_block_id(f"compound:{added_id}"), document_xml)
        self.assertIn(bookmark_name_for_block_id(f"spectrum:{added_id}:1H"), document_xml)
        self.assertIn("Added", document_xml)
        self.assertIn("add_compounds_1.png", rels_xml)
        self.assertIn("word/media/add_compounds_1.png", media_files)


def _write_manifest(root: Path, *, number: str, valid_docx: bool = False) -> Path:
    support_docx = root / "support_information.docx"
    if valid_docx:
        _build_support_docx_and_manifest(support_docx, Compound(id="cmp_001", number=number, name="Existing compound"))
    else:
        support_docx.write_bytes(b"placeholder")
    manifest_path = root / "support_information.manifest.json"
    manifest = {
        "run_id": "run",
        "artifacts": {"support_docx": str(support_docx), "manifest": str(manifest_path)},
        "output_paths": {"support_docx": str(support_docx), "manifest": str(manifest_path)},
        "order": ["cmp_001"],
        "compounds": {
            "cmp_001": {
                "id": "cmp_001",
                "number": number,
                "docx_block_id": "compound:cmp_001",
                "docx_bookmark": bookmark_name_for_block_id("compound:cmp_001"),
            }
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _build_support_docx_and_manifest(docx_path: Path, compound: Compound, *, spectra_embed_mode: str = "none") -> dict:
    model = build_si_document_model([compound], spectra_embed_mode=spectra_embed_mode)
    build_document_from_model(model, docx_path)
    compound_id = compound.id or "cmp_001"
    return {
        "run_id": "run",
        "artifacts": {"support_docx": str(docx_path)},
        "output_paths": {"support_docx": str(docx_path)},
        "order": [compound_id],
        "compounds": {
            compound_id: {
                "id": compound_id,
                "number": compound.number,
                "docx_block_id": f"compound:{compound_id}",
                "docx_bookmark": bookmark_name_for_block_id(f"compound:{compound_id}"),
                "artifacts": {"h1_png": compound.h1_image_path} if compound.h1_image_path else {},
            }
        },
    }


def _docx_text(docx_path: Path, member: str) -> str:
    with ZipFile(docx_path) as archive:
        return archive.read(member).decode("utf-8")


def _tiny_png() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


if __name__ == "__main__":
    unittest.main()
