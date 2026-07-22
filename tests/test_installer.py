from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import auto_support_generator_installer as installer  # noqa: E402


def make_payload(root: Path, *, app_text: str = "app") -> Path:
    payload = root / "payload"
    payload.mkdir()
    for filename in installer.PAYLOAD_FILES:
        (payload / filename).write_text(app_text if filename == installer.APP_EXE_NAME else filename, encoding="utf-8")
    example = payload / "examples" / "example_1"
    example.mkdir(parents=True)
    (example / "Compound_table.docx").write_text("example", encoding="utf-8")
    docs = payload / "docs" / "assets"
    docs.mkdir(parents=True)
    (docs / "gui_overview.png").write_bytes(b"png")
    return payload


class InstallerTests(unittest.TestCase):
    def test_install_payload_preserves_user_data_and_replaces_managed_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = make_payload(root, app_text="v2")
            app_dir = root / "LocalAppData" / installer.INSTALL_DIR_NAME
            (app_dir / "output").mkdir(parents=True)
            (app_dir / "output" / "support_information.docx").write_text("keep", encoding="utf-8")
            (app_dir / "gui_settings.json").write_text("settings", encoding="utf-8")
            old_example = app_dir / "examples" / "old"
            old_example.mkdir(parents=True)
            (old_example / "stale.txt").write_text("stale", encoding="utf-8")

            with patch.object(installer, "_payload_root", return_value=payload):
                installer._install_payload(app_dir)

            self.assertEqual((app_dir / installer.APP_EXE_NAME).read_text(encoding="utf-8"), "v2")
            self.assertEqual((app_dir / "output" / "support_information.docx").read_text(encoding="utf-8"), "keep")
            self.assertEqual((app_dir / "gui_settings.json").read_text(encoding="utf-8"), "settings")
            self.assertFalse(old_example.exists())
            self.assertTrue((app_dir / "examples" / "example_1" / "Compound_table.docx").is_file())
            self.assertTrue((app_dir / "docs" / "assets" / "gui_overview.png").is_file())

    def test_install_payload_reports_missing_required_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = make_payload(root)
            (payload / installer.APP_EXE_NAME).unlink()

            with patch.object(installer, "_payload_root", return_value=payload):
                with self.assertRaisesRegex(RuntimeError, installer.APP_EXE_NAME):
                    installer._install_payload(root / "app")

    def test_create_shortcuts_invokes_powershell_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / installer.APP_EXE_NAME).write_text("app", encoding="utf-8")

            with patch.object(installer.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = ""
                run.return_value.stderr = ""

                installer._create_shortcuts(app_dir)

            command = run.call_args.args[0]
            self.assertEqual(command[0], "powershell.exe")
            self.assertIn("-AppDir", command)
            self.assertIn(str(app_dir), command)
            self.assertIn(str(app_dir / installer.APP_EXE_NAME), command)

    def test_main_quiet_no_shortcuts_installs_to_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = make_payload(root)
            local_app_data = root / "Local"

            with patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}), patch.object(
                installer, "_payload_root", return_value=payload
            ), patch.object(sys, "argv", ["AutoSupportGeneratorSetup.exe", "--quiet", "--no-shortcuts"]):
                exit_code = installer.main()

            app_dir = local_app_data / installer.INSTALL_DIR_NAME
            self.assertEqual(exit_code, 0)
            self.assertTrue((app_dir / installer.APP_EXE_NAME).is_file())
            self.assertTrue((app_dir / installer.LOG_FILE_NAME).is_file())

    def test_main_quiet_install_dir_installs_to_selected_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = make_payload(root)
            selected_dir = root / "Selected Install"

            with patch.object(installer, "_payload_root", return_value=payload), patch.object(
                sys,
                "argv",
                [
                    "AutoSupportGeneratorSetup.exe",
                    "--quiet",
                    "--no-shortcuts",
                    "--install-dir",
                    str(selected_dir),
                ],
            ):
                exit_code = installer.main()

            self.assertEqual(exit_code, 0)
            self.assertTrue((selected_dir / installer.APP_EXE_NAME).is_file())
            self.assertTrue((selected_dir / "examples" / "example_1" / "Compound_table.docx").is_file())

    def test_main_without_quiet_opens_gui_installer_with_selected_defaults(self) -> None:
        selected_dir = Path("C:/Apps/AutoSupportGenerator")

        with patch.object(
            sys,
            "argv",
            [
                "AutoSupportGeneratorSetup.exe",
                "--install-dir",
                str(selected_dir),
                "--no-shortcuts",
                "--no-launch",
            ],
        ), patch.object(installer, "_run_gui_installer", return_value=0) as gui:
            exit_code = installer.main()

        self.assertEqual(exit_code, 0)
        gui.assert_called_once_with(selected_dir, create_shortcuts=False, launch_after_install=False)

    def test_install_dir_from_args_accepts_equals_form(self) -> None:
        self.assertEqual(
            installer._install_dir_from_args(["--install-dir=C:/Apps/AutoSupportGenerator"]),
            Path("C:/Apps/AutoSupportGenerator"),
        )


if __name__ == "__main__":
    unittest.main()
