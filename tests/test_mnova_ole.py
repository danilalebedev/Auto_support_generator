from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from si_generator.domain.compound import Compound
from si_generator.mnova_ole import MnovaOleTarget, _registered_mnova_ole_class_type, mnova_placeholder_map


class MnovaOleTests(unittest.TestCase):
    def test_placeholder_map_carries_mnova_and_preview_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mnova = root / "2a.mnova"
            h1_png = root / "2a_1H.png"
            c13_png = root / "2a_13C.png"
            mnova.write_bytes(b"mnova")
            h1_png.write_bytes(b"png")
            c13_png.write_bytes(b"png")
            compound = Compound(
                number="2a",
                name="Example",
                mnova_path=str(mnova),
                h1_image_path=str(h1_png),
                c13_image_path=str(c13_png),
            )

            result = mnova_placeholder_map([compound])

        self.assertEqual(
            result,
            {
                "[[MNOVA:2a:1H]]": MnovaOleTarget(mnova_path=mnova, image_path=h1_png),
                "[[MNOVA:2a:13C]]": MnovaOleTarget(mnova_path=mnova, image_path=c13_png),
            },
        )

    def test_placeholder_map_skips_missing_mnova_files(self) -> None:
        compound = Compound(number="2a", name="Example", mnova_path="missing.mnova")

        self.assertEqual(mnova_placeholder_map([compound]), {})

    def test_registered_mnova_ole_class_skips_shell_only_file_association(self) -> None:
        def fake_hkcr_default(subkey: str) -> str:
            values = {
                ".mnova": "MNova.Document",
                "MNova.Document\\CLSID": "",
                "MestReNova.Document\\CLSID": "{registered-but-not-extension-default}",
            }
            return values.get(subkey, "")

        with patch("si_generator.mnova_ole._hkcr_default", fake_hkcr_default), patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(_registered_mnova_ole_class_type())

    def test_registered_mnova_ole_class_accepts_real_ole_file_association(self) -> None:
        def fake_hkcr_default(subkey: str) -> str:
            values = {
                ".mnova": "MestReNova.Document",
                "MestReNova.Document\\CLSID": "{registered}",
            }
            return values.get(subkey, "")

        with patch("si_generator.mnova_ole._hkcr_default", fake_hkcr_default), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_registered_mnova_ole_class_type(), "MestReNova.Document")

    def test_registered_mnova_ole_class_can_be_forced(self) -> None:
        def fake_hkcr_default(subkey: str) -> str:
            values = {
                ".mnova": "MNova.Document",
                "MNova.Document\\CLSID": "",
                "MestReNova.Document\\CLSID": "{registered}",
            }
            return values.get(subkey, "")

        with patch("si_generator.mnova_ole._hkcr_default", fake_hkcr_default), patch.dict("os.environ", {"AUTO_SUPPORT_FORCE_MNOVA_OLE": "1"}):
            self.assertEqual(_registered_mnova_ole_class_type(), "MestReNova.Document")


if __name__ == "__main__":
    unittest.main()
