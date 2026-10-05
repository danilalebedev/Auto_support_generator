"""Create a new corpus version from source corrections and independent eligibility.

Never overwrite the parent corpus; never use parser success to select examples.
Only byte-identical procedure texts may inherit their independent annotation.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import acs_corpus_v2 as collector
from acs1000_annotations import FOLDER, ROOT, compile_case, validate_corpus
from acs_corpus_v2 import passage_candidates, save
from benchmark_acs1000 import load_labels, split_cases


def fingerprint(text):
    return re.sub(r"\W+", "", re.sub(r"\d+(?:\.\d+)?", "#", text.casefold()))


def independent_exclusion(label, *, has_source_correction=False):
    if label["eligibility"]=="not_synthesis":
        return "independent_not_synthesis_label"
    # A source correction gets a fresh independent judgment. Never exclude a
    # difficult but complete multistage/variant procedure for parser performance.
    if not has_source_correction and re.search(
        r"\btruncat\w*|\bfragmentary\b|\bincomplete\s+(?:reaction\s+)?(?:fragment|procedure|recipe)\b|"
        r"\b(?:text|passage|sentence)\s+(?:begins|ends)\s+mid[- ]|"
        r"\b(?:initial|opening)\s+(?:reaction\s+)?(?:substrates?|charges?|reactants?)\b[^.;]{0,35}\bmissing\b",
        label["notes"],re.I):
        return "independent_incomplete_source_label"
    return None


def select_replacement(pool, previous, counts, used, rejected):
    eligible=[c for c in pool if counts[c["parent_doi"]]<5
              and not c["extraction_flags"]
              and fingerprint(c["input_text"]) not in used and c["text_sha256"] not in rejected]
    if not eligible: return None
    return min(eligible,key=lambda c:(c["parent_doi"]!=previous["parent_doi"],len(c["extraction_flags"]),
                                     abs(c["page"]-previous["page"]),c["paper_id"],c["page"]))


def load_pool(cache):
    sources={}
    pool=[]
    for path in sorted((cache / "papers").glob("*.json")):
        record=json.loads(path.read_text(encoding="utf-8"))
        pages=cache / "pages" / (str(record["figshare_id"])+".json")
        if record.get("status")!="collected" or not pages.exists(): continue
        sources[str(record["figshare_id"])]=record
        for candidate in passage_candidates(json.loads(pages.read_text(encoding="utf-8")),limit=None,join_blocks=True):
            pool.append({**candidate,"parent_doi":record["parent_doi"],"paper_id":str(record["figshare_id"])})
    return sources,pool


def load_boundary_labels(parent_sha):
    labels={}
    for folder in sorted(FOLDER.glob("boundary_annotation_pool*")):
        path=folder / "frozen_inputs.json"
        if not path.exists(): continue
        corpus=json.loads(path.read_text(encoding="utf-8"))
        assert corpus["parent_dataset_sha256"]==parent_sha
        cases={c["id"]:c for c in corpus["cases"]}
        pool_labels={}
        for annotation in sorted((folder / "annotations").glob("*.json")):
            batch=json.loads(annotation.read_text(encoding="utf-8"))
            assert batch["dataset_sha256"]==corpus["dataset_sha256"]
            for label in batch["cases"]:
                case=cases[label["id"]]
                compile_case(case,label)
                identity=(case["paper_id"],case["text_sha256"])
                if identity in labels or identity in pool_labels: raise ValueError("Duplicate boundary-pool label")
                pool_labels[identity]=label
        if len(pool_labels)!=len(cases):
            raise RuntimeError(f"Wait for all independent annotations in {folder.name} before curation")
        labels.update(pool_labels)
    return labels


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--output",type=Path)
    arg.add_argument("--allow-additional-downloads",action="store_true")
    opts=arg.parse_args()
    output=(opts.output or FOLDER / "curated_v3").resolve()
    if output==FOLDER or (output / "frozen_inputs.json").exists():
        raise ValueError("Choose a fresh output directory; existing corpus versions are immutable")
    parent=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    validate_corpus(parent["cases"])
    labels=load_labels(parent["cases"])
    if len(labels)!=len(parent["cases"]):
        raise RuntimeError("Curation waits for complete independent labels; do not curate only the easy/early batches")
    cache=Path(parent.get("source_cache_root",str(FOLDER))).resolve()
    revision_path=FOLDER / "boundary_revision_proposals.json"
    proposals=json.loads(revision_path.read_text(encoding="utf-8")) if revision_path.exists() else {"parent_dataset_sha256":parent["dataset_sha256"],"proposals":[]}
    assert proposals["parent_dataset_sha256"]==parent["dataset_sha256"]
    revised={p["id"]:p for p in proposals["proposals"]}
    boundary_labels=load_boundary_labels(parent["dataset_sha256"])
    sources,pool=load_pool(cache)
    updated=[]
    rejected={sha for (_,sha),label in boundary_labels.items() if independent_exclusion(label)}
    changes=[]
    replacement_reasons={}
    restored_fingerprints=set()
    for old in parent["cases"]:
        correction=revised.get(old["id"])
        reviewed_correction=boundary_labels.get((old["paper_id"],correction["new_sha256"])) if correction else None
        exclusion=independent_exclusion(reviewed_correction or labels[old["id"]],has_source_correction=bool(correction and not reviewed_correction))
        if exclusion:
            rejected.add(old["text_sha256"])
            replacement_reasons[old["id"]]=exclusion
            updated.append(None)
            continue
        case=dict(old)
        if old["id"] in revised:
            correction=revised[old["id"]]
            assert correction["old_sha256"]==old["text_sha256"]
            assert hashlib.sha256(correction["new_text"].encode()).hexdigest()==correction["new_sha256"]
            case.update(input_text=correction["new_text"],text_sha256=correction["new_sha256"],page=correction["page"],end_page=correction["end_page"])
            flags=[]
            if case["input_text"][-1] not in ".):;": flags.append("possible_page_or_block_truncation")
            if case["input_text"].count("(")!=case["input_text"].count(")"): flags.append("unbalanced_parentheses")
            case["extraction_flags"]=flags
            changes.append({"parent_id":old["id"],"reason":"source_boundary_correction"})
        normalized=fingerprint(case["input_text"])
        boundary_label=boundary_labels.get((case["paper_id"],case["text_sha256"]))
        if boundary_label and independent_exclusion(boundary_label):
            rejected.add(case["text_sha256"])
            replacement_reasons[old["id"]]="restored_"+independent_exclusion(boundary_label)
            updated.append(None)
            continue
        if normalized in restored_fingerprints:
            rejected.add(old["text_sha256"])
            replacement_reasons[old["id"]]="duplicate_after_source_restoration"
            updated.append(None)
            continue
        restored_fingerprints.add(normalized)
        updated.append(case)
    counts=Counter(c["parent_doi"] for c in updated if c)
    used={fingerprint(c["input_text"]) for c in updated if c}
    discovery=json.loads((cache / "discovery.json").read_text(encoding="utf-8"))
    remaining=iter(e for e in discovery if str(e["figshare_id"]) not in sources)
    downloaded=0
    collector.OUT=cache
    for index,case in enumerate(updated):
        if case is not None: continue
        old=parent["cases"][index]
        replacement=select_replacement(pool,old,counts,used,rejected)
        while replacement is None and opts.allow_additional_downloads and downloaded<30:
            entry=next(remaining,None)
            if entry is None: break
            record=collector.fetch_paper(entry)
            downloaded+=1
            if record.get("status")!="collected": continue
            paper=str(record["figshare_id"])
            sources[paper]=record
            for candidate in record["passages"]:
                pool.append({**candidate,"parent_doi":record["parent_doi"],"paper_id":paper})
            replacement=select_replacement(pool,old,counts,used,rejected)
        if replacement is None:
            raise RuntimeError("No eligible replacement remains under the five-per-paper cap. Parent corpus is unchanged.")
        updated[index]=dict(replacement)
        counts[replacement["parent_doi"]]+=1
        used.add(fingerprint(replacement["input_text"]))
        changes.append({"parent_id":old["id"],"reason":replacement_reasons[old["id"]],"new_parent_doi":replacement["parent_doi"]})
    for index,case in enumerate(updated):
        old=parent["cases"][index]
        case.update(id=f"ACS3-{index+1:04d}",parent_case_id=old["id"],parent_text_sha256=old["text_sha256"],annotation_status="pending")
    cases,duplicates=split_cases(updated)
    # Preserve prior article assignment. In particular, no previously seen
    # development paper can migrate into validation/holdout after curation.
    previous_assignment={c["parent_doi"]:c["split"] for c in parent["cases"]}
    for case in cases:
        if case["parent_doi"] in previous_assignment: case["split"]=previous_assignment[case["parent_doi"]]
    for _ in range(len(duplicates)+1):
        changed=False
        assignments={c["parent_doi"]:c["split"] for c in cases}
        for a,b in duplicates:
            if assignments[a]!=assignments[b]:
                for case in cases:
                    if case["parent_doi"] in {a,b}: case["split"]="development"
                changed=True
        if not changed: break
    stats=validate_corpus(cases)
    digest=hashlib.sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    frozen={"created_utc":datetime.now(timezone.utc).isoformat(),"dataset_sha256":digest,
            "parent_dataset_sha256":parent["dataset_sha256"],"source_cache_root":str(cache),"stats":stats,
            "split_counts":dict(Counter(c["split"] for c in cases)),"normalized_cross_paper_duplicates":duplicates,
            "selection_policy":"Source-only paragraph restoration; replace independently identified non-synthesis/incomplete passages and restoration duplicates, never parser failures. Preserve difficult complete methods and prior article splits; at most five per DOI.","cases":cases}
    transferred=[]
    correction_transfers=0
    for case in cases:
        label=boundary_labels.get((case["paper_id"],case["text_sha256"]))
        if label: correction_transfers+=1
        elif case["text_sha256"]==case["parent_text_sha256"]: label=labels[case["parent_case_id"]]
        if label:
            label={**label,"id":case["id"]}
            compile_case(case,label)
            transferred.append(label)
    selected_sources=[]
    for paper in sorted({c["paper_id"] for c in cases}):
        record={k:v for k,v in sources[paper].items() if k!="passages"}
        record["pdf_path"]=os.path.relpath(cache / record["pdf_path"],output)
        selected_sources.append(record)
    save(output / "inputs.json",cases)
    save(output / "sources.json",selected_sources)
    save(output / "frozen_inputs.json",frozen)
    save(output / "annotations/transferred_parent.json",{"dataset_sha256":digest,"parent_dataset_sha256":parent["dataset_sha256"],"transfer_policy":"Exact source-text SHA256 and PDF identity equality only, from parent or independent boundary pool; IDs remapped without semantic edits","cases":transferred})
    snapshot=output / "snapshots"
    snapshot.mkdir(exist_ok=True)
    shutil.copy2(FOLDER / "snapshots/parser_before_1000.py",snapshot / "parser_before_1000.py")
    save(output / "curation_log.json",{"parent_corpus":str(FOLDER),"changes":changes,"transferred_labels":len(transferred),"boundary_pool_label_transfers":correction_transfers,"fresh_annotations_required":len(cases)-len(transferred),"additional_pdfs_attempted":downloaded})
    print(json.dumps({"output":str(output),**stats,"split_counts":frozen["split_counts"],"transferred_labels":len(transferred),"fresh_annotations_required":len(cases)-len(transferred)},indent=2))


if __name__=="__main__": main()
