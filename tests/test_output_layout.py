from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.output_layout import (
    LEGACY_GENERATED_DIRS,
    LEGACY_GENERATED_FILES,
    cleanup_legacy_output_root,
    create_run_output_root,
    prepare_output_layout,
    run_output_dirs,
)


class OutputLayoutTests(unittest.TestCase):
    def test_create_run_output_root_uses_unique_per_run_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "test input.docx"
            input_path.write_text("input", encoding="utf-8")
            requested_output = root / "output" / "support_information.docx"

            first = create_run_output_root(input_path, requested_output, "20260704T120000")
            first.mkdir(parents=True)
            second = create_run_output_root(input_path, requested_output, "20260704T120000")

        self.assertEqual(first.name, "20260704_120000_test_input")
        self.assertEqual(second.name, "20260704_120000_test_input_2")
        self.assertEqual(first.parent.name, "runs")

    def test_cleanup_legacy_output_root_deletes_only_known_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_file = root / "notes.docx"
            user_dir_file = root / "custom" / "keep.txt"
            generated_files = [root / name for name in LEGACY_GENERATED_FILES]
            generated_dirs = [root / name for name in LEGACY_GENERATED_DIRS]
            for path in generated_files:
                path.write_text("old", encoding="utf-8")
            for path in generated_dirs:
                path.mkdir()
                (path / "generated.txt").write_text("old", encoding="utf-8")
            user_file.write_text("keep", encoding="utf-8")
            user_dir_file.parent.mkdir()
            user_dir_file.write_text("keep", encoding="utf-8")

            cleanup_legacy_output_root(root)

            self.assertTrue(all(not path.exists() for path in generated_files))
            self.assertTrue(all(not path.exists() for path in generated_dirs))
            self.assertTrue(user_file.exists())
            self.assertTrue(user_dir_file.exists())

    def test_prepare_output_layout_returns_run_docx_and_standard_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.docx"
            input_path.write_text("input", encoding="utf-8")
            dirs = prepare_output_layout(
                root / "output" / "support_information.docx",
                input_path=input_path,
                run_id="20260704T120000",
            )

            support = dirs["support_docx"]
            logs_exists = dirs["logs_dir"].exists()
            self.assertEqual(support.parent.name, "docx")
            self.assertEqual(support.name, "support_information.docx")
            self.assertEqual(dirs["output_root"].name, "20260704_120000_input")
            self.assertEqual(dirs["output_root"].parent.name, "runs")
            self.assertTrue(dirs["docx_dir"].is_dir())
            self.assertTrue(dirs["input_dir"].is_dir())
            self.assertTrue(dirs["spectra_dir"].is_dir())
            self.assertTrue(dirs["mnova_dir"].is_dir())
            self.assertTrue(dirs["logs_dir"].is_dir())
            self.assertTrue(dirs["reports_dir"].is_dir())
            self.assertEqual(dirs["input_dir"].parent, dirs["output_root"])
            self.assertEqual(dirs["reports_dir"].parent, dirs["output_root"])
            self.assertTrue(logs_exists)

    def test_run_output_dirs_returns_standard_dirs_for_existing_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp) / "runs" / "20260704_120000_input"

            dirs = run_output_dirs(run_root)

            self.assertEqual(dirs["output_root"], run_root)
            self.assertEqual(dirs["docx_dir"], run_root / "docx")
            self.assertEqual(dirs["input_dir"], run_root / "input")
            self.assertEqual(dirs["spectra_dir"], run_root / "spectra")
            self.assertEqual(dirs["processed_mnova_dir"], run_root / "mnova" / "processed")
            self.assertEqual(dirs["mnova_reports_dir"], run_root / "logs" / "mnova_reports")


if __name__ == "__main__":
    unittest.main()
