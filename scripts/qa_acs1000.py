"""Render a fixed development-only source sample with bundled pypdfium2."""
import json
import argparse
import os
from pathlib import Path

import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1]
FOLDER=Path(os.environ.get("ACS_BENCHMARK_DIR",str(ROOT / "output/acs_benchmark_1000"))).resolve()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ids",nargs="*")
    parser.add_argument("--revisions",action="store_true")
    args=parser.parse_args()
    cases=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))["cases"]
    development=[c for c in cases if c["split"]=="development"]
    sources={str(s["figshare_id"]):s for s in json.loads((FOLDER / "sources.json").read_text(encoding="utf-8"))}
    output=FOLDER / "qa_pages"
    output.mkdir(exist_ok=True)
    sample=[]
    selected=[c for c in development if c["id"] in args.ids] if args.ids else [development[i] for i in [10,75,140,215]]
    if args.ids and {c["id"] for c in selected}!=set(args.ids): raise ValueError("Visual source QA is restricted to known development cases")
    for case in selected:
        if args.revisions:
            proposals=json.loads((FOLDER / "boundary_revision_proposals.json").read_text(encoding="utf-8"))["proposals"]
            revision=next((p for p in proposals if p["id"]==case["id"]),None)
            if not revision: continue
            case={**case,"page":revision["page"],"end_page":revision["end_page"],"input_text":revision["new_text"]}
        pdf=pdfium.PdfDocument(FOLDER / sources[case["paper_id"]]["pdf_path"])
        for physical_page in range(case["page"],case["end_page"]+1):
            path=output / (case["id"]+(f"_revision_p{physical_page}" if args.revisions else "")+".png")
            pdf[physical_page-1].render(scale=1.3).to_pil().save(path)
            sample.append({"id":case["id"],"parent_doi":case["parent_doi"],"page":physical_page,"image":str(path),"input_text":case["input_text"]})
        pdf.close()
    manifest="sample_"+"_".join(args.ids)+".json" if args.ids else "sample.json"
    if args.revisions: manifest="revisions_"+manifest
    (output / manifest).write_text(json.dumps(sample,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps([{k:v for k,v in c.items() if k!="input_text"} for c in sample],indent=2))


if __name__=="__main__":main()
