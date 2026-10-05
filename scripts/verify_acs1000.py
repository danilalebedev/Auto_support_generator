"""Verify frozen inputs and local source files without network or model calls."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from acs1000_annotations import FOLDER, validate_corpus, compile_case
from acs_corpus_v2 import save
from benchmark_acs1000 import load_labels


def main():
    frozen = json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    cases = frozen["cases"]
    stats = validate_corpus(cases)
    digest = hashlib.sha256(json.dumps(cases, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert digest == frozen["dataset_sha256"], "Frozen dataset hash mismatch"
    article_splits = {}
    for case in cases:
        previous = article_splits.setdefault(case["parent_doi"], case["split"])
        assert previous == case["split"], "Article leakage across splits"
    sources = json.loads((FOLDER / "sources.json").read_text(encoding="utf-8"))
    indexed = {str(s["figshare_id"]): s for s in sources}
    for case in cases:
        assert indexed[case["paper_id"]]["parent_doi"] == case["parent_doi"]
    for source in sources:
        path = FOLDER / source["pdf_path"]
        assert path.is_file(), f"Missing PDF: {path}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"], str(path)
    labels = load_labels(cases)
    for case in cases:
        if case["id"] in labels: compile_case(case,labels[case["id"]])
    event_types=Counter()
    tool_items=[]
    for folder in (FOLDER / "annotation_runs",FOLDER / "label_repairs/runs"):
        for path in folder.rglob("annotation-events.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                try: event=json.loads(line)
                except json.JSONDecodeError: continue
                if event.get("type")=="item.completed":
                    kind=event.get("item",{}).get("type","unknown")
                    event_types[kind]+=1
                    if kind in {"command_execution","file_change","mcp_tool_call","web_search","collab_tool_call"}:
                        tool_items.append({"log":str(path.relative_to(FOLDER)),"item_type":kind})
    assert not tool_items, "Annotation independence audit found unexpected tool-use events"
    result = {
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": digest, **stats,
        "split_counts": dict(Counter(c["split"] for c in cases)),
        "pdf_sha256_verified": len(sources), "independent_annotations": len(labels),
        "accepted_annotation_evidence_validated":len(labels),"annotation_completed_item_types":dict(event_types),
        "article_disjoint": True,
        "extraction_flags": dict(Counter(f for c in cases for f in c["extraction_flags"])),
        "limitation": "Integrity verification, not chemical correctness, completeness or parser accuracy.",
    }
    save(FOLDER / "integrity_verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
