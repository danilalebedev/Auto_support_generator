"""Article-disjoint, label-gated evaluation of the expanded ACS corpus."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone

from acs1000_annotations import FOLDER, ROOT, compile_case, key, validate_corpus
from acs_corpus_v2 import save
from si_generator.procedure_import import parse_procedure


def pipeline_fingerprints():
    paths = [ROOT / p for p in (
        "src/si_generator/procedure_import.py", "src/si_generator/reagent_catalog.py",
        "scripts/benchmark_acs1000.py", "scripts/acs1000_annotations.py")]
    paths += sorted((ROOT / "src/si_generator/resources/reagents").glob("*.json"))
    return {str(p.relative_to(ROOT)).replace("\\", "/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def evaluation_lock(corpus, labels, *, create=False):
    """Do not let later parser/scorer/label edits masquerade as a held-out test."""
    path = FOLDER / "evaluation_lock.json"
    expected = {"dataset_sha256":corpus["dataset_sha256"], "pipeline_files":pipeline_fingerprints(),
                "labels_sha256":hashlib.sha256(json.dumps(labels,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    if path.exists():
        locked = json.loads(path.read_text(encoding="utf-8"))
        if any(locked.get(k)!=v for k,v in expected.items()):
            raise RuntimeError("Evaluation lock mismatch: code, labels or corpus changed. Do not re-use this holdout for tuning.")
        return locked
    if not create:
        raise RuntimeError("Validation/holdout evaluation requires --lock-evaluation before inspecting results.")
    if len(labels)!=len(corpus["cases"]):
        raise RuntimeError("Complete independent annotations are required before locking evaluation")
    locked = {**expected,"created_utc":datetime.now(timezone.utc).isoformat(),
              "policy":"No parser, scorer or label changes after this lock for the reported held-out evaluation. Development was the only inspected split."}
    save(path,locked)
    return locked


def baseline_parser():
    path = FOLDER / "snapshots/parser_before_1000.py"
    spec = importlib.util.spec_from_file_location("si_generator._baseline1000",path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_procedure


def split_cases(cases):
    legacy = {r["article_doi"].lower() for r in json.loads((ROOT / "output/acs_benchmark/sources.json").read_text(encoding="utf-8"))}
    # Group normalized duplicates across papers, keeping connected papers together.
    dois = sorted({c["parent_doi"] for c in cases})
    parent = {d:d for d in dois}
    def root(d):
        while parent[d]!=d:
            parent[d]=parent[parent[d]]
            d=parent[d]
        return d
    fingerprints = {}
    duplicates = []
    for case in cases:
        fingerprint = re.sub(r"\W+","",re.sub(r"\d+(?:\.\d+)?","#",case["input_text"].casefold()))
        doi = case["parent_doi"]
        if fingerprint in fingerprints and fingerprints[fingerprint]!=doi:
            other = fingerprints[fingerprint]
            parent[root(doi)] = root(other)
            duplicates.append([doi,other])
        fingerprints[fingerprint]=doi
    groups = {}
    for doi in dois: groups.setdefault(root(doi),[]).append(doi)
    assignment = {}
    for group in groups.values():
        digest = hashlib.sha256(("acs1000-v2-split:"+"|".join(sorted(group))).encode()).hexdigest()
        bucket = int(digest[:8],16)%10
        split = "development" if bucket<7 else "validation" if bucket==7 else "holdout"
        if any(d in legacy for d in group): split="development"
        for doi in group: assignment[doi]=split
    return [{**c,"split":assignment[c["parent_doi"]]} for c in cases],duplicates


def freeze():
    inputs = json.loads((FOLDER / "inputs.json").read_text(encoding="utf-8"))
    stats = validate_corpus(inputs)
    path = FOLDER / "frozen_inputs.json"
    if path.exists():
        frozen = json.loads(path.read_text(encoding="utf-8"))
        assert [c["text_sha256"] for c in frozen["cases"]]==[c["text_sha256"] for c in inputs],"Frozen corpus changed"
        return frozen
    cases,duplicates = split_cases(inputs)
    encoded = json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()
    result = {"created_utc":datetime.now(timezone.utc).isoformat(),"dataset_sha256":hashlib.sha256(encoded).hexdigest(),
              "stats":stats,"split_counts":dict(Counter(c["split"] for c in cases)),"normalized_cross_paper_duplicates":duplicates,
              "selection_policy":"No parser-based filtering. Max 5 per DOI, exact text dedup. Article-level split with numeric-normalized duplicate grouping; legacy papers always development.","cases":cases}
    save(path,result)
    return result


def evaluate(case, actual):
    expected = case["expected_entities"]
    predicted = [e for e in actual["chemicals"] if e["role"] not in {"workup","product","equipment"}]
    # The application represents a stock's carrier as a nested property, not
    # another independently dosed table row. Flatten identity only for scoring;
    # never duplicate the stock volume, concentration or amount onto the carrier.
    for chemical in list(predicted):
        carrier = chemical.get("property_sources",{}).get("stock_carrier")
        if carrier and carrier.get("source")=="explicit_text" and not any(key(p["name"])==key(carrier["name"]) for p in predicted):
            predicted.append({"name":carrier["name"], "alias":"carrier_"+chemical["alias"],
                              "role":"solvent", "variable":False, "quantities":[]})
    matched, differences, aliases = set(),[],{}
    q_ok,q_total,role_ok = 0,0,0
    matched_quantity_positions = set()
    for e in expected:
        def compatible_name(p):
            if key(p["name"])==key(e["name"]): return True
            carrier=p.get("property_sources",{}).get("stock_carrier",{}).get("name")
            suffix=" in "+carrier if carrier else ""
            return bool(suffix and p["name"].casefold().endswith(suffix.casefold()) and key(p["name"][:-len(suffix)])==key(e["name"]))
        found = next((p for p in predicted if compatible_name(p) and p["alias"] not in matched),None)
        if found:
            matched.add(found["alias"])
            aliases[found["alias"]]=e["alias"]
            correct_role = found["role"]==e["role"] and found["variable"]==e["variable"]
            role_ok += correct_role
            if not correct_role: differences.append({"type":"role","name":e["name"]})
        else: differences.append({"type":"missing_entity","name":e["name"]})
        for q in e["quantities"]:
            q_total+=1
            candidates = []
            if found:
                # Match every explicitly repeated loading, not just the first scalar.
                candidates = [v["value"] for v in found["quantities"] if v["kind"]==q["field"] and not v["derived"] and v["span"][0]==q["span"][0]]
                if q["field"]=="equivalents":
                    candidates += [v["value"]/100 for v in found["quantities"] if v["kind"]=="percentage" and v["span"][0]==q["span"][0] and re.sub(r"\s+","",v["source_unit"]).lower()=="mol%"]
            good = any(math.isclose(v,q["value"],rel_tol=1e-9,abs_tol=1e-9) for v in candidates)
            q_ok+=good
            if good: matched_quantity_positions.add((found["alias"],q["field"],q["span"][0]))
            if not good: differences.append({"type":"quantity","name":e["name"],"field":q["field"],"expected":q["value"],"actual":candidates})
    differences += [{"type":"extra_entity","name":p["name"]} for p in predicted if p["alias"] not in matched]
    predicted_quantity_positions = set()
    for p in predicted:
        for q in p["quantities"]:
            if q["derived"]: continue
            kind=q["kind"]
            if kind=="percentage" and re.sub(r"\s+","",q["source_unit"]).lower()=="mol%": kind="equivalents"
            if kind not in {"mass_mg","amount_mmol","volume_ml","equivalents","concentration_m"}: continue
            position=(p["alias"],kind,q["span"][0])
            predicted_quantity_positions.add(position)
            if position not in matched_quantity_positions:
                differences.append({"type":"extra_quantity","name":p["name"],"field":kind,"source_start":q["span"][0],"actual":q["value"]})
    canonical = re.sub(r"\{([^{}.]+)\.([^{}]+)\}",lambda m:"{"+aliases.get(m[1],m[1])+"."+m[2]+"}",actual["template_text"])
    exact = canonical==case["target_template"]
    if not exact: differences.append({"type":"template_mismatch"})
    return {"matched_entities":len(matched),"expected_entities":len(expected),"predicted_entities":len(predicted),
            "correct_quantities":q_ok,"total_quantities":q_total,"predicted_quantities":len(predicted_quantity_positions),"correct_roles":role_ok,"template_exact":exact,"all_checks_pass":not differences,"differences":differences}


def aggregate(metrics):
    def total(field): return sum(m[field] for m in metrics)
    return {"cases":len(metrics),"entity_precision":total("matched_entities")/max(1,total("predicted_entities")),
            "entity_recall":total("matched_entities")/max(1,total("expected_entities")),
            "quantity_accuracy":total("correct_quantities")/max(1,total("total_quantities")),
            "quantity_precision":total("correct_quantities")/max(1,total("predicted_quantities")),
            "role_accuracy":total("correct_roles")/max(1,total("expected_entities")),
            "exact_templates":total("template_exact"),"complete_passes":total("all_checks_pass"),
            "error_counts":dict(Counter(d["type"] for m in metrics for d in m["differences"]))}


def load_labels(cases):
    labels = {}
    frozen_path=FOLDER / "frozen_inputs.json"
    digest=json.loads(frozen_path.read_text(encoding="utf-8"))["dataset_sha256"] if frozen_path.exists() else None
    for path in sorted((FOLDER / "annotations").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("dataset_sha256") != digest: raise ValueError(f"Annotation corpus hash mismatch: {path.name}")
        for row in raw["cases"]:
            if row["id"] in labels: raise ValueError(f"Duplicate annotation: {row['id']}")
            labels[row["id"]]=row
    known = {c["id"] for c in cases}
    if set(labels)-known: raise ValueError("Annotations refer to unknown IDs")
    return labels


def regression():
    from benchmark_acs_procedures import compile_targets, evaluate as old_evaluate, aggregate as old_aggregate
    old = baseline_parser()
    cases = compile_targets()
    results = []
    for c in cases:
        before = old(c["input_text"],variable_names=c["variable_names"])
        after = parse_procedure(c["input_text"],variable_names=c["variable_names"])
        results.append({"id":c["id"],"before":old_evaluate(c,before),"after":old_evaluate(c,after)})
    summary = {k:old_aggregate([r[k] for r in results]) for k in ("before","after")}
    save(FOLDER / "legacy_regression.json",{"note":"Old 100 cases used for development; not the new 1000-case held-out test.","summary":summary,"cases":results})
    print(json.dumps(summary,indent=2))


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--freeze",action="store_true")
    arg.add_argument("--regression",action="store_true")
    arg.add_argument("--available-development",action="store_true",help="Diagnostic only: score currently labelled development cases, never a partial holdout.")
    arg.add_argument("--lock-evaluation",action="store_true",help="Freeze code, corpus and all independent labels before validation/holdout; never overwrite an existing lock.")
    arg.add_argument("--split",choices=["development","validation","holdout","all"],default="development")
    opts = arg.parse_args()
    if opts.regression: return regression()
    corpus = freeze()
    if opts.freeze:
        print(json.dumps({k:v for k,v in corpus.items() if k!="cases"},indent=2))
        return
    labels = load_labels(corpus["cases"])
    if opts.lock_evaluation:
        print(json.dumps(evaluation_lock(corpus,labels,create=True),indent=2))
        return
    if opts.available_development and opts.split != "development":
        raise ValueError("Incremental diagnostics are restricted to development")
    selected = [c for c in corpus["cases"] if opts.split=="all" or c["split"]==opts.split]
    missing = [c["id"] for c in selected if c["id"] not in labels]
    total_selected = len(selected)
    if missing and not opts.available_development: raise RuntimeError(f"Evaluation BLOCKED: {len(missing)}/{len(selected)} independent annotations missing. No pseudo-gold scores emitted.")
    if opts.available_development: selected = [c for c in selected if c["id"] in labels]
    if not selected: raise RuntimeError("No independently annotated development cases available")
    lock = evaluation_lock(corpus,labels) if opts.split in {"validation","holdout","all"} else None
    baseline = baseline_parser()
    results = []
    for c in selected:
        target = compile_case(c,labels[c["id"]])
        before = baseline(c["input_text"],variable_names=target["variable_names"])
        after = parse_procedure(c["input_text"],variable_names=target["variable_names"])
        unassisted = parse_procedure(c["input_text"])
        results.append({**target,"baseline":before,"actual":after,"metrics":evaluate(target,after),
                        "baseline_metrics":evaluate(target,before),"unassisted_metrics":evaluate(target,unassisted),
                        "annotation_sha256":hashlib.sha256(json.dumps(labels[c["id"]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()})
    summary = {k:aggregate([r[field] for r in results]) for k,field in [("baseline","baseline_metrics"),("current","metrics"),("unassisted","unassisted_metrics")]}
    by_eligibility={}
    for eligibility in ("clear","review","not_synthesis"):
        subset=[r for r in results if r["eligibility"]==eligibility]
        if subset:
            by_eligibility[eligibility]={k:aggregate([r[field] for r in subset]) for k,field in [("baseline","baseline_metrics"),("current","metrics"),("unassisted","unassisted_metrics")]}
    suffix = opts.split + ("_partial" if opts.available_development else "")
    save(FOLDER / f"results_{suffix}.json",{"dataset_sha256":corpus["dataset_sha256"],"annotation_status":"Independent LLM silver, not expert gold",
         "partial_development_diagnostic":opts.available_development,"coverage":{"evaluated":len(selected),"split_total":total_selected},
         "evaluation_lock_created_utc":lock["created_utc"] if lock else None,"pipeline_files":pipeline_fingerprints(),
         "parser_sha256":hashlib.sha256((ROOT / "src/si_generator/procedure_import.py").read_bytes()).hexdigest(),
         "scorer_sha256":hashlib.sha256((ROOT / "scripts/benchmark_acs1000.py").read_bytes()).hexdigest(),
         "annotation_compiler_sha256":hashlib.sha256((ROOT / "scripts/acs1000_annotations.py").read_bytes()).hexdigest(),
         "eligibility_counts":dict(Counter(r["eligibility"] for r in results)),
         "annotation_quality_flags":dict(Counter(f for r in results for f in r["annotation_quality_flags"])),
         "summary":summary,"by_eligibility":by_eligibility,"cases":results})
    print(json.dumps(summary,indent=2))


if __name__ == "__main__": main()
