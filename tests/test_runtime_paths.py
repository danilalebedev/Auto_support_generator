from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.runtime_paths import app_base_dir, bundled_resource_path, default_output_path, gui_settings_path, local_app_data_dir


class RuntimePathsTests(unittest.TestCase):
    def test_app_base_dir_uses_repo_root_for_source_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_file = root / "src" / "si_generator" / "runtime_paths.py"
            package_file.parent.mkdir(parents=True)
            package_file.write_text("placeholder", encoding="utf-8")

            base_dir = app_base_dir(package_file=package_file, frozen=False)

        self.assertEqual(base_dir, root.resolve())

    def test_app_base_dir_uses_executable_parent_when_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "AutoSupportGenerator.exe"

            base_dir = app_base_dir(frozen=True, executable=exe)

        self.assertEqual(base_dir, exe.resolve().parent)

    def test_bundled_resource_path_prefers_pyinstaller_bundle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"

            path = bundled_resource_path("scripts/extract_nmr_report.qs", bundle_root=bundle)

        self.assertEqual(path, bundle / "scripts" / "extract_nmr_report.qs")

    def test_bundled_resource_path_falls_back_to_package_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_file = root / "src" / "si_generator" / "runtime_paths.py"
            resource = root / "src" / "si_generator" / "resources" / "scripts" / "extract_nmr_report.qs"
            package_file.parent.mkdir(parents=True)
            resource.parent.mkdir(parents=True)
            package_file.write_text("placeholder", encoding="utf-8")
            resource.write_text("script", encoding="utf-8")

            path = bundled_resource_path("scripts/extract_nmr_report.qs", package_file=package_file)

        self.assertEqual(path, resource.resolve())

    def test_local_app_data_paths_use_app_folder(self) -> None:
        env = {"LOCALAPPDATA": "C:/Users/test/AppData/Local"}

        self.assertEqual(local_app_data_dir(environ=env), Path("C:/Users/test/AppData/Local") / "AutoSupportGenerator")
        self.assertEqual(gui_settings_path(environ=env), Path("C:/Users/test/AppData/Local") / "AutoSupportGenerator" / "gui_settings.json")
        self.assertEqual(
            default_output_path(frozen=True, environ=env),
            Path("C:/Users/test/AppData/Local") / "AutoSupportGenerator" / "output" / "docx" / "support_information.docx",
        )


if __name__ == "__main__":
    unittest.main()
