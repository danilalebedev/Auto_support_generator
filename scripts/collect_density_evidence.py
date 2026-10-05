"""Bulk-download PubChem density annotations, keeping provenance and raw units.

Evidence is not silently treated as neat-liquid density: records may describe
solids, solutions, gases, ranges, or relative density. Only curated_properties
contains values approved for automatic volume calculations.
"""
import json
from build_reagent_catalog import get_json, OUTPUT


def main():
    selected = {r["cid"] for r in json.loads((OUTPUT / "catalog.json").read_text(encoding="utf-8"))["compounds"]}
    evidence = {}
    page,total = 1,1
    while page <= total:
        response = get_json(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/JSON?heading=Density&heading_type=Compound&page={page}",f"bulk_density_{page:02d}")["Annotations"]
        total = response["TotalPages"]
        for annotation in response["Annotation"]:
            cids = selected.intersection(annotation.get("LinkedRecords",{}).get("CID",[]))
            if not cids: continue
            facts = []
            for datum in annotation.get("Data",[]):
                for value in datum.get("Value",{}).get("StringWithMarkup",[]):
                    facts.append({"text":value["String"],"references":datum.get("Reference",[])})
            if not facts: continue
            row = {"source_name":annotation.get("SourceName"),"source_url":annotation.get("URL"),"license_url":annotation.get("LicenseURL"),
                   "source_record_name":annotation.get("Name"),"facts":facts,"status":"unreviewed_density_evidence"}
            for cid in cids: evidence.setdefault(str(cid),[]).append(row)
        print(f"Density page {page}/{total}: {len(evidence)} catalog compounds with evidence",flush=True)
        page += 1
    payload = {"schema_version":"1.0","retrieved_date":"2026-10-05","compound_count":len(evidence),
               "policy":"These are source assertions, not approved calculation constants. Temperature, material form and units require review.","by_cid":evidence}
    (OUTPUT / "density_evidence.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")


if __name__ == "__main__": main()
