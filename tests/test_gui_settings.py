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
                    "output_folder": Path("output/runs/demo"),
                    "unknown": "ignored",
                    "input_kind": "WORD",
                    "insert_spectra_as": "invalid",
                    "target_signal_height_percent": "72",
                    "h1_ppm_min": "-0.5",
                    "h1_ppm_max": "11.5",
                    "c13_ppm_min": "-5",
                    "c13_ppm_max": "205",
                    "peak_threshold_1h_percent": "8",
                    "peak_threshold_13c_percent": "4",
                    "loadings_schema_docx": Path("Reaction_schema.docx"),
                    "loadings_scope_docx": Path("Scope.docx"),
                    "mnova_graphics_profile": Path("default.mngp"),
                    "check_support": "false",
                    "generate_loadings": "yes",
                    "calculate_elemental_analysis": "true",
                }
            }
        )

        self.assertEqual(settings["input_path"], "input.docx")
        self.assertEqual(settings["output_folder"], str(Path("output/runs/demo")))
        self.assertEqual(settings["input_kind"], "word")
        self.assertEqual(settings["target_signal_height_percent"], "72")
        self.assertEqual(settings["h1_ppm_min"], "-0.5")
        self.assertEqual(settings["h1_ppm_max"], "11.5")
        self.assertEqual(settings["c13_ppm_min"], "-5")
        self.assertEqual(settings["c13_ppm_max"], "205")
        self.assertEqual(settings["peak_threshold_1h_percent"], "8")
        self.assertEqual(settings["peak_threshold_13c_percent"], "4")
        self.assertEqual(settings["loadings_schema_docx"], "Reaction_schema.docx")
        self.assertEqual(settings["loadings_scope_docx"], "Scope.docx")
        self.assertEqual(settings["mnova_graphics_profile"], "default.mngp")
        self.assertNotIn("unknown", settings)
        self.assertNotIn("insert_spectra_as", settings)
        self.assertFalse(settings["check_support"])
        self.assertTrue(settings["generate_loadings"])
        self.assertTrue(settings["calculate_elemental_analysis"])

    def test_saves_and_loads_settings_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gui_settings.json"

            saved_path = save_gui_settings(
                {
                    "input_path": "C:/data/input.docx",
                    "spectra_zip": "C:/data/spectra.zip",
                    "output_folder": "C:/data/output",
                    "input_kind": "csv",
                    "insert_spectra_as": "mnova",
                    "target_signal_height_percent": "85",
                    "h1_ppm_min": "-1",
                    "h1_ppm_max": "12",
                    "c13_ppm_min": "-10",
                    "c13_ppm_max": "210",
                    "peak_threshold_1h_percent": "6",
                    "peak_threshold_13c_percent": "4",
                    "loadings_schema_docx": "C:/data/loadings/Reaction_schema.docx",
                    "loadings_scope_docx": "C:/data/loadings/Scope.docx",
                    "mnova_graphics_profile": "C:/data/profiles/default.mngp",
                    "check_support": True,
                    "generate_loadings": False,
                    "calculate_elemental_analysis": True,
                },
                path=path,
            )
            loaded = load_gui_settings(path)

        self.assertEqual(saved_path, path)
        self.assertEqual(loaded["input_path"], "C:/data/input.docx")
        self.assertEqual(loaded["spectra_zip"], "C:/data/spectra.zip")
        self.assertEqual(loaded["output_folder"], "C:/data/output")
        self.assertEqual(loaded["input_kind"], "csv")
        self.assertEqual(loaded["insert_spectra_as"], "mnova")
        self.assertEqual(loaded["target_signal_height_percent"], "85")
        self.assertEqual(loaded["h1_ppm_min"], "-1")
        self.assertEqual(loaded["h1_ppm_max"], "12")
        self.assertEqual(loaded["c13_ppm_min"], "-10")
        self.assertEqual(loaded["c13_ppm_max"], "210")
        self.assertEqual(loaded["peak_threshold_1h_percent"], "6")
        self.assertEqual(loaded["peak_threshold_13c_percent"], "4")
        self.assertEqual(loaded["loadings_schema_docx"], "C:/data/loadings/Reaction_schema.docx")
        self.assertEqual(loaded["loadings_scope_docx"], "C:/data/loadings/Scope.docx")
        self.assertEqual(loaded["mnova_graphics_profile"], "C:/data/profiles/default.mngp")
        self.assertTrue(loaded["check_support"])
        self.assertFalse(loaded["generate_loadings"])
        self.assertTrue(loaded["calculate_elemental_analysis"])

    def test_load_returns_empty_settings_for_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gui_settings.json"
            path.write_text("{broken", encoding="utf-8")

            loaded = load_gui_settings(path)

        self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main()
