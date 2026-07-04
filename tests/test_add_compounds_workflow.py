from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from si_generator.domain.bookmarks import bookmark_name_for_block_id
from si_generator.domain.requests import AddCompoundsRequest
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

    def test_non_duplicate_adds_text_block_and_manifest_entry(self) -> None:
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

        self.assertEqual(state["status"], "pass")
        self.assertTrue(output_exists)
        self.assertEqual([merged_manifest["compounds"][compound_id]["number"] for compound_id in merged_manifest["order"]], ["2a", "2b"])
        self.assertIn("Existing compound (2a)", text)
        self.assertIn("Added (2b)", text)
        self.assertEqual(report["status"], "pass")
        self.assertIn("ADD_COMPOUNDS_TEXT_ONLY_MERGE", {issue["code"] for issue in report["issues"]})


def _write_manifest(root: Path, *, number: str, valid_docx: bool = False) -> Path:
    support_docx = root / "support_information.docx"
    if valid_docx:
        document = Document()
        document.add_paragraph(f"Existing compound ({number})")
        document.save(support_docx)
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


if __name__ == "__main__":
    unittest.main()
