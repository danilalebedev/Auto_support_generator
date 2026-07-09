from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from si_generator import mnova
from si_generator.mnova import MnovaBatchError, MnovaTask


class MnovaBatchRecoveryTests(unittest.TestCase):
    def test_no_status_batch_retries_by_compound(self) -> None:
        tasks = [
            MnovaTask("2a", "1H", Path("2a_1h/fid")),
            MnovaTask("2a", "13C", Path("2a_13c/fid")),
            MnovaTask("2b", "1H", Path("2b_1h/fid")),
            MnovaTask("2b", "13C", Path("2b_13c/fid")),
        ]
        calls: list[tuple[tuple[tuple[str, str], ...], Path]] = []

        def fake_once(
            batch_tasks: list[MnovaTask],
            output_dir: Path,
            timeout: int = 600,
            mnova_exe: str | Path | None = None,
        ) -> dict[tuple[str, str], dict[str, str]]:
            calls.append((tuple((task.compound, task.nucleus) for task in batch_tasks), Path(output_dir)))
            if len(calls) == 1:
                raise MnovaBatchError("ERROR: no status file", no_status=True, launch_log=Path("launch.txt"))
            return {
                (task.compound, task.nucleus): {
                    "report": f"{task.compound} {task.nucleus}",
                    "peak_report": "",
                    "image": "",
                    "mnova": "",
                    "single_mnova": "",
                    "reference_offset": "0",
                    "error": "",
                }
                for task in batch_tasks
            }

        with tempfile.TemporaryDirectory() as tmp, patch.object(mnova, "_extract_reports_batch_once", side_effect=fake_once):
            reports = mnova.extract_reports_batch(tasks, Path(tmp))

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0], (("2a", "1H"), ("2a", "13C"), ("2b", "1H"), ("2b", "13C")))
        self.assertEqual(calls[1][0], (("2a", "1H"), ("2a", "13C")))
        self.assertEqual(calls[2][0], (("2b", "1H"), ("2b", "13C")))
        self.assertEqual(calls[1][1].parts[-2:], ("retry_by_compound", "2a"))
        self.assertEqual(calls[2][1].parts[-2:], ("retry_by_compound", "2b"))
        self.assertEqual(set(reports), {("2a", "1H"), ("2a", "13C"), ("2b", "1H"), ("2b", "13C")})

    def test_single_compound_no_status_is_reported(self) -> None:
        tasks = [MnovaTask("2a", "1H", Path("2a_1h/fid"))]

        def fake_once(
            batch_tasks: list[MnovaTask],
            output_dir: Path,
            timeout: int = 600,
            mnova_exe: str | Path | None = None,
        ) -> dict[tuple[str, str], dict[str, str]]:
            raise MnovaBatchError("ERROR: no status file", no_status=True, launch_log=Path("launch.txt"))

        with tempfile.TemporaryDirectory() as tmp, patch.object(mnova, "_extract_reports_batch_once", side_effect=fake_once):
            with self.assertRaisesRegex(RuntimeError, "no status file"):
                mnova.extract_reports_batch(tasks, Path(tmp))


if __name__ == "__main__":
    unittest.main()
