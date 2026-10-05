"""Reproducible example and PDF source-page images for visual QA."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=["example","sources","render-pdf"])
    parser.add_argument("--path",type=Path)
    args = parser.parse_args()
    if args.mode == "example":
        sys.path.insert(0,str(ROOT / "src"))
        from si_generator.procedure_import import generate_procedure_inputs
        text = ("To a solution of substrate A (100 mg, 0.50 mmol, 1.0 equiv) in THF (5.0 mL) "
                "were added NBS (1.2 equiv), Et3N (0.15 mL) and catalyst Q (5 mol%). "
                "The mixture was stirred at room temperature for 2 h, then quenched with water "
                "(10 mL) and extracted with EtOAc (20 mL).")
        result = generate_procedure_inputs(text,ROOT / "output" / "procedure_catalog_example",variable_names=["substrate A"],product_numbers=["2a","2b"])
        print(result)
    elif args.mode == "sources":
        import pypdfium2 as pdfium
        folder = ROOT / "output/acs_benchmark"
        sources = {r["source_id"]:r for r in json.loads((folder / "sources.json").read_text(encoding="utf-8"))}
        checks = {"S01":33,"S02":7,"S03":16,"S05":25,"S08":32,"S11":16,"S14":5,"S15":6,"S16":13}
        output = folder / "qa_pages"
        output.mkdir(exist_ok=True)
        for source,page in checks.items():
            document = pdfium.PdfDocument(folder / sources[source]["pdf_path"])
            document[page-1].render(scale=1.3).to_pil().save(output / f"{source}_p{page:02d}.png")
            document.close()
        print(output)
    else:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(args.path)
        for i in range(len(document)):
            document[i].render(scale=1.7).to_pil().save(args.path.with_name(args.path.stem+f"-page-{i+1}.png"))


if __name__ == "__main__": main()
