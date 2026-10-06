from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .procedure_import import generate_procedure_inputs, generate_procedure_inputs_from_docx, read_procedure_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a loadings table and Auto Support Generator input drafts from an ordinary method."
    )
    parser.add_argument("procedure", help="UTF-8 .txt/.md or .docx file containing the procedure.")
    parser.add_argument("--output-folder", "-o", required=True, help="Folder for generated input drafts.")
    parser.add_argument(
        "--variable",
        action="append",
        default=[],
        help="Chemical that varies across the scope. Repeat for Reagent_2, Reagent_3, etc.",
    )
    parser.add_argument("--inventory", help="Optional CSV with name, synonyms, molecular_weight_g_mol, density_g_ml, role.")
    parser.add_argument(
        "--product-number",
        action="append",
        default=[],
        help="Optional Scope product number. Repeat for every product row.",
    )
    args = parser.parse_args(argv)
    try:
        if Path(args.procedure).suffix.casefold() == ".docx":
            generated = generate_procedure_inputs_from_docx(
                args.procedure,
                args.output_folder,
                variable_names=args.variable,
                inventory_path=args.inventory,
                product_numbers=args.product_number,
            )
        else:
            generated = generate_procedure_inputs(
                read_procedure_text(args.procedure),
                args.output_folder,
                variable_names=args.variable,
                inventory_path=args.inventory,
                product_numbers=args.product_number,
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"All-in-one input: {generated.all_in_one}")
    print(f"Compound table: {generated.compound_table}")
    print(f"Reaction schema: {generated.reaction_schema}")
    print(f"Scope: {generated.scope}")
    print(f"SI template: {generated.si_template}")
    print(f"Loadings table: {generated.loadings_table}")
    print(f"Review report: {generated.report}")
    print("Next: review highlighted cells, then add ChemDraw OLE structures and measured values to Compound_table.docx and Scope.docx.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
