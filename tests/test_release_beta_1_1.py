from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

from si_generator.models import Compound
from si_generator.spectra_zip import assign_spectra_from_folder, prepare_spectra_source


REPO_ROOT = Path(__file__).resolve().parents[1]


class SpectraSourceTests(unittest.TestCase):
    def test_prepare_spectra_source_accepts_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_root = root / "spectra"
            _write_bruker_experiment(spectra_root / "2a" / "run_1H", "1H")
            _write_bruker_experiment(spectra_root / "2a" / "run_13C", "13C")
            compound = Compound(number="2a", name="Example")

            prepared = prepare_spectra_source(spectra_root, root / "work")
            assign_spectra_from_folder([compound], prepared)

        self.assertIn("run_1H", compound.h1_spectrum_path)
        self.assertIn("run_13C", compound.c13_spectrum_path)

    def test_prepare_spectra_source_accepts_single_compound_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compound_folder = root / "2a"
            _write_bruker_experiment(compound_folder / "run_1H", "1H")
            compound = Compound(number="2a", name="Example")

            prepared = prepare_spectra_source(compound_folder, root / "work")
            assign_spectra_from_folder([compound], prepared)

        self.assertIn("run_1H", compound.h1_spectrum_path)

    def test_prepare_spectra_source_accepts_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "spectra.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("2a/run_1H/fid", "")
                archive.writestr("2a/run_1H/acqus", "##$NUC1= <1H>")
            compound = Compound(number="2a", name="Example")

            prepared = prepare_spectra_source(zip_path, root / "work")
            assign_spectra_from_folder([compound], prepared)

        self.assertIn("run_1H", compound.h1_spectrum_path)

    def test_prepare_spectra_source_rejects_unsafe_zip_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            zip_path = root / "bad.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("../escape/fid", "")

            with self.assertRaisesRegex(ValueError, "Unsafe path"):
                prepare_spectra_source(zip_path, root / "work")


class InstallerShortcutTests(unittest.TestCase):
    def test_shortcut_command_uses_named_file_parameters(self) -> None:
        installer = _load_installer_module()

        command = installer._shortcut_command(
            Path("create_shortcuts.ps1"),
            Path("C:/Users/User/AppData/Local/AutoSupportGenerator"),
            Path("C:/Users/User/AppData/Local/AutoSupportGenerator/AutoSupportGenerator.exe"),
        )

        self.assertIn("-File", command)
        self.assertIn("-AppDir", command)
        self.assertIn("-ExePath", command)
        self.assertNotIn("-Command", command)

    def test_shortcut_script_sets_target_and_validates_saved_link(self) -> None:
        installer = _load_installer_module()
        script = installer._shortcut_script()

        self.assertIn("$shortcut.TargetPath = $ExePath", script)
        self.assertIn("$shortcut.WorkingDirectory = $AppDir", script)
        self.assertIn("$saved.TargetPath -ne $ExePath", script)


def _write_bruker_experiment(path: Path, nucleus: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "fid").write_bytes(b"")
    (path / "acqus").write_text(f"##$NUC1= <{nucleus}>", encoding="latin1")


def _load_installer_module():
    module_path = REPO_ROOT / "scripts" / "auto_support_generator_installer.py"
    spec = importlib.util.spec_from_file_location("auto_support_generator_installer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load installer module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
