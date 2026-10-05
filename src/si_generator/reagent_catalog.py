"""Exact, offline chemical identity lookup with provenance and ambiguity handling."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

RESOURCE = Path(__file__).parent / "resources" / "reagents"


@lru_cache(maxsize=1)
def _density_evidence() -> dict[str, Any]:
    path = RESOURCE / "density_evidence.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"compound_count": 0, "by_cid": {}}


def normalize_reagent_name(name: str) -> str:
    value = name.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")).casefold().strip()
    value = re.sub(r"^(?:(?:dry|anhydrous|anhyd\.?|degassed|freshly|distilled|deaerated|glacial|base)\s+)+", "", value)
    value = re.sub(r"-\s+", "-", value)
    return re.sub(r"\s+", "", value).replace("·", ".")


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    source = RESOURCE / "catalog.json"
    if not source.exists():
        return {}, {"compound_count": 0, "available": False}
    data = json.loads(source.read_text(encoding="utf-8"))
    overrides_path = RESOURCE / "curated_properties.json"
    curated = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    index: dict[str, list[dict[str, Any]]] = {}
    for record in data["compounds"]:
        record.update(curated.get("by_cid", {}).get(str(record["cid"]), {}))
        for name in record["aliases"]:
            bucket = index.setdefault(normalize_reagent_name(name), [])
            if not any(r["cid"] == record["cid"] for r in bucket):
                bucket.append(record)
    # Curator-verified identities override misleading PubChem name resolutions.
    for record in curated.get("identity_overrides", []):
        for name in record["aliases"]:
            index[normalize_reagent_name(name)] = [record]
    return index, {"compound_count":data["compound_count"], "available":True, "ranking_source":data["ranking_source"],
                   "density_count":len(curated.get("by_cid", {})), "identity_overrides":len(curated.get("identity_overrides", [])),
                   "unreviewed_density_evidence_count":_density_evidence()["compound_count"]}


def lookup_reagent(name: str) -> dict[str, Any]:
    index, _ = _load()
    normalized = normalize_reagent_name(name)
    # Never silently turn a solution, dispersion, supported catalyst, hydrate
    # of unspecified stoichiometry, or vague abbreviation into a neat reagent.
    if re.search(r"\b(?:solution|dispersion|aqueous)\b|\d\s*%|/C\b|·xH2O|\.xH2O", name, re.I):
        return {"status":"formulation", "record":None}
    if normalized in {"dbp", "ether", "petroleumether", "hexanes", "pd/c"}:
        return {"status":"ambiguous", "record":None}
    matches = index.get(normalized, [])
    if not matches:
        return {"status":"not_found", "record":None}
    if len(matches) > 1:
        # Prefer a specifically curated laboratory alias only when the exact
        # key belongs to a single validated core identity.
        core = [r for r in matches if r.get("core_reagent")]
        if len(core) == 1:
            matches = core
        else:
            return {"status":"ambiguous", "record":None, "candidate_cids":[r["cid"] for r in matches]}
    record = dict(matches[0])
    record["density_evidence"] = _density_evidence()["by_cid"].get(str(record.get("cid")), [])
    return {"status":"matched", "record":record}


def catalog_summary() -> dict[str, Any]:
    return dict(_load()[1])
