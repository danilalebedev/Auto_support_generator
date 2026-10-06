from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from .domain.types import SpectrumRenderSpec
from .domain.spectra_config import build_spectrum_render_spec
from .chemistry import parse_formula
from .mnova import MnovaTask, extract_reports_batch
from .domain.compound import Compound
from .nmr_validation import count_c_from_13c_nmr
from .output_layout import output_dirs


def fill_nmr_from_mnova(
    compounds: list[Compound],
    base_dir: str | Path,
    output_dir: str | Path,
    output_root: str | Path | None = None,
    mnova_exe: str | Path | None = None,
    mnova_graphics_profile_path: str | Path | None = None,
    mnova_graphics_profile_1h_path: str | Path | None = None,
    mnova_graphics_profile_13c_path: str | Path | None = None,
    render_specs_by_compound: dict[str, dict[str, SpectrumRenderSpec]] | None = None,
) -> None:
    base_dir = Path(base_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_root = Path(output_root).resolve() if output_root else output_dir.parent
    dirs = output_dirs(output_root / "support_information.docx")

    tasks: list[MnovaTask] = []
    image_root = dirs["spectra_dir"] / "images"
    processed_root = dirs["processed_mnova_dir"]
    reports_root = dirs["mnova_reports_dir"]
    mnova_graphics_profile = Path(mnova_graphics_profile_path).resolve() if mnova_graphics_profile_path else None
    mnova_graphics_profile_1h = (
        Path(mnova_graphics_profile_1h_path).resolve() if mnova_graphics_profile_1h_path else mnova_graphics_profile
    )
    mnova_graphics_profile_13c = (
        Path(mnova_graphics_profile_13c_path).resolve() if mnova_graphics_profile_13c_path else mnova_graphics_profile
    )
    for compound in compounds:
        compound_specs = (render_specs_by_compound or {}).get(compound.id or compound.number, {})
        h1_source = _resolve_path(compound.h1_spectrum_path, base_dir) if compound.h1_spectrum_path else None
        c13_source = _resolve_path(compound.c13_spectrum_path, base_dir) if compound.c13_spectrum_path else None
        mnova_path = processed_root / compound.number / f"{compound.number}.mnova"
        compound.mnova_path = str(mnova_path)
        if compound.h1_spectrum_path:
            image_path = image_root / f"{compound.number}_1H" / f"{compound.number}_1H.png"
            single_mnova_path = processed_root / compound.number / f"{compound.number}_1H.mnova"
            compound.h1_image_path = str(image_path)
            compound.h1_mnova_path = str(single_mnova_path)
            h1_render_spec = dict(compound_specs.get("1H", {}))
            expected_hydrogens = _formula_hydrogen_count(compound.formula)
            if expected_hydrogens:
                h1_render_spec["expected_hydrogen_count"] = expected_hydrogens
            tasks.append(
                MnovaTask(
                    compound.number,
                    "1H",
                    h1_source,
                    image_path,
                    mnova_path,
                    h1_render_spec,
                    single_mnova_path,
                    mnova_graphics_profile_1h,
                )
            )
        if compound.c13_spectrum_path:
            image_path = image_root / f"{compound.number}_13C" / f"{compound.number}_13C.png"
            single_mnova_path = processed_root / compound.number / f"{compound.number}_13C.mnova"
            compound.c13_image_path = str(image_path)
            compound.c13_mnova_path = str(single_mnova_path)
            tasks.append(
                MnovaTask(
                    compound.number,
                    "13C",
                    c13_source,
                    image_path,
                    mnova_path,
                    dict(compound_specs.get("13C", {})),
                    single_mnova_path,
                    mnova_graphics_profile_13c,
                )
            )
        for nucleus, input_path in discover_2d_experiments(compound):
            image_path = image_root / f"{compound.number}_{nucleus}" / f"{compound.number}_{nucleus}.png"
            single_mnova_path = processed_root / compound.number / f"{compound.number}_{nucleus}.mnova"
            render_spec = dict(compound_specs.get(nucleus, build_spectrum_render_spec(nucleus, {})))
            vertical_nucleus = "1H" if nucleus in {"NOESY", "COSY", "TOCSY", "ROESY"} else "13C"
            render_spec["horizontal_trace_render_spec"] = dict(
                compound_specs.get("1H", build_spectrum_render_spec("1H", {}))
            )
            render_spec["vertical_trace_render_spec"] = dict(
                compound_specs.get(vertical_nucleus, build_spectrum_render_spec(vertical_nucleus, {}))
            )
            use_external_traces = bool(render_spec.get("use_external_traces", True))
            tasks.append(
                MnovaTask(
                    compound=compound.number,
                    nucleus=nucleus,
                    input_path=input_path,
                    image_path=image_path,
                    mnova_path=mnova_path,
                    render_spec=render_spec,
                    single_mnova_path=single_mnova_path,
                    graphics_profile_path=None,
                    horizontal_trace_path=h1_source if use_external_traces else None,
                    vertical_trace_path=(h1_source if vertical_nucleus == "1H" else c13_source) if use_external_traces else None,
                )
            )

    if not tasks:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[Mnova] extracting {len(tasks)} spectra in one MestReNova session", flush=True)
    reports = extract_reports_batch(tasks, output_dir, mnova_exe=mnova_exe)

    for compound in compounds:
        h1 = reports.get((compound.number, "1H"))
        if h1:
            if h1["error"]:
                print(f"[Mnova] {compound.number} 1H: {h1['error']}", flush=True)
            else:
                report = _apply_reference_offset(h1["report"], h1.get("reference_offset", "0"), 2)
                compound.h1_conditions, compound.h1_nmr = _parse_mnova_report(report, "1H")
                if h1.get("image"):
                    compound.h1_image_path = h1["image"]
                if h1.get("single_mnova"):
                    compound.h1_mnova_path = h1["single_mnova"]
                _write_report(reports_root, compound.number, "1H", report)

        c13 = reports.get((compound.number, "13C"))
        if c13:
            if c13["error"]:
                print(f"[Mnova] {compound.number} 13C: {c13['error']}", flush=True)
            else:
                base_report = _apply_reference_offset(c13["report"], c13.get("reference_offset", "0"), 1)
                peak_report = _apply_reference_offset(c13.get("peak_report", ""), c13.get("reference_offset", "0"), 1)
                report = _complete_13c_report(base_report, peak_report, compound.formula)
                compound.c13_conditions, compound.c13_nmr = _parse_mnova_report(report, "13C")
                if c13.get("image"):
                    compound.c13_image_path = c13["image"]
                if c13.get("single_mnova"):
                    compound.c13_mnova_path = c13["single_mnova"]
                _write_report(reports_root, compound.number, "13C", report)

        for nucleus, _ in discover_2d_experiments(compound):
            two_d = reports.get((compound.number, nucleus))
            if not two_d:
                continue
            if two_d["error"]:
                print(f"[Mnova] {compound.number} {nucleus}: {two_d['error']}", flush=True)
                continue
            for key in ("image", "single_mnova"):
                path = two_d.get(key, "")
                if path and path not in compound.spectra_2d_files:
                    compound.spectra_2d_files.append(path)

        report_mnova = next(
            (item.get("mnova", "") for key, item in reports.items() if key[0] == compound.number and item.get("mnova")),
            "",
        )
        if report_mnova:
            compound.mnova_path = report_mnova

    package = _build_processed_spectra_package(compounds, output_root)
    print(f"[Output] processed spectra package: {package}", flush=True)


def _write_report(reports_root: Path, compound_number: str, nucleus: str, report: str) -> None:
    folder = reports_root / compound_number
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{compound_number}_{nucleus}.txt").write_text(report, encoding="utf-8")


def _build_processed_spectra_package(compounds: list[Compound], output_root: Path) -> Path:
    dirs = output_dirs(output_root / "support_information.docx")
    package_root = dirs["processed_spectra_dir"]
    zip_path = dirs["processed_spectra_zip"]

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)

    for compound in compounds:
        folder = package_root / compound.number
        wrote_any = False
        for source, suffix in [
            (compound.h1_image_path, "1H.png"),
            (compound.c13_image_path, "13C.png"),
            (compound.h1_mnova_path, "1H.mnova"),
            (compound.c13_mnova_path, "13C.mnova"),
            (compound.mnova_path, "mnova"),
        ]:
            if not source:
                continue
            source_path = Path(source)
            if not source_path.exists():
                continue
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{compound.number}_{suffix}" if suffix != "mnova" else folder / f"{compound.number}.mnova"
            shutil.copy2(source_path, target)
            wrote_any = True
        for source in compound.spectra_2d_files:
            source_path = Path(source)
            if source_path.suffix.lower() not in {".png", ".mnova"} or not source_path.exists():
                continue
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, folder / source_path.name)
            wrote_any = True
        if not wrote_any and folder.exists():
            folder.rmdir()

    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_root))
    return zip_path


