"""Write an inspectable status snapshot of the long-running local benchmark."""
import json
from collections import Counter
from datetime import datetime, timezone
from acs1000_annotations import FOLDER
from acs_corpus_v2 import save
from benchmark_acs1000 import load_labels, evaluation_lock


def main():
    corpus=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    labels=load_labels(corpus["cases"])
    jobs=list((FOLDER / "annotation_runs").glob("batch_*/batch_manifest.json"))
    finished=list((FOLDER / "annotation_runs").glob("batch_*/status.json"))
    statuses=[]
    for path in finished:
        try: statuses.append(json.loads(path.read_text(encoding="utf-8"))["status"])
        except (KeyError,json.JSONDecodeError): pass
    usage=Counter()
    for parent in (FOLDER / "annotation_runs",FOLDER / "label_repairs/runs"):
        for path in parent.rglob("annotation-events.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                try: event=json.loads(line)
                except json.JSONDecodeError: continue
                if event.get("type")=="turn.completed":
                    usage.update({k:v for k,v in event.get("usage",{}).items() if isinstance(v,int)})
    evaluations={}
    for split in ("all","holdout"):
        path=FOLDER / f"results_{split}.json"
        if not path.exists(): continue
        report=json.loads(path.read_text(encoding="utf-8"))
        if report.get("dataset_sha256")!=corpus["dataset_sha256"]: continue
        try: evaluation_lock(corpus,labels)
        except RuntimeError: continue
        evaluations[split]=report["summary"]
    state={
        "snapshot_utc":datetime.now(timezone.utc).isoformat(),
        "objective.status":"in_progress",
        "dataset.sha256":corpus["dataset_sha256"],
        "dataset.candidate_passages":len(corpus["cases"]),
        "dataset.papers":corpus["stats"]["papers"],
        "dataset.max_per_paper":corpus["stats"]["max_per_paper"],
        "dataset.complete_procedures_verified":False,
        "node.collection.status":"complete",
        "node.source_quality.status":"needs_review",
        "node.annotation.status":"complete_silver" if len(labels)==len(corpus["cases"]) else "running",
        "annotation.accepted_cases":len(labels),
        "annotation.eligibility_counts":dict(Counter(r["eligibility"] for r in labels.values())),
        "annotation.total_batches":len(jobs),
        "annotation.raw_batch_statuses":dict(Counter(statuses)),
        "annotation.user_authorized_cli":True,
        "annotation.confirmed_completed_turn_usage":dict(usage),
        "node.evaluation.full_corpus_accuracy":evaluations.get("all"),
        "node.evaluation.held_out_agreement":evaluations.get("holdout"),
        "node.evaluation.note":"Agreement with independent LLM silver labels, not expert chemical accuracy." if evaluations else "No full-corpus accuracy claim until independent labels, source curation and article-disjoint evaluation are complete.",
        "next.action":"chemist validation and product-mode decision; do not tune on the opened holdout" if evaluations else "finish independent annotation, curate sources, develop on development only, freeze parser, then evaluate validation and holdout",
    }
    save(FOLDER / "state.json",state)
    print(json.dumps(state,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
