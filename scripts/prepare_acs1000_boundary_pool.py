"""Freeze source-only corrections for independent annotation alongside raw jobs.

This is an annotation work pool, not a second accuracy benchmark. Curation may
reuse a label only when both its PDF identity and complete source hash match.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from acs1000_annotations import FOLDER
from acs_corpus_v2 import save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="boundary_annotation_pool")
    parser.add_argument("--exclude-pool",action="append",default=[])
    args=parser.parse_args()
    parent=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    proposals=json.loads((FOLDER / "boundary_revision_proposals.json").read_text(encoding="utf-8"))
    assert parent["dataset_sha256"]==proposals["parent_dataset_sha256"]
    indexed={c["id"]:c for c in parent["cases"]}
    excluded=set()
    for name in args.exclude_pool:
        prior=json.loads((FOLDER / name / "frozen_inputs.json").read_text(encoding="utf-8"))
        excluded.update((c["paper_id"],c["text_sha256"]) for c in prior["cases"])
    cases=[]
    seen=set()
    for proposal in proposals["proposals"]:
        old=indexed[proposal["id"]]
        identity=(old["paper_id"],proposal["new_sha256"])
        if identity in seen or identity in excluded: continue
        seen.add(identity)
        cases.append({**old,"id":f"ACSFIX-{len(cases)+1:04d}","parent_case_id":old["id"],
                      "page":proposal["page"],"end_page":proposal["end_page"],
                      "input_text":proposal["new_text"],"text_sha256":proposal["new_sha256"],
                      "annotation_status":"pending"})
    digest=hashlib.sha256(json.dumps(cases,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    counts=Counter(c["parent_doi"] for c in cases)
    result={"created_utc":datetime.now(timezone.utc).isoformat(),"dataset_sha256":digest,
            "parent_dataset_sha256":parent["dataset_sha256"],"purpose":"Independent annotation pool, not an accuracy evaluation dataset",
            "source_cache_root":str(FOLDER),"extractor_sha256":proposals["extractor_sha256"],
            "stats":{"cases":len(cases),"papers":len(counts),"max_per_paper":max(counts.values())},
            "split_counts":dict(Counter(c["split"] for c in cases)),"cases":cases}
    path=FOLDER / args.output / "frozen_inputs.json"
    if path.exists():
        existing=json.loads(path.read_text(encoding="utf-8"))
        if existing["dataset_sha256"]!=digest: raise ValueError("Annotation pool is frozen; use a separately versioned pool for further corrections")
    else: save(path,result)
    print(json.dumps({"folder":str(path.parent),"dataset_sha256":digest,**result["stats"]},indent=2))


if __name__=="__main__":main()
