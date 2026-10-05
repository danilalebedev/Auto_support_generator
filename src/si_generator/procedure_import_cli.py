from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .procedure_import import generate_procedure_inputs, read_procedure_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create Reaction_schema.docx, Scope_draft.docx, and SI_template.docx from an ordinary method."
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
        text = read_procedure_text(args.procedure)
        generated = generate_procedure_inputs(
            text,
            args.output_folder,
            variable_names=args.variable,
            inventory_path=args.inventory,
            product_numbers=args.product_number,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Reaction schema: {generated.reaction_schema}")
    print(f"Scope draft: {generated.scope_draft}")
    print(f"SI template: {generated.si_template}")
    print(f"Review report: {generated.report}")
    print("Next: add ChemDraw OLE structures and measured masses to Scope_draft.docx, then rename it to Scope.docx.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
