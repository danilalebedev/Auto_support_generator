from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .chemdraw_ole import insert_chemdraw_placeholders
from .docx_builder import build_document
from .input_validation import validate_compound_inputs
from .input_table import read_compounds
from .nmr_fill import fill_nmr_from_mnova
from .nmr_validation import validate_support
from .spectra_zip import assign_spectra_from_folder, prepare_spectra_zip
from .style_config import config_get, load_style_config
from .word_input import paste_word_structures, read_word_compounds


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


def _main(argv: list[str] | None = None) -> int:
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
    args = parser.parse_args(argv)
    style_config = load_style_config(args.style_config)

    input_path = Path(args.word_input or args.input)
    compounds = (
        read_word_compounds(args.word_input, extract_structure_metadata=args.extract_structure_metadata)
        if args.word_input
        else read_compounds(args.input)
    )
    if args.only:
        wanted = {item.strip() for item in args.only.split(",") if item.strip()}
        compounds = [compound for compound in compounds if compound.number in wanted]
    if args.spectra_zip:
        spectra_root = prepare_spectra_zip(args.spectra_zip, Path(args.output).parent / "logs" / "_spectra_zip")
        assign_spectra_from_folder(compounds, spectra_root)
    for warning in validate_compound_inputs(compounds, require_structure=bool(args.word_input)):
        print(f"[Input warning] {warning}", flush=True)
    if not args.no_extract_nmr:
        fill_nmr_from_mnova(
            compounds,
            input_path.parent,
            Path(args.output).parent / "logs" / "mnova_batch",
            output_root=Path(args.output).parent,
            mnova_exe=args.mnova_exe,
        )
    if not args.no_check_support:
        validate_support(compounds)
    output_path = build_document(compounds, args.output, style_config=style_config, template_path=args.template_docx)

    if args.word_input:
        paste_word_structures(
            args.word_input,
            output_path,
            compounds,
            main_top_offset_pt=float(config_get(style_config, "compound.structure.top_offset_pt", 12)),
            appendix_top_offset_pt=float(config_get(style_config, "appendix.structure.top_offset_pt", 0)),
        )
    elif args.insert_chemdraw:
        structure_map = {compound.number: compound.structure_path for compound in compounds if compound.structure_path}
        if structure_map:
            insert_chemdraw_placeholders(output_path, structure_map)

    print(f"Generated {Path(output_path).resolve()}")
    return 0
