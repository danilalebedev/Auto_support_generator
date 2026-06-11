from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from si_generator.cli import main as cli_main
from si_generator.domain.manifest import check_manifest, manifest_has_errors
from si_generator.graph.state import CheckSIRequest
from si_generator.workflows.check_si import run_check_si


class CheckWorkflowTests(unittest.TestCase):
    def test_manifest_check_passes_for_valid_generated_manifest_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support_docx = root / "support_information.docx"
            support_docx.write_bytes(b"docx placeholder")
            manifest_path = root / "support_information.manifest.json"
            manifest = {
                "run_id": "run",
                "artifacts": {"support_docx": str(support_docx), "manifest": str(manifest_path)},
                "order": ["cmp_001"],
                "compounds": {
                    "cmp_001": {
                        "id": "cmp_001",
                        "number": "2a",
                        "docx_block_id": "compound:cmp_001",
                        "artifacts": {},
                    }
                },
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            state = run_check_si(CheckSIRequest(manifest_path=manifest_path))

        self.assertEqual(state["status"], "pass")
        self.assertFalse(manifest_has_errors(state["issues"]))

    def test_manifest_check_reports_missing_docx_and_broken_compound_entry(self) -> None:
        manifest = {
            "run_id": "run",
            "artifacts": {"support_docx": "missing.docx"},
            "order": ["cmp_001"],
            "compounds": {"cmp_001": {"id": "cmp_001", "number": "2a"}},
        }

        issues = check_manifest(manifest, manifest_path="C:/tmp/support_information.manifest.json")

        self.assertTrue(manifest_has_errors(issues))
        self.assertIn("MANIFEST_MISSING_SUPPORT_DOCX", {issue["code"] for issue in issues})
        self.assertIn("MANIFEST_MISSING_COMPOUND_FIELD", {issue["code"] for issue in issues})

    def test_cli_check_manifest_mode_returns_zero_on_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support_docx = root / "support_information.docx"
            support_docx.write_bytes(b"docx placeholder")
            manifest_path = root / "support_information.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "run",
                        "artifacts": {"support_docx": str(support_docx), "manifest": str(manifest_path)},
                        "order": [],
                        "compounds": {},
                    }
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(["--check-manifest", str(manifest_path)])

        self.assertEqual(exit_code, 0)
        self.assertIn("Manifest check passed", stdout.getvalue())

    def test_cli_check_manifest_mode_returns_nonzero_on_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "support_information.manifest.json"
            manifest_path.write_text(json.dumps({"run_id": "run", "order": [], "compounds": {}}), encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(["--check-manifest", str(manifest_path)])

        self.assertEqual(exit_code, 1)
        self.assertIn("MANIFEST_MISSING_SUPPORT_DOCX", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