def discover_2d_experiments(compound: Compound) -> list[tuple[str, Path]]:
    roots: list[Path] = []
    if compound.spectra_2d_folder:
        roots.append(Path(compound.spectra_2d_folder))
    for value in compound.spectra_2d_files:
        path = Path(value)
        roots.append(path if path.is_dir() else path.parent)

    experiments: dict[str, Path] = {}
    seen_roots: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen_roots or not resolved.exists():
            continue
        seen_roots.add(resolved)
        candidates = [resolved] if (resolved / "ser").is_file() else [path.parent for path in resolved.rglob("ser")]
        for candidate in sorted(candidates, key=lambda path: str(path).casefold()):
            if not ((candidate / "acqu2").exists() or (candidate / "acqu2s").exists()):
                continue
            nucleus = _infer_2d_nucleus(candidate)
            if nucleus and nucleus not in experiments:
                experiments[nucleus] = candidate
    order = {name: index for index, name in enumerate(("HSQC", "HMBC", "NOESY", "COSY", "TOCSY", "ROESY"))}
    return sorted(experiments.items(), key=lambda item: (order.get(item[0], 999), str(item[1]).casefold()))


def _infer_2d_nucleus(experiment: Path) -> str:
    fragments = [experiment.name]
    for relative in (Path("pulseprogram"), Path("pdata") / "1" / "title"):
        path = experiment / relative
        if not path.is_file():
            continue
        try:
            fragments.append(path.read_text(encoding="utf-8", errors="ignore")[:8192])
        except OSError:
            continue
    text = " ".join(fragments).upper()
    for label in ("HSQC", "HMBC", "NOESY", "TOCSY", "ROESY", "COSY"):
        if label in text:
            return label
    return ""


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value.strip().strip('"'))
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _formula_hydrogen_count(formula: str) -> int:
    if not formula:
        return 0
    try:
        return int(parse_formula(formula).get("H", 0))
    except ValueError:
        return 0


