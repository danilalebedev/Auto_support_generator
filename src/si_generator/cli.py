from __future__ import annotations

import argparse
import sys

from .workflows.generate_si import output_path_from_state, request_from_args, run_generate_si


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


def _main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run_generate_si(request_from_args(args))
    print(f"Generated {output_path_from_state(result).resolve()}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Supporting Information DOCX from compound CSV data.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", "-i", help="Path to compounds CSV.")
    input_group.add_argument("--word-input", help="Path to a Word table with ChemDraw/ChemSketch OLE structures.")
    parser.add_argument("--output", "-o", required=True, help="Path to output DOCX.")
    parser.add_argument(
        "--template-docx",
        help="Optional Word file used as the visual template: margins, page setup, and named styles.",
    )
    parser.add_argument(
        "--style-config",
        help="Optional YAML file with semantic formatting rules for titles, NMR, HRMS, IR, and chemical notation.",
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
