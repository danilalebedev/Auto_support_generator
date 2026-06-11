from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from docx import Document

from si_generator.cli import main as cli_main
from si_generator.docx_builder import build_document_from_model
from si_generator.domain.bookmarks import bookmark_name_for_block_id
from si_generator.domain.manifest import check_manifest, manifest_has_errors
from si_generator.domain.patching import parse_renumber_map
from si_generator.graph.state import PatchSIRequest
from si_generator.models import Compound
from si_generator.render.document_model import build_si_document_model
from si_generator.workflows.patch_si import run_patch_si


class PatchWorkflowTests(unittest.TestCase):
    def test_parse_renumber_map_accepts_comma_separated_pairs(self) -> None:
        self.assertEqual(parse_renumber_map("2a=3a, cmp_002=3b"), {"2a": "3a", "cmp_002": "3b"})

    def test_parse_renumber_map_rejects_invalid_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "OLD=NEW"):
            parse_renumber_map("2a")

    def test_patch_workflow_renumbers_docx_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_docx, source_manifest = _write_source_support(root)
            patched_docx = root / "support_information_renumbered.docx"
            patched_manifest = root / "support_information_renumbered.manifest.json"

            state = run_patch_si(
                PatchSIRequest(
                    manifest_path=source_manifest,
                    renumber={"2a": "5a"},
                    output_docx=patched_docx,
                    output_manifest=patched_manifest,
                )
            )

            patched = json.loads(patched_manifest.read_text(encoding="utf-8"))
            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)
            issues = check_manifest(patched, manifest_path=patched_manifest)
            patched_docx_exists = patched_docx.exists()
            patched_manifest_exists = patched_manifest.exists()

        self.assertEqual(state["status"], "pass")
        self.assertTrue(patched_docx_exists)
        self.assertTrue(patched_manifest_exists)
        self.assertEqual(patched["compounds"]["cmp_001"]["number"], "5a")
        self.assertIn("Example (5a)", text)
        self.assertNotIn("Example (2a)", text)
        self.assertFalse(manifest_has_errors(issues))

    def test_cli_patch_manifest_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_manifest = _write_source_support(root)
            patched_docx = root / "patched.docx"
            stdout = StringIO()

            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(
                    [
                        "--patch-manifest",
                        str(source_manifest),
                        "--renumber",
                        "2a=6a",
                        "--patched-output",
                        str(patched_docx),
                    ]
                )

            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)

        self.assertEqual(exit_code, 0)
        self.assertIn("Patch check passed", stdout.getvalue())
        self.assertIn("Example (6a)", text)


def _write_source_support(root: Path) -> tuple[Path, Path]:
    source_docx = root / "support_information.docx"
    source_manifest = root / "support_information.manifest.json"
    compound = Compound(id="cmp_001", number="2a", name="Example")
    build_document_from_model(build_si_document_model([compound]), source_docx)
    manifest = {
        "run_id": "run",
        "artifacts": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
        "output_paths": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
        "order": ["cmp_001"],
        "compounds": {
            "cmp_001": {
                "id": "cmp_001",
                "number": "2a",
                "source_row": 2,
                "structure_placeholder": "STRUCTURE:2a",
                "docx_block_id": "compound:cmp_001",
                "docx_bookmark": bookmark_name_for_block_id("compound:cmp_001"),
                "artifacts": {},
            }
        },
    }
    source_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return source_docx, source_manifest


if __name__ == "__main__":
    unittest.main()
