"""Prepare/replay independent annotation batches using the installed Codex CLI.

Default is prepare-only. Execution must be explicitly authorized by the user;
the harness never substitutes parser predictions for missing reference labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acs1000_annotations import FOLDER, INSTRUCTIONS, compile_case, schema
from acs_corpus_v2 import save


def prepare(batch_size, missing_only=False):
    corpus = json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    if batch_size < 1: raise ValueError("Batch size must be positive")
    cases=corpus["cases"]
    if missing_only:
        covered=set()
        for path in (FOLDER / "annotations").glob("*.json"):
            raw=json.loads(path.read_text(encoding="utf-8"))
            if raw.get("dataset_sha256")!=corpus["dataset_sha256"]: raise ValueError("Existing annotation corpus mismatch")
            for row in raw["cases"]:
                if row["id"] in covered: raise ValueError("Duplicate existing annotation")
                covered.add(row["id"])
        cases=[c for c in cases if c["id"] not in covered]
    batches = []
    save(FOLDER / "annotation_schema.json",schema())
    for offset in range(0,len(cases),batch_size):
        batch = cases[offset:offset+batch_size]
        number = offset//batch_size+1
        identity=hashlib.sha256("|".join(c["id"] for c in batch).encode()).hexdigest()[:12]
        folder = FOLDER / "annotation_runs" / (f"batch_missing_{identity}" if missing_only else f"batch_{number:03d}")
        folder.mkdir(parents=True,exist_ok=True)
        prompt = INSTRUCTIONS + "\nINPUT CASES:\n"+json.dumps([{k:c[k] for k in ("id","input_text")} for c in batch],ensure_ascii=False)
        manifest={"dataset_sha256":corpus["dataset_sha256"],"ids":[c["id"] for c in batch],"label_source":"independent Codex CLI, no parser output provided"}
        manifest_path=folder / "batch_manifest.json"
        if manifest_path.exists():
            previous=json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous["dataset_sha256"]!=manifest["dataset_sha256"] or previous["ids"]!=manifest["ids"]:
                raise ValueError("Refusing to overwrite a batch from another corpus or partition")
        else:
            (folder / "prompt.txt").write_text(prompt,encoding="utf-8")
            save(manifest_path,manifest)
        batches.append((folder,batch))
    return batches


def run_batch(task, binary):
    folder,cases = task
    target = FOLDER / "annotations" / (folder.name+".json")
    manifest=json.loads((folder / "batch_manifest.json").read_text(encoding="utf-8"))
    if target.exists():
        saved=json.loads(target.read_text(encoding="utf-8"))
        if saved.get("dataset_sha256") != manifest["dataset_sha256"]:
            raise ValueError("Existing annotation belongs to a different corpus")
        if {r["id"] for r in saved["cases"]} != {c["id"] for c in cases}:
            raise ValueError("Existing annotation belongs to a different batch")
        return {"batch":folder.name,"status":"already_complete"}
    # A retry must not overwrite evidence from a failed request.
    attempt_number = 1
    while (folder / f"attempt_{attempt_number:03d}").exists(): attempt_number += 1
    attempt = folder / f"attempt_{attempt_number:03d}"
    attempt.mkdir()
    final = attempt / "annotation-last.json"
    commands = [binary,"exec","--json","--skip-git-repo-check","--color","never","--sandbox","read-only",
                "-C",str(folder),"--output-schema",str(FOLDER / "annotation_schema.json"),"-o",str(final),"-"]
    save(attempt / "command.json",commands)
    with (attempt / "annotation-events.jsonl").open("w",encoding="utf-8") as events, (attempt / "stderr.log").open("w",encoding="utf-8") as errors:
        process = subprocess.Popen(commands,stdin=subprocess.PIPE,stdout=events,stderr=errors,text=True,encoding="utf-8",
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        try:
            process.communicate((folder / "prompt.txt").read_text(encoding="utf-8"),timeout=1200)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            result={"batch":folder.name,"status":"blocked","reason":"Codex batch timeout"}
            save(attempt / "status.json",result)
            save(folder / "status.json",result)
            return result
    if process.returncode or not final.exists():
        result={"batch":folder.name,"status":"blocked","reason":f"Codex failed with return code {process.returncode}; see stderr.log"}
    else:
        try:
            raw=json.loads(final.read_text(encoding="utf-8"))
            indexed={r["id"]:r for r in raw["cases"]}
            assert len(indexed)==len(raw["cases"])
            assert set(indexed)=={c["id"] for c in cases},"Missing/unexpected case IDs"
            for case in cases: compile_case(case,indexed[case["id"]])
            save(target,{"dataset_sha256":manifest["dataset_sha256"],**raw})
            result={"batch":folder.name,"status":"complete","cases":len(cases)}
        except Exception as exc:
            result={"batch":folder.name,"status":"needs_label_repair","reason":str(exc)}
    result["attempt_directory"]=str(attempt)
    save(attempt / "status.json",result)
    save(folder / "status.json",result)
    return result


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--batch-size",type=int,default=20)
    arg.add_argument("--missing-only",action="store_true",help="Prepare only IDs without accepted labels, with stable non-colliding batch names.")
    arg.add_argument("--workers",type=int,default=2)
    arg.add_argument("--execute-authorized",action="store_true",help="Use only after explicit human authorization to start Codex jobs.")
    arg.add_argument("--limit-batches",type=int)
    arg.add_argument("--codex-bin",default=os.environ.get("CODEX_BIN"))
    opts=arg.parse_args()
    tasks=prepare(opts.batch_size, opts.missing_only)
    if opts.limit_batches: tasks=tasks[:opts.limit_batches]
    if not opts.execute_authorized:
        print(f"Prepared {len(tasks)} batches; no Codex jobs executed.")
        return
    binary=opts.codex_bin or shutil.which("codex.exe") or shutil.which("codex")
    if not binary: raise RuntimeError("Codex CLI unavailable; provide --codex-bin.")
    # Do not submit the entire queue against unavailable authentication/network.
    completed = [t for t in tasks if (FOLDER / "annotations" / (t[0].name+".json")).exists()]
    if tasks:
        first = completed[0] if completed else tasks[0]
        status = run_batch(first, binary)
        print(json.dumps(status,ensure_ascii=False),flush=True)
        if status["status"] not in {"complete","already_complete"}:
            raise SystemExit("Annotation queue stopped after unsuccessful preflight batch.")
        tasks = [t for t in tasks if t != first]
    with ThreadPoolExecutor(max_workers=min(opts.workers,3)) as pool:
        for future in as_completed([pool.submit(run_batch,t,binary) for t in tasks]):
            print(json.dumps(future.result(),ensure_ascii=False),flush=True)


if __name__=="__main__": main()
