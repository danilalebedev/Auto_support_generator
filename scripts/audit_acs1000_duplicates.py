"""Source-only near-duplicate audit. Does not change the frozen article split."""
import json
import re
from acs1000_annotations import FOLDER
from acs_corpus_v2 import save


def shingles(text, width=5):
    normalized=re.sub(r"\d+(?:[.,]\d+)?", "#", text.casefold())
    words=re.findall(r"\w+|#",normalized)
    return {tuple(words[i:i+width]) for i in range(max(0,len(words)-width+1))}


def audit(cases, threshold=.90):
    signatures=[shingles(c["input_text"]) for c in cases]
    pairs=[]
    for i,a in enumerate(signatures):
        if not a: continue
        for j in range(i+1,len(cases)):
            if cases[i]["parent_doi"]==cases[j]["parent_doi"]: continue
            b=signatures[j]
            if not b or min(len(a),len(b))/max(len(a),len(b))<threshold: continue
            common=len(a & b)
            similarity=common/(len(a)+len(b)-common)
            if similarity>=threshold:
                pairs.append({"left":cases[i]["id"],"right":cases[j]["id"],"similarity":similarity,
                              "cross_split":cases[i]["split"]!=cases[j]["split"]})
    return pairs


def main():
    corpus=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    pairs=audit(corpus["cases"])
    report={"dataset_sha256":corpus["dataset_sha256"],"method":"Jaccard of number-normalized five-token shingles, threshold 0.90; cross-paper pairs only",
            "cross_paper_pairs":len(pairs),"cross_split_pairs":sum(p["cross_split"] for p in pairs),"pairs":pairs,
            "limitation":"This lexical audit does not rule out paraphrases, shared reaction families or structure-only duplicates."}
    save(FOLDER / "near_duplicate_audit.json",report)
    print(json.dumps({k:v for k,v in report.items() if k!="pairs"},indent=2))


if __name__=="__main__": main()