def _parse_mnova_report(report: str, nucleus: str) -> tuple[str, str]:
    report = " ".join(report.strip().split())
    match = re.match(rf"^{re.escape(nucleus)}\s+NMR\s*\((?P<conditions>[^)]*)\)\s*\u03b4\s*(?P<body>.*)$", report)
    if not match:
        return "", report

    conditions = _normalize_conditions(match.group("conditions"), nucleus)
    body = match.group("body").strip()
    if body and not body.startswith("="):
        body = "= " + body
    return conditions, "\u03b4 " + body


def _normalize_conditions(conditions: str, nucleus: str) -> str:
    parts = [part.strip() for part in conditions.split(",") if part.strip()]
    if len(parts) == 2 and parts[0].lower().endswith("mhz"):
        parts = [parts[1], parts[0]]
    if nucleus == "13C":
        parts = [_normalize_c13_frequency(part) for part in parts]
    return ", ".join(parts)


def _normalize_c13_frequency(part: str) -> str:
    match = re.fullmatch(r"(\d+)\s*MHz", part)
    if not match:
        return part
    value = int(match.group(1))
    if value in {101, 151}:
        value -= 1
    return f"{value} MHz"


def _complete_13c_report(base_report: str, peak_report: str, formula: str) -> str:
    if not peak_report or not formula:
        return base_report

    try:
        expected_c = parse_formula(formula).get("C", 0)
    except ValueError:
        return base_report

    base_count = count_c_from_13c_nmr(base_report)
    if not expected_c or base_count >= expected_c:
        return base_report

    base_shifts = _extract_shifts(base_report)
    peak_shifts = _extract_shifts(peak_report)
    if not base_shifts or not peak_shifts:
        return base_report

    shifts = base_shifts[:]
    candidates = [shift for shift in peak_shifts if not _has_close_shift(shifts, shift)]
    candidates.sort(reverse=True)
    for shift in candidates:
        shifts.append(shift)
        if len(shifts) >= expected_c:
            break

    if len(shifts) < expected_c:
        return base_report

    shifts = sorted(shifts, reverse=True)
    header = base_report.split("\u03b4", 1)[0].strip()
    return f"{header} \u03b4 " + ", ".join(f"{shift:.1f}" for shift in shifts) + "."


def _extract_shifts(report: str) -> list[float]:
    body = report.split("\u03b4", 1)[-1]
    shifts = []
    for item in _split_top_level_commas(body):
        match = re.match(r"\s*=?\s*(-?\d+(?:\.\d+)?)\b", item)
        if match:
            shifts.append(float(match.group(1)))
    return shifts


def _split_top_level_commas(text: str) -> list[str]:
    result = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index])
            start = index + 1
    result.append(text[start:])
    return result


def _has_close_shift(shifts: list[float], candidate: float, tolerance: float = 0.15) -> bool:
    return any(abs(shift - candidate) <= tolerance for shift in shifts)


def _apply_reference_offset(report: str, offset_text: str, precision: int) -> str:
    if not report:
        return report
    try:
        offset = float(offset_text)
    except (TypeError, ValueError):
        return report
    if abs(offset) < 0.005:
        return report

    if "\u03b4" not in report:
        return report
    header, body = report.split("\u03b4", 1)
    prefix = ""
    if body.lstrip().startswith("="):
        leading_ws = body[: len(body) - len(body.lstrip())]
        prefix = leading_ws + "= "
        body = body.lstrip()[1:].lstrip()

    shifted_items = [_shift_peak_item(item, offset, precision) for item in _split_top_level_commas(body)]
    return f"{header}\u03b4 {prefix}{', '.join(item.strip() for item in shifted_items if item.strip())}"


def _shift_peak_item(item: str, offset: float, precision: int) -> str:
    leading = item[: len(item) - len(item.lstrip())]
    rest = item.lstrip()

    def shift(match: re.Match[str]) -> str:
        return f"{float(match.group(0)) + offset:.{precision}f}"

    rest = re.sub(r"^-?\d+(?:\.\d+)?", shift, rest, count=1)
    rest = re.sub(r"(?<=\s-\s)-?\d+(?:\.\d+)?", shift, rest, count=1)
    return leading + rest
