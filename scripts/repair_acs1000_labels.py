"""Repair only invalid independent evidence labels, never using parser output."""
import argparse
import json
import shutil
import time
from pathlib import Path

import annotate_acs1000_cli as runner
from acs1000_annotations import FOLDER, INSTRUCTIONS, compile_case, schema
from acs_corpus_v2 import save


REPAIR_INSTRUCTIONS = """
Your earlier annotation failed an exact-source validation check. Correct the
provided cases without using tools or parser predictions. Do not change source text.
An evidence string must include the entity name but MUST NOT claim quantities
belonging to another entity. It may end before a closing parenthesis when needed.
For A (0.3 mmol in THF (1 mL)), use A evidence 'A (0.3 mmol', and THF evidence
'THF (1 mL)'. For A in hexane (2 M, 1 mL, 2 mmol), the stock concentration,
solution volume and amount belong to A, while hexane has evidence 'hexane' only.
If one entity has several additions, include every occurrence, repeating an
identical evidence string if two identical passages both describe reaction additions.
Resolve the listed overlaps/absent snippets; do not force a chemically impossible
ownership merely to pass validation. Keep uncertainties visible in notes.
Return every requested ID exactly once in the same JSON schema.
"""


def sweep(opts):
    corpus=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    indexed={c["id"]:c for c in corpus["cases"]}
    repair_root=FOLDER / "label_repairs"
    save(repair_root / "annotation_schema.json",schema())
    runner.FOLDER=repair_root
    binary=opts.codex_bin or shutil.which("codex.exe") or shutil.which("codex")
    processed=0
    for folder in sorted((FOLDER / "annotation_runs").glob("batch_*")):
        job=repair_root / "runs" / folder.name
        if len(list(job.glob("attempt_*"))) >= 3: continue
        target=FOLDER / "annotations" / (folder.name+".json")
        if target.exists(): continue
        files=list(folder.glob("attempt_*/annotation-last.json"))+list(folder.glob("annotation-last.json"))
        if not files: continue
        source=max(files,key=lambda p:p.stat().st_mtime)
        try: raw=json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError: continue
        manifest=json.loads((folder / "batch_manifest.json").read_text(encoding="utf-8"))
        assert manifest["dataset_sha256"]==corpus["dataset_sha256"]
        assert len(raw["cases"])==len(manifest["ids"])
        assert {r["id"] for r in raw["cases"]}==set(manifest["ids"])
        invalid=[]
        for row in raw["cases"]:
            try: compile_case(indexed[row["id"]],row)
            except Exception as exc:
                invalid.append({"id":row["id"],"input_text":indexed[row["id"]]["input_text"],"earlier_label":row,"validation_error":str(exc)})
        if not invalid:
            if opts.execute_authorized:
                save(target,{"dataset_sha256":corpus["dataset_sha256"],"raw_annotation_source":str(source),**raw})
            continue
        job.mkdir(parents=True,exist_ok=True)
        (job / "prompt.txt").write_text(INSTRUCTIONS+REPAIR_INSTRUCTIONS+json.dumps(invalid,ensure_ascii=False),encoding="utf-8")
        save(job / "batch_manifest.json",{"dataset_sha256":corpus["dataset_sha256"],"ids":[r["id"] for r in invalid],"raw_source":str(source)})
        print(json.dumps({"batch":folder.name,"repair_cases":len(invalid)},ensure_ascii=False),flush=True)
        if opts.execute_authorized:
            if not binary: raise RuntimeError("Codex CLI not found")
            status=runner.run_batch((job,[indexed[r["id"]] for r in invalid]),binary)
            print(json.dumps(status,ensure_ascii=False),flush=True)
            if status["status"] in {"complete","already_complete"}:
                fixed=json.loads((repair_root / "annotations" / (folder.name+".json")).read_text(encoding="utf-8"))
                replacements={r["id"]:r for r in fixed["cases"]}
                rows=[replacements.get(r["id"],r) for r in raw["cases"]]
                for row in rows: compile_case(indexed[row["id"]],row)
                save(target,{"dataset_sha256":corpus["dataset_sha256"],"raw_annotation_source":str(source),"repair_source":str(job),"cases":rows})
        processed+=1
        if opts.limit_batches and processed>=opts.limit_batches: break


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--execute-authorized",action="store_true")
    arg.add_argument("--codex-bin")
    arg.add_argument("--limit-batches",type=int)
    arg.add_argument("--watch",action="store_true",help="Process completed batches while the already-running annotation queue finishes.")
    opts=arg.parse_args()
    if opts.watch and not opts.execute_authorized:
        raise ValueError("--watch requires an explicitly authorized execution")
    started=time.monotonic()
    previous=None
    while True:
        sweep(opts)
        finished=len(list((FOLDER / "annotation_runs").glob("batch_*/status.json")))
        expected=len(list((FOLDER / "annotation_runs").glob("batch_*/batch_manifest.json")))
        accepted=len(list((FOLDER / "annotations").glob("batch_*.json")))
        state={"finished_raw_batches":finished,"total_batches":expected,"accepted_batches":accepted,
               "status":"running" if finished<expected else "complete" if accepted==expected else "needs_manual_review"}
        save(FOLDER / "label_repairs/progress.json",state)
        if state!=previous: print(json.dumps(state),flush=True)
        previous=state
        if not opts.watch or finished>=expected or time.monotonic()-started>14400: break
        time.sleep(30)


if __name__=="__main__": main()
