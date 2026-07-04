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
from si_generator.domain.patching import parse_remove_list, parse_renumber_map, parse_reorder_list
from si_generator.graph.state import PatchSIRequest
from si_generator.domain.compound import Compound
from si_generator.render.document_model import build_si_document_model
from si_generator.workflows.patch_si import run_patch_si


class PatchWorkflowTests(unittest.TestCase):
    def test_parse_renumber_map_accepts_comma_separated_pairs(self) -> None:
        self.assertEqual(parse_renumber_map("2a=3a, cmp_002=3b"), {"2a": "3a", "cmp_002": "3b"})

    def test_parse_renumber_map_rejects_invalid_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "OLD=NEW"):
            parse_renumber_map("2a")

    def test_parse_reorder_list_accepts_numbers_or_ids(self) -> None:
        self.assertEqual(parse_reorder_list("2b, cmp_001"), ("2b", "cmp_001"))

    def test_parse_remove_list_accepts_numbers_or_ids(self) -> None:
        self.assertEqual(parse_remove_list("2a, cmp_002"), ("2a", "cmp_002"))

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
            patch_report = json.loads((root / "support_information_renumbered.patch_report.json").read_text(encoding="utf-8"))
            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)
            issues = check_manifest(patched, manifest_path=patched_manifest)
            patched_docx_exists = patched_docx.exists()
            patched_manifest_exists = patched_manifest.exists()

        self.assertEqual(state["status"], "pass")
        self.assertTrue(patched_docx_exists)
        self.assertTrue(patched_manifest_exists)
        self.assertEqual(Path(state["artifacts"]["patch_report"]), root / "support_information_renumbered.patch_report.json")
        self.assertEqual(patch_report["status"], "pass")
        self.assertEqual(patch_report["operations"]["renumber"], {"2a": "5a"})
        self.assertEqual(state["patch_result"]["renumbered"], {"2a": "5a"})
        self.assertEqual(patch_report["patch_result"]["renumbered"], {"2a": "5a"})
        self.assertEqual(patch_report["patch_result"]["removed_ids"], [])
        self.assertEqual(patch_report["patch_result"]["reordered_ids"], [])
        self.assertEqual(patch_report["compound_issue_counts"], {})
        self.assertEqual(len(patched["patch_history"]), 1)
        self.assertEqual(patched["patch_history"][0]["run_id"], state["run_id"])
        self.assertEqual(patched["patch_history"][0]["source_manifest"], str(source_manifest))
        self.assertEqual(patched["patch_history"][0]["output_manifest"], str(patched_manifest))
        self.assertEqual(patched["patch_history"][0]["output_docx"], str(patched_docx))
        self.assertEqual(patched["patch_history"][0]["operations"]["renumber"], {"2a": "5a"})
        self.assertEqual(patched["patch_history"][0]["result"]["renumbered"], {"2a": "5a"})
        self.assertEqual(patched["compounds"]["cmp_001"]["number"], "5a")
        self.assertEqual(patched["compounds"]["cmp_001"]["domain_snapshot"]["number"], "5a")
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
        self.assertIn("Patch report:", stdout.getvalue())
        self.assertIn("Example (6a)", text)

    def test_cli_patch_manifest_remove_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_manifest = _write_source_support(
                root,
                [
                    Compound(id="cmp_001", number="2a", name="Example A", color="white", state="solid"),
                    Compound(id="cmp_002", number="2b", name="Example B", color="yellow", state="solid"),
                ],
            )
            patched_docx = root / "patched_removed.docx"
            stdout = StringIO()

            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(
                    [
                        "--patch-manifest",
                        str(source_manifest),
                        "--remove",
                        "2a",
                        "--patched-output",
                        str(patched_docx),
                    ]
                )

            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)

        self.assertEqual(exit_code, 0)
        self.assertIn("Patch check passed", stdout.getvalue())
        self.assertNotIn("Example A (2a)", text)
        self.assertIn("Example B (2b)", text)

    def test_patch_workflow_writes_report_for_malformed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "support_information.manifest.json"
            manifest.write_text("{", encoding="utf-8")

            state = run_patch_si(PatchSIRequest(manifest_path=manifest, renumber={"2a": "3a"}))
            report_path = root / "support_information.patch_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(state["status"], "fail")
        self.assertEqual(Path(state["artifacts"]["patch_report"]), report_path)
        self.assertIn("MANIFEST_LOAD_FAILED", {issue["code"] for issue in state["issues"]})
        self.assertEqual(report["patch_result"]["renumbered"], {})

    def test_cli_patch_manifest_mode_returns_report_for_malformed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "support_information.manifest.json"
            manifest.write_text("{", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(["--patch-manifest", str(manifest), "--renumber", "2a=3a"])

        self.assertEqual(exit_code, 1)
        self.assertIn("MANIFEST_LOAD_FAILED", stdout.getvalue())
        self.assertIn("Patch report:", stdout.getvalue())

    def test_patch_workflow_writes_report_when_docx_bookmark_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_docx = root / "support_information.docx"
            source_manifest = root / "support_information.manifest.json"
            patched_docx = root / "patched.docx"
            Document().save(source_docx)
            source_manifest.write_text(
                json.dumps(
                    {
                        "run_id": "run",
                        "artifacts": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
                        "output_paths": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
                        "order": ["cmp_001"],
                        "compounds": {
                            "cmp_001": {
                                "id": "cmp_001",
                                "number": "2a",
                                "docx_block_id": "compound:cmp_001",
                                "docx_bookmark": bookmark_name_for_block_id("compound:cmp_001"),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            state = run_patch_si(
                PatchSIRequest(
                    manifest_path=source_manifest,
                    renumber={},
                    remove=("2a",),
                    output_docx=patched_docx,
                )
            )
            report_path = root / "patched.patch_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            patched_docx_exists = patched_docx.exists()
            patched_manifest_exists = (root / "patched.manifest.json").exists()
            temp_outputs = [path.name for path in root.iterdir() if path.name.startswith(".patched")]

        self.assertEqual(state["status"], "fail")
        self.assertEqual(Path(state["artifacts"]["patch_report"]), report_path)
        self.assertIn("PATCH_APPLY_FAILED", {issue["code"] for issue in state["issues"]})
        self.assertIn("PATCH_APPLY_FAILED", {issue["code"] for issue in report["issues"]})
        self.assertFalse(patched_docx_exists)
        self.assertFalse(patched_manifest_exists)
        self.assertEqual(temp_outputs, [])

    def test_patch_workflow_reorders_docx_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_manifest = _write_source_support(
                root,
                [
                    Compound(id="cmp_001", number="2a", name="Example A", color="white", state="solid"),
                    Compound(id="cmp_002", number="2b", name="Example B", color="yellow", state="solid"),
                ],
            )
            patched_docx = root / "support_information_reordered.docx"
            patched_manifest = root / "support_information_reordered.manifest.json"

            state = run_patch_si(
                PatchSIRequest(
                    manifest_path=source_manifest,
                    renumber={},
                    reorder=("2b", "2a"),
                    output_docx=patched_docx,
                    output_manifest=patched_manifest,
                )
            )
            patched = json.loads(patched_manifest.read_text(encoding="utf-8"))
            patch_report = json.loads((root / "support_information_reordered.patch_report.json").read_text(encoding="utf-8"))
            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)

        self.assertEqual(state["status"], "pass")
        self.assertEqual(state["patch_result"]["reordered_ids"], ["cmp_002", "cmp_001"])
        self.assertEqual(patch_report["patch_result"]["reordered_ids"], ["cmp_002", "cmp_001"])
        self.assertEqual(patched["order"], ["cmp_002", "cmp_001"])
        self.assertLess(text.index("Example B (2b)"), text.index("Example A (2a)"))

    def test_patch_workflow_removes_docx_block_and_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, source_manifest = _write_source_support(
                root,
                [
                    Compound(id="cmp_001", number="2a", name="Example A", color="white", state="solid"),
                    Compound(id="cmp_002", number="2b", name="Example B", color="yellow", state="solid"),
                ],
            )
            patched_docx = root / "support_information_removed.docx"
            patched_manifest = root / "support_information_removed.manifest.json"

            state = run_patch_si(
                PatchSIRequest(
                    manifest_path=source_manifest,
                    renumber={},
                    remove=("2a",),
                    output_docx=patched_docx,
                    output_manifest=patched_manifest,
                )
            )
            patched = json.loads(patched_manifest.read_text(encoding="utf-8"))
            patch_report = json.loads((root / "support_information_removed.patch_report.json").read_text(encoding="utf-8"))
            text = "\n".join(paragraph.text for paragraph in Document(patched_docx).paragraphs)

        self.assertEqual(state["status"], "pass")
        self.assertEqual(state["patch_result"]["removed_ids"], ["cmp_001"])
        self.assertEqual(patch_report["patch_result"]["removed_ids"], ["cmp_001"])
        self.assertEqual(
            patch_report["patch_result"]["removed_bookmarks"],
            [bookmark_name_for_block_id("compound:cmp_001")],
        )
        self.assertEqual(patched["order"], ["cmp_002"])
        self.assertNotIn("cmp_001", patched["compounds"])
        self.assertNotIn("Example A (2a)", text)
        self.assertIn("Example B (2b)", text)


def _write_source_support(root: Path, compounds: list[Compound] | None = None) -> tuple[Path, Path]:
    source_docx = root / "support_information.docx"
    source_manifest = root / "support_information.manifest.json"
    compounds = compounds or [Compound(id="cmp_001", number="2a", name="Example")]
    build_document_from_model(build_si_document_model(compounds), source_docx)
    compound_entries = {}
    for index, compound in enumerate(compounds, start=2):
        compound_entries[compound.id] = {
            "id": compound.id,
            "number": compound.number,
            "domain_snapshot": compound.to_domain_dict(),
            "source_row": index,
            "structure_placeholder": f"STRUCTURE:{compound.number}",
            "docx_block_id": f"compound:{compound.id}",
            "docx_bookmark": bookmark_name_for_block_id(f"compound:{compound.id}"),
            "artifacts": {},
        }
    manifest = {
        "run_id": "run",
        "artifacts": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
        "output_paths": {"support_docx": str(source_docx), "manifest": str(source_manifest)},
        "order": [compound.id for compound in compounds],
        "compounds": compound_entries,
    }
    source_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return source_docx, source_manifest


if __name__ == "__main__":
    unittest.main()
