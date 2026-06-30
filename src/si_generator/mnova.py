from __future__ import annotations

import argparse
import json
import locale
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .external_tools import find_mnova_executable, make_ascii_work_dir
from .runtime_paths import bundled_resource_path


SCRIPT_PATH = bundled_resource_path("scripts/extract_nmr_report.qs", package_file=__file__)


@dataclass(frozen=True)
class MnovaTask:
    compound: str
    nucleus: str
    input_path: Path
    image_path: Path | None = None
    mnova_path: Path | None = None
    render_spec: dict[str, object] | None = None
    single_mnova_path: Path | None = None


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
    mnova_exe: str | Path | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = output_dir / "mnova_batch_tasks.tsv"
    output_json_path = output_dir / "mnova_batch_reports.json"
    status_path = output_dir / "mnova_batch.status.txt"
    run_dir = make_ascii_work_dir("mnova")
    run_tasks_path = run_dir / "mnova_batch_tasks.tsv"
    run_output_json_path = run_dir / "mnova_batch_reports.json"
    run_status_path = run_dir / "mnova_batch.status.txt"
    output_map: dict[tuple[str, str], dict[str, Path]] = {}

    for path in [tasks_path, output_json_path, status_path]:
        if path.exists():
            path.unlink()

    try:
        lines = []
        for index, task in enumerate(tasks, start=1):
            key = (task.compound, task.nucleus)
            staged_input = _stage_spectrum_input(_resolve_spectrum_input(task.input_path), run_dir / "inputs", index)
            staged_image = run_dir / "images" / f"{_safe_token(task.compound)}_{task.nucleus}.png" if task.image_path else None
            staged_mnova = run_dir / "mnova" / _safe_token(task.compound) / f"{_safe_token(task.compound)}.mnova" if task.mnova_path else None
            staged_single_mnova = (
                run_dir / "single_mnova" / _safe_token(task.compound) / f"{_safe_token(task.compound)}_{task.nucleus}.mnova"
                if task.single_mnova_path
                else None
            )
            output_map[key] = {}
            if task.image_path and staged_image:
                task.image_path.parent.mkdir(parents=True, exist_ok=True)
                staged_image.parent.mkdir(parents=True, exist_ok=True)
                output_map[key]["image"] = task.image_path
            if task.mnova_path and staged_mnova:
                task.mnova_path.parent.mkdir(parents=True, exist_ok=True)
                staged_mnova.parent.mkdir(parents=True, exist_ok=True)
                output_map[key]["mnova"] = task.mnova_path
            if task.single_mnova_path and staged_single_mnova:
                task.single_mnova_path.parent.mkdir(parents=True, exist_ok=True)
                staged_single_mnova.parent.mkdir(parents=True, exist_ok=True)
                output_map[key]["single_mnova"] = task.single_mnova_path
            image_path = _mnova_arg(staged_image) if staged_image else ""
            mnova_path = _mnova_arg(staged_mnova) if staged_mnova else ""
            single_mnova_path = _mnova_arg(staged_single_mnova) if staged_single_mnova else ""
            lines.append(
                _format_task_line(
                    task.compound,
                    task.nucleus,
                    _mnova_arg(staged_input),
                    image_path=image_path,
                    mnova_path=mnova_path,
                    render_spec=task.render_spec,
                    single_mnova_path=single_mnova_path,
                )
            )
        run_tasks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        sf_arg = ",".join(
            [
                "extractSpectrumReportsBatch",
                _mnova_arg(run_tasks_path),
                _mnova_arg(run_output_json_path),
                _mnova_arg(run_status_path),
            ]
        )
        executable = find_mnova_executable(mnova_exe)
        print(f"[Mnova] executable: {executable}", flush=True)
        command = [str(executable), "-w", str(SCRIPT_PATH), "-sf", sf_arg]
        subprocess.run(command, cwd=run_dir, check=False, timeout=timeout)

        _copy_if_exists(run_tasks_path, tasks_path)
        _copy_if_exists(run_output_json_path, output_json_path)
        _copy_if_exists(run_status_path, status_path)

        status = _read_mnova_text(run_status_path) if run_status_path.exists() else "ERROR: no status file"
        if "DONE" not in status:
            raise RuntimeError(status.strip())
        if not run_output_json_path.exists():
            raise RuntimeError(f"Mnova did not create batch report file: {output_json_path}")

        raw = json.loads(_read_mnova_text(run_output_json_path))
        reports: dict[tuple[str, str], dict[str, str]] = {}
        for item in raw.values():
            compound = str(item.get("compound", ""))
            nucleus = str(item.get("nucleus", ""))
            key = (compound, nucleus)
            destinations = output_map.get(key, {})
            report = _normalize_report_text(str(item.get("report", "")))
            peak_report = _normalize_report_text(str(item.get("peakReport", "")))
            error = str(item.get("error", ""))
            image = _copy_mnova_output(str(item.get("image", "")), destinations.get("image"))
            reference_offset = str(item.get("referenceOffset", "0"))
            mnova = _copy_mnova_output(str(item.get("mnova", "")), destinations.get("mnova"))
            single_mnova = _copy_mnova_output(str(item.get("singleMnova", "")), destinations.get("single_mnova"))
            reports[key] = {
                "report": report,
                "peak_report": peak_report,
                "image": image,
                "mnova": mnova,
                "single_mnova": single_mnova,
                "reference_offset": reference_offset,
                "error": error,
            }

        return reports
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def _resolve_spectrum_input(path: Path) -> Path:
    path = path.resolve()
    if path.is_dir() and (path / "fid").exists():
        return path / "fid"
    return path


def _stage_spectrum_input(input_path: Path, inputs_root: Path, index: int) -> Path:
    inputs_root.mkdir(parents=True, exist_ok=True)
    source = input_path.resolve()
    if source.name.lower() == "fid" and source.parent.exists():
        target_dir = inputs_root / f"{index:03d}_{_safe_token(source.parent.name)}"
        shutil.copytree(source.parent, target_dir)
        return target_dir / "fid"
    if source.is_dir():
        target_dir = inputs_root / f"{index:03d}_{_safe_token(source.name)}"
        shutil.copytree(source, target_dir)
        return target_dir
    target = inputs_root / f"{index:03d}_{_safe_token(source.name)}"
    shutil.copy2(source, target)
    return target


def _copy_mnova_output(source: str, destination: Path | None) -> str:
    if not source:
        return ""
    source_path = Path(source)
    if destination is None or not source_path.exists():
        return source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    return str(destination)


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _read_mnova_text(path: Path) -> str:
    encodings = ["utf-8-sig", locale.getpreferredencoding(False), "mbcs", "cp1251"]
    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _mnova_arg(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _render_spec_arg(render_spec: dict[str, object] | None) -> str:
    if not render_spec:
        return "{}"
    return json.dumps(render_spec, ensure_ascii=True, separators=(",", ":"))


def _format_task_line(
    compound: str,
    nucleus: str,
    input_path: str,
    *,
    image_path: str = "",
    mnova_path: str = "",
    render_spec: dict[str, object] | None = None,
    single_mnova_path: str = "",
) -> str:
    return "\t".join(
        [
            compound,
            nucleus,
            input_path,
            image_path,
            mnova_path,
            _render_spec_arg(render_spec),
            single_mnova_path,
        ]
    )


def _safe_token(value: str) -> str:
    safe = "".join(char if char.isascii() and (char.isalnum() or char in "._-") else "_" for char in str(value))
    return safe.strip("._-") or "item"


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
