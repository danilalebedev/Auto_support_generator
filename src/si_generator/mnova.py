from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MNOVA_EXE = Path(r"C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe")


def _resource_path(relative_path: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path


SCRIPT_PATH = _resource_path("scripts/extract_nmr_report.qs")


@dataclass(frozen=True)
class MnovaTask:
    compound: str
    nucleus: str
    input_path: Path
    image_path: Path | None = None
    mnova_path: Path | None = None


def extract_report(input_path: Path, output_path: Path, nucleus: str, timeout: int = 120) -> Path:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reports = extract_reports_batch(
        [MnovaTask(compound="compound", nucleus=nucleus, input_path=input_path)],
        output_path.parent,
        timeout=timeout,
    )
    result = reports.get(("compound", nucleus))
    if not result:
        raise RuntimeError(f"Mnova did not return a report for {nucleus}: {input_path}")
    if result["error"]:
        raise RuntimeError(result["error"])
    output_path.write_text(result["report"], encoding="utf-8")
    return output_path


def extract_reports_batch(
    tasks: list[MnovaTask],
    output_dir: Path,
    timeout: int = 600,
) -> dict[tuple[str, str], dict[str, str]]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = output_dir / "mnova_batch_tasks.tsv"
    output_json_path = output_dir / "mnova_batch_reports.json"
    status_path = output_dir / "mnova_batch.status.txt"

    for path in [tasks_path, output_json_path, status_path]:
        if path.exists():
            path.unlink()

    lines = []
    for task in tasks:
        input_path = _resolve_spectrum_input(task.input_path)
        image_path = _mnova_arg(task.image_path) if task.image_path else ""
        mnova_path = _mnova_arg(task.mnova_path) if task.mnova_path else ""
        if task.image_path:
            task.image_path.parent.mkdir(parents=True, exist_ok=True)
        if task.mnova_path:
            task.mnova_path.parent.mkdir(parents=True, exist_ok=True)
        lines.append(f"{task.compound}\t{task.nucleus}\t{_mnova_arg(input_path)}\t{image_path}\t{mnova_path}")
    tasks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sf_arg = ",".join(
        [
            "extractSpectrumReportsBatch",
            _mnova_arg(tasks_path),
            _mnova_arg(output_json_path),
            _mnova_arg(status_path),
        ]
    )
    command = [str(MNOVA_EXE), "-w", str(SCRIPT_PATH), "-sf", sf_arg]
    subprocess.run(command, cwd=output_dir, check=False, timeout=timeout)

    status = status_path.read_text(encoding="utf-8", errors="replace") if status_path.exists() else "ERROR: no status file"
    if "DONE" not in status:
        raise RuntimeError(status.strip())
    if not output_json_path.exists():
        raise RuntimeError(f"Mnova did not create batch report file: {output_json_path}")

    raw = json.loads(output_json_path.read_text(encoding="utf-8", errors="replace"))
    reports: dict[tuple[str, str], dict[str, str]] = {}
    for item in raw.values():
        compound = str(item.get("compound", ""))
        nucleus = str(item.get("nucleus", ""))
        report = _normalize_report_text(str(item.get("report", "")))
        peak_report = _normalize_report_text(str(item.get("peakReport", "")))
        error = str(item.get("error", ""))
        image = str(item.get("image", ""))
        reference_offset = str(item.get("referenceOffset", "0"))
        mnova = str(item.get("mnova", ""))
        reports[(compound, nucleus)] = {
            "report": report,
            "peak_report": peak_report,
            "image": image,
            "mnova": mnova,
            "reference_offset": reference_offset,
            "error": error,
        }

    return reports


def _resolve_spectrum_input(path: Path) -> Path:
    path = path.resolve()
    if path.is_dir() and (path / "fid").exists():
        return path / "fid"
    return path


def _mnova_arg(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _normalize_report_text(text: str) -> str:
    return (
        text.replace(" ? ", " \u03b4 ")
        .replace(" \u041e\u0491 ", " \u03b4 ")
        .replace("\u00c2", "")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract an NMR text report from Mnova automatic multiplet analysis.")
    parser.add_argument("input", help="Bruker experiment folder or fid file.")
    parser.add_argument("output", help="Output text file.")
    parser.add_argument("--nucleus", choices=["1H", "13C"], required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)

    path = extract_report(Path(args.input), Path(args.output), args.nucleus, args.timeout)
    print(f"Generated {path}")
    print(path.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
