from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.gui_settings import load_gui_settings, normalize_gui_settings, save_gui_settings


class GuiSettingsTests(unittest.TestCase):
    def test_normalizes_known_fields_and_filters_unknown_values(self) -> None:
        settings = normalize_gui_settings(
            {
                "settings": {
                    "input_path": Path("input.docx"),
                    "unknown": "ignored",
                    "input_kind": "WORD",
                    "insert_spectra_as": "invalid",
                    "peak_threshold_1h_percent": "8",
                    "peak_threshold_13c_percent": "4",
                    "loadings_schema_docx": Path("Reaction_schema.docx"),
                    "loadings_scope_docx": Path("Scope.docx"),
                    "check_support": "false",
                    "generate_loadings": "yes",
                }
            }
        )

        self.assertEqual(settings["input_path"], "input.docx")
        self.assertEqual(settings["input_kind"], "word")
        self.assertEqual(settings["peak_threshold_1h_percent"], "8")
        self.assertEqual(settings["peak_threshold_13c_percent"], "4")
        self.assertEqual(settings["loadings_schema_docx"], "Reaction_schema.docx")
        self.assertEqual(settings["loadings_scope_docx"], "Scope.docx")
        self.assertNotIn("unknown", settings)
        self.assertNotIn("insert_spectra_as", settings)
        self.assertFalse(settings["check_support"])
        self.assertTrue(settings["generate_loadings"])

    def test_saves_and_loads_settings_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gui_settings.json"

            saved_path = save_gui_settings(
                {
                    "input_path": "C:/data/input.docx",
                    "spectra_zip": "C:/data/spectra.zip",
                    "input_kind": "csv",
                    "insert_spectra_as": "mnova",
                    "peak_threshold_1h_percent": "6",
                    "peak_threshold_13c_percent": "4",
                    "loadings_schema_docx": "C:/data/loadings/Reaction_schema.docx",
                    "loadings_scope_docx": "C:/data/loadings/Scope.docx",
                    "check_support": True,
                    "generate_loadings": False,
                },
                path=path,
            )
            loaded = load_gui_settings(path)

        self.assertEqual(saved_path, path)
        self.assertEqual(loaded["input_path"], "C:/data/input.docx")
        self.assertEqual(loaded["spectra_zip"], "C:/data/spectra.zip")
        self.assertEqual(loaded["input_kind"], "csv")
        self.assertEqual(loaded["insert_spectra_as"], "mnova")
        self.assertEqual(loaded["peak_threshold_1h_percent"], "6")
        self.assertEqual(loaded["peak_threshold_13c_percent"], "4")
        self.assertEqual(loaded["loadings_schema_docx"], "C:/data/loadings/Reaction_schema.docx")
        self.assertEqual(loaded["loadings_scope_docx"], "C:/data/loadings/Scope.docx")
        self.assertTrue(loaded["check_support"])
        self.assertFalse(loaded["generate_loadings"])

    def test_load_returns_empty_settings_for_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gui_settings.json"
            path.write_text("{broken", encoding="utf-8")

            loaded = load_gui_settings(path)

        self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main()
