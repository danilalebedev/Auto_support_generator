"""Audit raw independent labels; never consult parser predictions.

Development details may be printed. Other splits expose only validation errors,
not text or labels, so format repair need not leak the held-out chemistry.
"""
import argparse
import json
from acs1000_annotations import FOLDER, compile_case
from acs_corpus_v2 import save


def audit(accept_valid=False):
    corpus = json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    indexed = {c["id"]:c for c in corpus["cases"]}
    summaries=[]
    for folder in sorted((FOLDER / "annotation_runs").glob("batch_*")):
        files = list(folder.glob("attempt_*/annotation-last.json")) + list(folder.glob("annotation-last.json"))
        if not files: continue
        source=max(files,key=lambda p:p.stat().st_mtime)
        try:
            raw=json.loads(source.read_text(encoding="utf-8"))
            manifest=json.loads((folder / "batch_manifest.json").read_text(encoding="utf-8"))
            assert manifest["dataset_sha256"] == corpus["dataset_sha256"]
            assert len(raw["cases"]) == len(manifest["ids"])
            assert {r["id"] for r in raw["cases"]} == set(manifest["ids"])
        except Exception as exc:
            summaries.append({"batch":folder.name,"error":str(exc)})
            continue
        errors=[]
        repeated=[]
        for row in raw["cases"]:
            try: compile_case(indexed[row["id"]],row)
            except Exception as exc:
                errors.append({"id":row["id"],"reason":str(exc)})
                if indexed[row["id"]]["split"]=="development":
                    print(json.dumps({"id":row["id"],"reason":str(exc),"label":row},ensure_ascii=False))
                else: print(row["id"],"validation error; non-development details hidden")
            for entity in row["entities"]:
                for evidence in set(entity["evidence"]):
                    if indexed[row["id"]]["input_text"].count(evidence) > entity["evidence"].count(evidence):
                        repeated.append({"id":row["id"],"evidence":evidence,"issue":"More source occurrences than annotations; may be workup, product or an omitted repeated reaction addition. Review, do not auto-expand."})
        target=FOLDER / "annotations" / (folder.name+".json")
        if accept_valid and not errors and not target.exists():
            save(target,{"dataset_sha256":corpus["dataset_sha256"],"raw_annotation_source":str(source),**raw})
        summaries.append({"batch":folder.name,"raw_source":str(source),"cases":len(raw["cases"]),"errors":errors,"repeated_evidence_checks":repeated})
    save(FOLDER / "annotation_audit.json",summaries)
    print(json.dumps({"raw_batches":len(summaries),"invalid_cases":sum(len(s.get("errors",[])) for s in summaries)}))
    return summaries


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--accept-valid",action="store_true")
    audit(parser.parse_args().accept_valid)
