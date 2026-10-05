"""Resumable public ACS SI collection; at most five passages per parent DOI.

Collection is independent of the system under test. It never generates labels or
uses parser confidence for sampling. PDFs, provenance and exclusions are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/acs_benchmark_1000"
POPLER = Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftotext.exe")
TOPICS = ["total synthesis", "photoredox", "cross-coupling", "borylation", "amination", "fluorination", "oxidation", "cyclization",
          "reduction", "alkylation", "arylation", "hydrogenation", "acylation", "esterification", "amidation", "sulfonylation",
          "alkynylation", "olefination", "carbonylation", "annulation", "dearomatization", "rearrangement", "organocatalytic",
          "electrochemical synthesis", "C-H functionalization", "heterocycles", "radical addition", "enantioselective",
          "hydroamination", "halogenation", "thiolation", "phosphorylation", "Suzuki", "Buchwald", "Mitsunobu", "Diels-Alder"]
_lock = threading.Lock()
_last_request = 0.0


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(8):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 7: raise
                # Windows may briefly deny replacement while another reader
                # or writer is closing the destination handle.
                time.sleep(min(.02 * 2**attempt, .2))
    finally:
        temp.unlink(missing_ok=True)


def request(url, payload=None):
    global _last_request
    for attempt in range(4):
        with _lock:
            time.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
        req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None,
            headers={"User-Agent":"AutoSupportGenerator-research/2.0", "Content-Type":"application/json"})
        try:
            return urllib.request.urlopen(req, timeout=90)
        except Exception:
            if attempt == 3: raise
            time.sleep(min(2 ** attempt, 8))


def api(url, cache, payload=None):
    if cache.exists(): return json.loads(cache.read_text(encoding="utf-8"))
    with request(url, payload) as response: data = json.load(response)
    save(cache, data)
    return data


def normalize(text):
    text = text.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    text = text.replace("μ", "µ").replace("\uf06d", "µ").replace("−", "-").replace("–", "-").replace("\u00ad", "")
    return re.sub(r"\s+", " ", text).strip()


def strip_characterization(text):
    """A monitoring mention is not the start of the spectral data block."""
    for marker in re.finditer(r"\b(?:1\s*H\s*NMR|13\s*C\s*NMR|HRMS|FTIR)\b", text):
        prefix = text[max(0,marker.start()-70):marker.start()]
        if re.search(r"\b(?:by|using|via|with)\s+(?:\w+\s+){0,2}$",prefix,re.I):
            continue
        text = text[:marker.start()].strip()
        break
    text = re.split(r"\[(?:α|\uf061)\]",text)[0].strip()
    text = re.sub(r"\s+For\s+[^:.;]{1,30}:\s*$", "", text, flags=re.I)
    return text


def joined_source_blocks(pages):
    """Undo layout-only blank lines without crossing a new procedure heading.

    Uses source prose and punctuation only, never parser predictions or labels.
    Page provenance is retained even when a recipe spans physical pages.
    """
    joined = []
    for page in pages:
        text = re.sub(r"(?m)^\s*S?[-–]?\d+\s*$", "", page["text"])
        text = re.sub(r"(?im)^\s*SUPPORTING INFORMATION\s*(?:S?\d+)?\s*$", "", text)
        for block in re.split(r"\n\s*\n",text):
            raw = normalize(block)
            if not raw: continue
            section = re.search(r"(?<!\S)(?:\d+\.\d+(?:\.\d+)*[.)]?\s+(?:[A-Z][a-z]{2,}|\d+[a-z]\s+[a-z])|\d+\.\s+(?:Detailed|Application|General|Synthesis|Preparation|Experimental|Mechanism|Characterization|Optimization)\b)",raw)
            barrier_after = bool(section)
            if section and section.start()>0:
                raw=raw[:section.start()].rstrip()
            new_start = bool(re.match(r"(?:[a-z]\)\s|To (?:a|an|the) (?!resulting|above|cooled|stirred)|(?:A|An) (?:solution|mixture|suspension|oven|flame|round|Schlenk)|In (?:a|an|the) |Under |(?:\d+(?:[.-]\d+)*[.)-]?\s*)?(?:Synthesis|General procedure|Preparation|Experimental procedure|Synthetic procedure|Table|Figure|Scheme)\b)",raw,re.I))
            if raw.startswith("in "): new_start=False
            spectral = bool(re.match(r"(?:1\s*H|13\s*C|19\s*F|31\s*P)\s*NMR|HR[- ]?MS|FTIR|\[α\]",raw))
            continuation = bool(re.match(r"(?:The (?:mixture|reaction|resulting|combined|organic|aqueous|residue|crude|solvent|filtrate)|After |Then |Following |Upon |Subsequently |Finally |To the (?:resulting|above|cooled)|[a-z])",raw))
            if joined:
                previous=joined[-1]
                unfinished = previous["text"][-1] not in ".;:" and not re.search(r"[.;]\s*\[\d+(?:[-,]\d+)*\]\.?$",previous["text"])
                chemical_prose = bool(re.search(r"\b(?:was|were|reaction|mixture|solution|stirred|added|dissolved|residue)\b", previous["text"],re.I) or re.match(r"To (?:a|an)\b",previous["text"]))
                trailing_heading = bool(re.search(r"\b(?:\d+[.-]\d+\s+)?(?:Synthesis|General procedure|Preparation|Experimental procedure|Synthetic procedure)\b[^.;]*$",previous["text"],re.I))
                previous_spectral = bool(re.search(r"\b(?:NMR|HRMS)\s*\(",previous["text"]))
                if (not new_start and not spectral and not previous_spectral and not trailing_heading and chemical_prose
                        and not previous.get("barrier_after") and not (section and section.start()==0)
                        and (unfinished or continuation) and len(previous["text"])+len(raw)<6500
                        and page["page"]-previous["end_page"]<=1):
                    previous["text"] += " "+raw
                    previous["end_page"]=page["page"]
                    previous["barrier_after"]=barrier_after
                    continue
            joined.append({"page":page["page"],"end_page":page["page"],"text":raw,"barrier_after":barrier_after})
    return joined


def passage_candidates(pages, limit=5, *, join_blocks=False):
    records = []
    cleaned_pages = []
    if join_blocks: pages = joined_source_blocks(pages)
    for page in pages:
        text = re.sub(r"(?m)^\s*S?\d+\s*$", "", page["text"])
        text = re.sub(r"(?im)^\s*SUPPORTING INFORMATION\s*(?:S?\d+)?\s*$", "", text)
        blocks = [b for b in re.split(r"\n\s*\n",text) if b.strip()]
        cleaned_pages.append({"page":page["page"],"end_page":page.get("end_page",page["page"]),"blocks":blocks})
    for page_index,page in enumerate(cleaned_pages):
        for block_index,block in enumerate(page["blocks"]):
            end_page = page["end_page"]
            # Continue a paragraph cut by a physical PDF page boundary. Never
            # join across a new synthetic heading or a new procedural start.
            if not join_blocks and block_index == len(page["blocks"])-1 and page_index+1 < len(cleaned_pages):
                next_page = cleaned_pages[page_index+1]
                if next_page["blocks"]:
                    continuation = normalize(next_page["blocks"][0])
                    if re.match(r"(?:[a-z]|The (?:mixture|reaction|resulting|combined|organic|aqueous|residue|crude)|After |Then |Following )", continuation) and not re.match(r"(?:To (?:a|an)|Synthesis|General procedure|Synthetic procedure)", continuation, re.I):
                        block += "\n"+next_page["blocks"][0]
                        end_page = next_page["page"]
            raw = normalize(block)
            # Stop before characterization rather than treating NMR as chemistry.
            raw = strip_characterization(raw)
            # Drop diagram/header material preceding a recognizable prose start.
            starts = list(re.finditer(r"\b(?:To (?:a|an|the) |(?:A|An) (?:solution|mixture|suspension|oven-dried|flame-dried|round-bottom|Schlenk|reaction tube)|Under (?:a|an|the|nitrogen|argon)|In (?:a|an|the) (?:glove|oven|flame|round|Schlenk)|Following (?:the|general))", raw))
            if starts and not re.search(r"\d\s*(?:mg|mmol|mL|equiv)\b", raw[:starts[0].start()]):
                raw = raw[starts[0].start():]
            raw = re.split(r"\b(?:The characterization|Characterization data|Chiral HPLC|HPLC analysis|Method [A-Z]:|The quantum yield was determined|Figure\b)|\bRf\s*=|\[α\]",raw)[0].strip()
            raw = re.sub(r"\s+(?:[A-Za-z0-9]+\s*:\s*)?mp\s*:.*$", "", raw, flags=re.I)
            raw = re.sub(r"\s+S?\d+\s*$", "", raw).strip()
            if not 200 <= len(raw) <= 3800: continue
            if len(re.findall(r"\d\s*(?:mg|mmol|mL|ml|equiv|mol\s*%)\b", raw)) < 3: continue
            if not re.search(r"\b(?:was|were)\s+(?:added|stirred|dissolved|charged|heated|cooled|treated|irradiated)|\bstirred\s+(?:at|for)", raw, re.I): continue
            if not re.search(r"\b(?:yield|afford|obtain|purif|extract|concentrat|quench|evaporat|filter|residue|reaction mixture|completion)",raw,re.I): continue
            if re.search(r"\b(?:MTT|cell viability|IC50|cytotoxicity|assay plate|western blot|actinometry|photon flux|Stern.Volmer|fluorescence quenching|cyclic voltammetry|UV.vis absorption)\b", raw,re.I): continue
            # Final dangling clause is explicitly flagged, not declared complete.
            flags = []
            if raw[-1] not in ".):;": flags.append("possible_page_or_block_truncation")
            if raw.count("(") != raw.count(")"): flags.append("unbalanced_parentheses")
            records.append({"page":page["page"], "end_page":end_page, "input_text":raw, "extraction_flags":flags,
                            "text_sha256":hashlib.sha256(raw.encode()).hexdigest()})
    # Suppress duplicates/near-copies within a paper; no parser predictions involved.
    selected, fingerprints = [], set()
    for r in records:
        fingerprint = re.sub(r"\d+(?:\.\d+)?", "#",r["input_text"].casefold())
        fingerprint = re.sub(r"\W+", "",fingerprint)
        if fingerprint in fingerprints: continue
        fingerprints.add(fingerprint)
        selected.append(r)
    # Spread choices over the available procedures, not simply first five siblings.
    if limit is not None and len(selected) > limit:
        indices = [round(i*(len(selected)-1)/(limit-1)) for i in range(limit)] if limit>1 else [0]
        selected = [selected[i] for i in indices]
    return selected


def discover():
    queues = []
    for index, topic in enumerate(TOPICS):
        entries = api("https://api.figshare.com/v2/articles/search", OUT / f"search/topic_{index:02d}.json",
                      {"search_for":'"'+topic+'"',"page_size":100,"order":"published_date","order_direction":"desc"})
        queue = []
        for entry in entries:
            doi = entry.get("doi", "").lower()
            if not re.match(r"10\.1021/(?:acs\.)?(?:orglett|joc|jacs|acscatal|orgchem|orginorgau)\.", doi): continue
            if not re.search(r"\.s\d+$",doi): continue
            if entry.get("published_date", "9999")[:10] > date.today().isoformat(): continue
            queue.append({"api_url":entry["url"],"figshare_id":entry["id"], "si_doi":doi,
                          "parent_doi":re.sub(r"\.s\d+$", "",doi), "topic":topic})
        queues.append(queue)
        print(f"Search {topic}: {len(queue)} ACS SI candidates",flush=True)
    seen, ordered = set(), []
    for position in range(max(map(len,queues))):
        for queue in queues:
            if position >= len(queue): continue
            row = queue[position]
            if row["parent_doi"] in seen: continue
            seen.add(row["parent_doi"])
            ordered.append(row)
    save(OUT / "discovery.json", ordered)
    return ordered


def fetch_paper(entry):
    fid = entry["figshare_id"]
    cached = OUT / "papers" / f"{fid}.json"
    if cached.exists():
        record = json.loads(cached.read_text(encoding="utf-8"))
        pages_path = OUT / "pages" / f"{fid}.json"
        if pages_path.exists():
            record["passages"] = passage_candidates(json.loads(pages_path.read_text(encoding="utf-8")))
            save(cached,record)
        return record
    try:
        meta = api(entry["api_url"],OUT / "metadata" / f"{fid}.json")
        files = [f for f in meta["files"] if f["name"].lower().endswith(".pdf") and f["size"] < 40_000_000]
        if not files: return {**entry,"status":"excluded","reason":"no PDF under 40 MB"}
        # Prefer experimental SI, not crystallographic checkCIF/coordinates.
        files.sort(key=lambda f:(bool(re.search(r"checkcif|crystal",f["name"],re.I)), f["name"]))
        file = files[0]
        pdf = OUT / "pdfs" / f"{fid}_{file['name']}"
        pdf.parent.mkdir(parents=True,exist_ok=True)
        if not pdf.exists():
            tmp = pdf.with_suffix(".pdf.part")
            with request(file["download_url"]) as response, tmp.open("wb") as stream:
                while block := response.read(1024*1024): stream.write(block)
            tmp.replace(pdf)
        raw_bytes = pdf.read_bytes()
        if hashlib.md5(raw_bytes).hexdigest() != file["computed_md5"]: raise ValueError("PDF MD5 mismatch")
        if POPLER.exists():
            completed = subprocess.run([str(POPLER),"-layout","-enc","UTF-8","-f","1","-l","60",str(pdf),"-"],capture_output=True,timeout=100)
            if completed.returncode: raise RuntimeError(completed.stderr.decode(errors="replace")[:400])
            pages = [{"page":i+1,"text":text} for i,text in enumerate(completed.stdout.decode("utf-8",errors="replace").split("\f")) if text.strip()]
        else:
            reader = PdfReader(pdf)
            pages = [{"page":i+1,"text":p.extract_text(extraction_mode="layout")} for i,p in enumerate(reader.pages[:60])]
        save(OUT / "pages" / f"{fid}.json", pages)
        passages = passage_candidates(pages)
        record = {**entry,"parent_doi":(meta.get("resource_doi") or entry["parent_doi"]).lower(),
                  "status":"collected","title":re.sub(r"\s+"," ",meta["title"]), "authors":[a["full_name"] for a in meta.get("authors",[])],
                  "license":meta["license"],"source_url":meta["url_public_html"],"download_url":file["download_url"],
                  "pdf_path":str(pdf.relative_to(OUT)), "pdf_size":len(raw_bytes),"sha256":hashlib.sha256(raw_bytes).hexdigest(),
                  "retrieved_date":date.today().isoformat(),"text_pages":len(pages),"passages":passages}
        save(cached,record)
        return record
    except Exception as exc:
        return {**entry,"status":"error","reason":str(exc)}


def assemble(records, target):
    papers, cases, hashes = [], [], set()
    parent_seen = set()
    for record in records:
        if record.get("status") != "collected" or not record["passages"]: continue
        if record["parent_doi"] in parent_seen: continue
        parent_seen.add(record["parent_doi"])
        paper = {k:v for k,v in record.items() if k != "passages"}
        retained = []
        for passage in record["passages"]:
            if passage["text_sha256"] in hashes: continue
            hashes.add(passage["text_sha256"])
            retained.append(passage)
        if not retained: continue
        for passage in retained:
            if len(cases) >= target: break
            cases.append({"id":f"ACS2-{len(cases)+1:04d}","paper_id":str(record["figshare_id"]),"parent_doi":record["parent_doi"],
                          **passage,"annotation_status":"unannotated"})
        papers.append(paper)
        if len(cases) >= target: break
    return papers,cases


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--target",type=int,default=1000)
    arg.add_argument("--workers",type=int,default=3)
    arg.add_argument("--assemble-only",action="store_true")
    opts = arg.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    discovery = json.loads((OUT / "discovery.json").read_text(encoding="utf-8")) if (OUT / "discovery.json").exists() else discover()
    records = []
    for start in range(0,len(discovery),12):
        batch = discovery[start:start+12]
        if opts.assemble_only:
            batch_results = [fetch_paper(e) for e in batch if (OUT / "papers" / f"{e['figshare_id']}.json").exists()]
        else:
            with ThreadPoolExecutor(max_workers=opts.workers) as pool:
                futures = {pool.submit(fetch_paper,e):e for e in batch}
                batch_results = []
                for future in as_completed(futures):
                    r = future.result()
                    batch_results.append(r)
                    print(f"{r['figshare_id']} {r['status']} {len(r.get('passages',[]))} passages",flush=True)
            batch_results.sort(key=lambda r:next(i for i,e in enumerate(batch) if e["figshare_id"] == r["figshare_id"]))
        records.extend(batch_results)
        papers,cases = assemble(records,opts.target)
        save(OUT / "collection_log.json", [{k:v for k,v in r.items() if k != "passages"} for r in records])
        save(OUT / "sources.json",papers)
        save(OUT / "inputs.json",cases)
        save(OUT / "collection_status.json",{"target":opts.target,"cases":len(cases),"papers":len(papers),"attempted":len(records),"max_per_paper":5,
             "complete":len(cases)==opts.target,"extractor":"Layout text, first 60 pages; Poppler if installed, otherwise pypdf; candidates independent of parser predictions"})
        print(f"TOTAL {len(cases)}/{opts.target} methods / {len(papers)} papers; attempted {len(records)}",flush=True)
        if len(cases) >= opts.target: break


if __name__ == "__main__": main()
