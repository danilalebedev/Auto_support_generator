"""Download openly available ACS SI and retain page-level provenance.

This script only collects candidate passages. It does NOT create gold labels.
Gold annotations are authored separately after reading the saved PDF text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "output" / "acs_benchmark"
TOPICS = ["total synthesis", "photoredox", "cross-coupling", "borylation", "amination", "fluorination", "oxidation", "cyclization"]


def request_json(url: str, payload: dict | None = None) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": "AutoSupportGenerator-research/1.0", "Content-Type": "application/json"},
                                     data=json.dumps(payload).encode() if payload else None)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def download(url: str, path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as target:
        while block := response.read(1024 * 1024):
            target.write(block)
    temp.replace(path)


def collect(folder: Path, per_topic: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "sources.json"
    sources = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    seen = {source["article_doi"] for source in sources}
    for topic in TOPICS:
        existing = sum(source["search_topic"] == topic for source in sources)
        if existing >= per_topic:
            continue
        entries = request_json("https://api.figshare.com/v2/articles/search", {
            "search_for": '"' + topic + '"', "page_size": 100, "order": "published_date", "order_direction": "desc"})
        for entry in entries:
            doi = entry.get("doi", "")
            article_doi = re.sub(r"\.s\d+$", "", doi)
            if not doi.startswith("10.1021/") or not doi.endswith(".s001") or article_doi in seen:
                continue
            if not any(journal in doi for journal in ("orglett", "joc.", "jacs.", "acscatal", "acs.org", "acs.chem")):
                continue
            if entry.get("published_date", "9999")[:10] > "2026-10-05":
                continue
            meta = request_json(entry["url"])
            pdfs = [file for file in meta["files"] if file["name"].endswith(".pdf") and file["size"] < 45_000_000]
            if not pdfs:
                continue
            file = pdfs[0]
            source_id = f"S{len(sources)+1:02d}"
            target = folder / "pdfs" / f"{source_id}_{file['name']}"
            try:
                download(file["download_url"], target)
                checksum = hashlib.md5(target.read_bytes()).hexdigest()
                if checksum != file["computed_md5"]:
                    raise ValueError("MD5 mismatch")
                reader = PdfReader(target)
                pages = [{"page": index+1, "text": page.extract_text(extraction_mode="layout")} for index, page in enumerate(reader.pages[:50])]
            except Exception as exc:
                print(f"SKIP {doi}: {exc}", flush=True)
                continue
            text_file = folder / "pages" / f"{source_id}.json"
            text_file.parent.mkdir(exist_ok=True)
            text_file.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
            source = {"source_id": source_id, "article_doi": meta.get("resource_doi") or article_doi,
                      "si_doi": doi, "title": re.sub(r"\s+", " ", meta["title"]), "search_topic": topic,
                      "figshare_id": meta["id"], "source_url": meta["url_public_html"], "download_url": file["download_url"],
                      "license": meta["license"], "pdf_path": str(target.relative_to(folder)),
                      "md5": checksum, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                      "page_count": len(reader.pages), "text_pages": len(pages), "retrieved_date": "2026-10-05",
                      "authors": [a["full_name"] for a in meta.get("authors", [])]}
            sources.append(source)
            seen.add(article_doi)
            manifest_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{source_id} {topic}: {source['title']} ({len(reader.pages)} pages)", flush=True)
            existing += 1
            if existing >= per_topic:
                break


def restore_from_manifest(folder: Path) -> None:
    """Reproduce the pinned corpus without running a changing literature search."""
    for source in json.loads((folder / "sources.json").read_text(encoding="utf-8")):
        target = folder / source["pdf_path"]
        download(source["download_url"], target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"PDF checksum mismatch: {source['source_id']}")
        reader = PdfReader(target)
        pages = [{"page": index+1, "text": page.extract_text(extraction_mode="layout")} for index, page in enumerate(reader.pages[:source["text_pages"]])]
        page_path = folder / "pages" / f"{source['source_id']}.json"
        page_path.parent.mkdir(exist_ok=True)
        page_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Verified {source['source_id']}", flush=True)


def candidates(folder: Path) -> None:
    records = []
    for source in json.loads((folder / "sources.json").read_text(encoding="utf-8")):
        source_id = source["source_id"]
        for page in json.loads((folder / "pages" / f"{source_id}.json").read_text(encoding="utf-8")):
            for block in re.split(r"\n\s*\n", page["text"]):
                text = re.sub(r"\s+", " ", block).strip()
                if len(text) < 150 or len(text) > 5000:
                    continue
                if not re.search(r"\b(?:added|stirred|dissolved|charged|heated|cooled|treated|irradiated)\b", text, re.I):
                    continue
                if len(re.findall(r"\d\s*(?:mg|mmol|mL|equiv|mol%)", text)) < 2:
                    continue
                records.append({"candidate_id": f"{source_id}-P{page['page']:02d}-B{len(records)+1:03d}",
                                "source_id": source_id, "page": page["page"], "text": text})
    (folder / "candidates.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "candidate_index.txt").write_text("\n\n".join(f"{r['candidate_id']}\n{r['text']}" for r in records), encoding="utf-8")
    print(f"Collected {len(records)} candidate passages from {len(set(r['source_id'] for r in records))} papers", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, default=DEFAULT)
    parser.add_argument("--per-topic", type=int, default=2)
    parser.add_argument("--candidates-only", action="store_true")
    parser.add_argument("--from-manifest", action="store_true")
    args = parser.parse_args()
    if args.from_manifest:
        restore_from_manifest(args.folder)
    elif not args.candidates_only:
        collect(args.folder, args.per_topic)
    candidates(args.folder)
