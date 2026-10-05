"""Prepare a separate source-boundary revision; never mutate frozen inputs/labels."""
import hashlib
import json
from pathlib import Path
from acs1000_annotations import FOLDER
from acs_corpus_v2 import passage_candidates, save


def main():
    corpus=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    by_paper={}
    cache=Path(corpus.get("source_cache_root",str(FOLDER)))
    proposals=[]
    ambiguous=[]
    for case in corpus["cases"]:
        paper=case["paper_id"]
        if paper not in by_paper:
            pages=json.loads((cache / "pages" / (paper+".json")).read_text(encoding="utf-8"))
            by_paper[paper]=passage_candidates(pages,limit=None,join_blocks=True)
        text=case["input_text"]
        matches=[c for c in by_paper[paper] if c["page"]<=case["page"]<=c["end_page"] and
                 (text in c["input_text"] or c["input_text"] in text)]
        exact=[c for c in matches if c["input_text"]==text]
        if exact: continue
        if len(matches)!=1:
            ambiguous.append(case["id"])
            continue
        candidate=matches[0]
        proposals.append({"id":case["id"],"paper_id":paper,"parent_doi":case["parent_doi"],
                          "old_sha256":case["text_sha256"],"new_sha256":candidate["text_sha256"],
                          "page":candidate["page"],"end_page":candidate["end_page"],
                          "old_text":text,"new_text":candidate["input_text"],"needs_fresh_annotation":True})
    report={"parent_dataset_sha256":corpus["dataset_sha256"],
            "extractor_sha256":hashlib.sha256(__import__('pathlib').Path(__file__).with_name('acs_corpus_v2.py').read_bytes()).hexdigest(),
            "frozen_corpus_modified":False,"proposal_count":len(proposals),
            "unmatched_or_ambiguous_ids":ambiguous,"proposals":proposals}
    save(FOLDER / "boundary_revision_proposals.json",report)
    print(json.dumps({k:v for k,v in report.items() if k not in {"proposals","unmatched_or_ambiguous_ids"}},indent=2))
    print("Ambiguous/unmatched source boundary mappings:",len(ambiguous))


if __name__=="__main__": main()
