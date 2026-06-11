from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .domain.manifest import manifest_has_errors
from .runtime_diagnostics import format_preflight_issues, issue_has_errors, preflight_generate_request
from .workflows.check_si import check_request_from_args, run_check_si
from .workflows.generate_si import output_path_from_state, request_from_args, run_generate_si
from .workflows.patch_si import patch_request_from_args, run_patch_si


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


def _main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.check_manifest:
        result = run_check_si(check_request_from_args(args))
        _print_check_result(result)
        return 1 if manifest_has_errors(result.get("issues", [])) else 0
    if args.patch_manifest:
        result = run_patch_si(patch_request_from_args(args))
        _print_patch_result(result)
        return 1 if manifest_has_errors(result.get("issues", [])) else 0
    if not args.output:
        parser.error("--output is required unless --check-manifest or --patch-manifest is used.")
    request = request_from_args(args)
    preflight_issues = preflight_generate_request(request)
    if preflight_issues:
        print(format_preflight_issues(preflight_issues))
    if issue_has_errors(preflight_issues):
        return 1
    result = run_generate_si(request)
    _print_generate_result(result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Supporting Information DOCX from compound CSV data.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", "-i", help="Path to compounds CSV.")
    input_group.add_argument("--word-input", help="Path to a Word table with ChemDraw/ChemSketch OLE structures.")
    input_group.add_argument("--check-manifest", help="Check an existing support_information.manifest.json file.")
    input_group.add_argument("--patch-manifest", help="Patch an existing support_information.manifest.json file.")
    parser.add_argument("--output", "-o", help="Path to output DOCX.")
    parser.add_argument("--support-docx", help="Optional DOCX path override for --check-manifest.")
    parser.add_argument("--renumber", help="For --patch-manifest, comma-separated OLD=NEW pairs, e.g. 2a=3a,2b=3b.")
    parser.add_argument("--remove", help="For --patch-manifest, comma-separated compound ids or numbers to remove.")
    parser.add_argument("--reorder", help="For --patch-manifest, comma-separated compound ids or numbers in the desired order.")
    parser.add_argument("--patched-output", help="For --patch-manifest, output path for the patched DOCX.")
    parser.add_argument("--patched-manifest-output", help="For --patch-manifest, output path for the patched manifest JSON.")
    parser.add_argument(
        "--no-strict-artifacts",
        action="store_true",
        help="For --check-manifest, only validate manifest structure and support DOCX, not every listed artifact path.",
    )
    parser.add_argument(
        "--template-docx",
        help="Optional Word file used as the visual template: margins, page setup, and named styles.",
    )
    parser.add_argument(
        "--style-config",
        help="Optional YAML file with semantic formatting rules for titles, NMR, HRMS, IR, and chemical notation.",
    )
    parser.add_argument(
        "--journal-profile",
        help="Optional built-in profile name (default, acs, rsc, wiley) or path to a journal profile YAML.",
    )
    parser.add_argument(
        "--references",
        help="Optional YAML file with bibliography entries referenced by the compound table.",
    )
    parser.add_argument(
        "--spectra-zip",
        help="Zip archive with compound-number folders containing NMR spectra.",
    )
    parser.add_argument(
        "--mnova-exe",
        help="Optional path to MestReNova.exe. If omitted, the program searches PATH, registry, and common install folders.",
    )
    parser.add_argument(
        "--no-extract-nmr",
        action="store_true",
        help="Do not run Mnova even if h1_spectrum_path/c13_spectrum_path columns are present.",
    )
    parser.add_argument(
        "--insert-spectra-as",
        choices=["png", "mnova", "both", "none"],
        default="png",
        help="How to place processed spectra in the appendix: PNG images, Mnova placeholders, both, or no appendix.",
    )
    parser.add_argument(
        "--generate-loadings",
        action="store_true",
        help="Calculate reagent loadings from target_mmol/reagent_N_* input columns when present.",
    )
    parser.add_argument(
        "--extract-structure-metadata",
        action="store_true",
        help="Try to read names/formulas from ChemDraw OLE objects. Slower and may require responsive OLE servers.",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated compound numbers to generate, e.g. 2a,2c.",
    )
    parser.add_argument(
        "--insert-chemdraw",
        action="store_true",
        help="Replace structure placeholders with ChemDraw OLE objects using structure_path values.",
    )
    parser.add_argument(
        "--no-check-support",
        action="store_true",
        help="Do not add support-check warnings for NMR counts and HRMS values.",
    )
    return parser


def _print_check_result(result: dict) -> None:
    status = result.get("status", "fail")
    issues = result.get("issues", [])
    for issue in issues:
        severity = issue.get("severity", "warning").upper()
        code = issue.get("code", "CHECK")
        message = issue.get("message", "")
        print(f"[{severity}] {code}: {message}")
    if status == "pass":
        print("Manifest check passed.")
    else:
        print("Manifest check failed.")
    if result.get("artifacts", {}).get("check_report"):
        print(f"Check report: {Path(result['artifacts']['check_report']).resolve()}")


def _print_patch_result(result: dict) -> None:
    for issue in result.get("issues", []):
        severity = issue.get("severity", "warning").upper()
        code = issue.get("code", "PATCH")
        message = issue.get("message", "")
        print(f"[{severity}] {code}: {message}")
    artifacts = result.get("artifacts", {})
    if artifacts.get("support_docx"):
        print(f"Patched DOCX: {artifacts['support_docx']}")
    if artifacts.get("manifest"):
        print(f"Patched manifest: {artifacts['manifest']}")
    if artifacts.get("patch_report"):
        print(f"Patch report: {Path(artifacts['patch_report']).resolve()}")
    if result.get("status") == "pass":
        print("Patch check passed.")
    else:
        print("Patch check failed.")


def _print_generate_result(result: dict) -> None:
    print(f"Generated {output_path_from_state(result).resolve()}")
    artifacts = result.get("artifacts", {})
    for label, key in [
        ("Spectra package", "processed_spectra_zip"),
        ("Manifest", "manifest"),
        ("Run summary", "run_summary"),
        ("Input warnings", "input_warnings"),
        ("Support warnings", "support_warnings"),
    ]:
        value = artifacts.get(key)
        if value:
            print(f"{label}: {Path(value).resolve()}")
