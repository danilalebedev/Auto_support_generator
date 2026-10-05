"""Compile independently selected labels, freeze a baseline, and score ACS input.

Run --freeze-baseline once before changing the parser, then rerun without it.
Manual annotations are silver labels. Numerical decoding below is merely a
serializer of explicitly annotated spans, not a chemical-name extractor.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from acs_manual_annotations import CASES
from si_generator.procedure_import import parse_procedure

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "output" / "acs_benchmark"
NORMALIZATION = "Whitespace collapsed; Unicode subscripts become ASCII; typographic minus becomes hyphen; private-use mu and m mol spacing normalized. No numbers repaired."


def norm(text):
    text = text.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789"))
    text = text.replace("μ", "µ").replace("\uf06d", "µ").replace("−", "-").replace("–", "-")
    return re.sub(r"\s+", " ", re.sub(r"\bm\s+mol\b", "mmol", text)).strip()


def key(name):
    name = norm(name).casefold()
    name = re.sub(r"^(?:(?:the|dry|anhydrous|deaerated|base|substrate|compound|intermediate|ligand|commercially available)\s+)+", "", name)
    return re.sub(r"\s+", "", name).strip(".,")


def balanced_end(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(": depth += 1
        if text[i] == ")":
            depth -= 1
            if not depth: return i + 1
    return start


# The labels select an exact name or an exact prefix span. This function only
# finds the byte range to serialize that selection; it never proposes a name.
def labeled_span(text, name, explicit):
    if explicit:
        start = text.index(explicit)
        name_start = text.index(name, start, start + len(explicit))
        return name_start, name_start + len(name), start, start + len(explicit)
    boundary = r"(?<![A-Za-z0-9])" if len(name) <= 3 else ""
    mentions = list(re.finditer(boundary + re.escape(name) + r"(?![A-Za-z0-9])", text))
    if not mentions:
        raise ValueError(f"Annotated name not in input: {name!r}")
    for mention in mentions:
        after = mention.end()
        while after < len(text) and text[after] in " ,": after += 1
        end = balanced_end(text, after) if after < len(text) and text[after] == "(" else after
        if end > after and re.search(r"\d\s*(?:mg|mmol|mol|g|mL|ml|M|equiv|eq|µL|µmol)", text[after:end]):
            return mention.start(), mention.end(), after, end
    mention = mentions[0]
    return mention.start(), mention.end(), mention.end(), mention.end()


def annotated_quantities(text, start, end):
    # No shared regexes or functions with the system under test.
    pattern = r"(?<![\w.])(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>mol\s*/\s*L|mol\s*%|mmol|µmol|µL|mL|ml|mg|kg|mol|equiv\.?|eq\.?|mM|M|g|L)(?![A-Za-z/])"
    quantities = []
    for match in re.finditer(pattern, text[start:end]):
        unit = match["u"].rstrip(".")
        value = float(match["n"].replace(",", "."))
        # Ratios mL/mmol are scale instructions, not independent volumes.
        if text[start + match.end():].lstrip().startswith("/"): continue
        field, attr, multiplier, out_unit = {
            "g": ("mass_mg", "g", 1000, "g"), "mg": ("mass_mg", "mg", 1, "mg"), "kg": ("mass_mg", "kg", 1e6, "kg"),
            "mmol": ("amount_mmol", "mmol", 1, "mmol"), "mol": ("amount_mmol", "mol", 1000, "mol"), "µmol": ("amount_mmol", "mmol", .001, "mmol"),
            "mL": ("volume_ml", "ml", 1, "mL"), "ml": ("volume_ml", "ml", 1, "mL"), "µL": ("volume_ml", "mcl", .001, "µL"), "L": ("volume_ml", "l", 1000, "L"),
            "eq": ("equivalents", "eq", 1, "equiv"), "equiv": ("equivalents", "eq", 1, "equiv"),
            "M": ("concentration_m", None, 1, "M"), "mM": ("concentration_m", None, .001, "M"),
            "mol/L": ("concentration_m", None, 1, "M"), "mol%": ("equivalents", None, .01, "mol%"),
        }[re.sub(r"\s+", "", unit)]
        quantities.append(dict(field=field, value=value*multiplier, attr=attr, unit=out_unit, span=[start+match.start(), start+match.end()], literal=match[0]))
    return quantities


def compile_targets():
    candidates = {int(item["candidate_id"].rsplit("B", 1)[1]): item for item in json.loads((FOLDER / "candidates.json").read_text(encoding="utf-8"))}
    sources = {item["source_id"]: item for item in json.loads((FOLDER / "sources.json").read_text(encoding="utf-8"))}
    result = []
    for number, spec in enumerate(CASES, 1):
        block = spec["block"]
        if isinstance(block, int):
            candidate = candidates[block]
            raw = candidate["text"]
            source_id, pages = candidate["source_id"], [candidate["page"]]
        else:
            source_id, page_spec = block.split(":")
            page_range = list(map(int, page_spec.split("-")))
            pages = list(range(page_range[0], page_range[-1]+1))
            page_data = json.loads((FOLDER / "pages" / f"{source_id}.json").read_text(encoding="utf-8"))
            raw = " ".join(p["text"] for p in page_data if p["page"] in pages)
            raw = re.sub(r"(?m)^\s*S\d+\s*$", "", raw)
        text = norm(raw)
        if spec["start"]: text = text[text.index(norm(spec["start"])):]
        if spec["stop"]: text = text[:text.index(norm(spec["stop"]))]
        text = re.split(r"(?:1H NMR|1 H NMR|13C NMR|FTIR|HRMS|\[α\]|\[\uf061\])", text)[0].strip()
        entities, replacements = [], []
        used_aliases = set()
        for role, names in (("variable", spec["variables"]), ("reagent", spec["fixed"]), ("solvent", spec["solvents"])):
            for name in names:
                name = norm(name)
                explicit = next((norm(v) for k, v in spec["spans"].items() if norm(k) == name), None)
                try:
                    ns, ne, qs, qe = labeled_span(text, name, explicit)
                except ValueError as exc:
                    raise ValueError(f"ACS{number:03d} block {block}: {exc}") from exc
                alias = f"Reagent_{sum(e['variable'] for e in entities)+1}" if role == "variable" else re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
                if role == "solvent": alias = "Solvent_" + alias
                elif alias[0].isdigit(): alias = "R_" + alias
                base = alias
                suffix = 2
                while alias in used_aliases:
                    alias = f"{base}_{suffix}"
                    suffix += 1
                used_aliases.add(alias)
                quantities = annotated_quantities(text, qs, qe)
                entity = dict(name=name, alias=alias, role="reagent" if role == "variable" else role, variable=role == "variable", name_span=[ns, ne], quantities=quantities)
                entities.append(entity)
                if role == "variable": replacements.append((ns, ne, "{" + alias + ".name}"))
                for quantity in quantities:
                    if quantity["attr"]:
                        replacements.append((*quantity["span"], "{" + alias + "." + quantity["attr"] + "} " + quantity["unit"]))
        target = text
        # Ranges and alternative loadings remain visible in source; flagged cases
        # require review even if the lexical substitutions happen to agree.
        for start, end, value in sorted(set(replacements), reverse=True):
            target = target[:start] + value + target[end:]
        result.append(dict(id=f"ACS{number:03d}", source_id=source_id, pages=pages, source=sources[source_id], input_text=text,
                           variable_names=[e["name"] for e in entities if e["variable"]], target_template=target, expected_entities=entities,
                           annotation_note=spec["note"], split="holdout" if source_id in {"S14", "S15", "S16"} else "development",
                           human_review_status="unreviewed"))
    assert len(result) == 100, len(result)
    assert len({r["input_text"] for r in result}) == 100, "Duplicate inputs"
    return result


def evaluate(case, actual):
    expected = case["expected_entities"]
    predicted = [e for e in actual["chemicals"] if e["role"] not in {"workup", "product"}]
    matched, differences = set(), []
    alias_map = {}
    correct_quantities = total_quantities = correct_roles = 0
    for entity in expected:
        found = next((e for e in predicted if key(e["name"]) == key(entity["name"]) and e["alias"] not in matched), None)
        if found is None:
            differences.append({"type":"missing_entity", "name":entity["name"]})
            total_quantities += len(entity["quantities"])
            continue
        matched.add(found["alias"])
        alias_map[found["alias"]] = entity["alias"]
        role_ok = found["role"] == entity["role"] and found["variable"] == entity["variable"]
        correct_roles += role_ok
        if not role_ok: differences.append({"type":"role", "name":entity["name"], "expected":[entity["role"],entity["variable"]], "actual":[found["role"],found["variable"]]})
        for q in entity["quantities"]:
            total_quantities += 1
            value = found.get(q["field"])
            good = value is not None and math.isclose(value, q["value"], rel_tol=.005, abs_tol=1e-8)
            correct_quantities += good
            if not good: differences.append({"type":"quantity", "name":entity["name"], "field":q["field"], "expected":q["value"], "actual":value})
    for e in predicted:
        if e["alias"] not in matched: differences.append({"type":"extra_entity", "name":e["name"]})
    canonical_template = re.sub(r"\{([^{}.]+)\.([^{}]+)\}", lambda m:"{"+alias_map.get(m[1],m[1])+"."+m[2]+"}", actual["template_text"])
    exact = canonical_template == case["target_template"]
    if not exact: differences.append({"type":"template_mismatch"})
    return dict(matched_entities=len(matched), expected_entities=len(expected), predicted_entities=len(predicted),
                correct_roles=correct_roles, correct_quantities=correct_quantities, total_quantities=total_quantities,
                template_exact=exact, all_checks_pass=not differences, differences=differences)


def aggregate(results):
    matched = sum(r["matched_entities"] for r in results)
    expected = sum(r["expected_entities"] for r in results)
    predicted = sum(r["predicted_entities"] for r in results)
    total_q = sum(r["total_quantities"] for r in results)
    return dict(cases=len(results), entity_precision=matched/predicted if predicted else 0,
                entity_recall=matched/expected if expected else 0,
                quantity_accuracy=sum(r["correct_quantities"] for r in results)/total_q if total_q else 0,
                role_accuracy=sum(r["correct_roles"] for r in results)/expected if expected else 0,
                exact_templates=sum(r["template_exact"] for r in results), complete_passes=sum(r["all_checks_pass"] for r in results),
                error_counts=dict(Counter(d["type"] for r in results for d in r["differences"])))


def write_html(report, path):
    data = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    page = r'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>ACS · 100 реальных методик</title>
<style>body{font:16px system-ui;margin:32px auto;max-width:1400px;background:#f4f5f7;color:#172333;padding:0 24px}h1{font-size:30px}p{line-height:1.6}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;border:1px solid #d9dee5;padding:16px;line-height:1.6;font:14px ui-monospace,monospace}details{border:1px solid #d5dce3;background:#fff;margin:12px 0;padding:16px}summary{cursor:pointer;font-weight:600}small{color:#506172}select,input,button,textarea{font:inherit;padding:8px;margin:4px;border:1px solid #bac7d2;border-radius:5px}textarea{width:95%;height:70px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #d5dce3;padding:8px;text-align:left}.bad{color:#ad350e}.ok{color:#176437}.note{color:#96520b}a{color:#205bab}.toolbar{position:sticky;top:0;background:#f4f5f7;padding:10px 0;z-index:2}mark{background:#fff0b3}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style>
<h1>100 реальных методик из ACS Supporting Information</h1>
<p>Для каждого примера сохранены текст, PDF и страница, разметка LLM, целевой шаблон и фактический результат. Разметка ещё не подтверждена химиком. Жёлтые замечания отмечают неоднозначности исходного текста. Кнопка экспорта сохраняет ваши оценки в JSON.</p>
<p><strong>Как читать оценку.</strong> 100 фрагментов из 10 статей, не 100 независимых статей. baseline/current/development/holdout используют подсказку — размеченные переменные реагенты; unassisted_all получает только текст. 79 случаев использованы для доработок, 21 из трёх других статей — для отложенной проверки. «Все проверки» означает совпадение размеченных сущностей, ролей, чисел и текста шаблона, а не готовность методики к использованию. Структуры Scope, безопасность, все операции workup и фактические выходы этим тестом не валидируются. Варианты условий и многостадийные случаи требуют отдельной проверки даже при совпадении шаблона. Номера страниц — физические страницы PDF.</p>
<div id="summary"></div><div class="toolbar"><input id="query" placeholder="Поиск по тексту / реагенту"><select id="filter"><option value="all">Все примеры</option><option value="fail">Есть расхождения</option><option value="pass">Все проверки пройдены</option><option value="holdout">Отложенные статьи</option></select><button id="export">Скачать мои оценки</button></div><div id="cases"></div>
<script>const data=__DATA__; const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let reviews={};try{reviews=JSON.parse(localStorage.getItem('acs100-reviews')||'{}')}catch(e){};
const rows=Object.entries(data.summary).map(([s,x])=>`<tr><td>${s}</td><td>${x.cases}</td><td>${(100*x.entity_precision).toFixed(1)}%</td><td>${(100*x.entity_recall).toFixed(1)}%</td><td>${(100*x.quantity_accuracy).toFixed(1)}%</td><td>${x.exact_templates}/${x.cases}</td><td>${x.complete_passes}/${x.cases}</td></tr>`).join('');
document.getElementById('summary').innerHTML='<table><tr><th>Выборка</th><th>N</th><th>Точность сущностей</th><th>Полнота</th><th>Численные поля</th><th>Точный шаблон</th><th>Все проверки</th></tr>'+rows+'</table>';
function render(){let q=document.getElementById('query').value.toLowerCase(),f=document.getElementById('filter').value;document.getElementById('cases').innerHTML=data.cases.filter(c=>(c.id+' '+c.source.title+' '+c.input_text).toLowerCase().includes(q)&&(f==='all'||f==='holdout'&&c.split==='holdout'||f==='pass'&&c.metrics.all_checks_pass||f==='fail'&&!c.metrics.all_checks_pass)).map(c=>`<details><summary>${c.id} · ${c.source_id} · стр. ${c.pages.join(', ')} · ${c.split} · <span class="${c.metrics.all_checks_pass?'ok':'bad'}">${c.metrics.all_checks_pass?'проверки пройдены':c.metrics.differences.length+' расхождений'}</span></summary><p><a href="${esc(c.source.source_url)}" target="_blank">${esc(c.source.title)}</a> · DOI ${esc(c.source.article_doi)} · <a href="${esc(c.source.license.url)}" target="_blank" rel="noopener">${esc(c.source.license.name)}</a> · <a href="${esc(c.source.pdf_path.replaceAll('\\','/'))}#page=${c.pages[0]}">локальный PDF</a></p><small>${esc(c.source.authors.join(", "))}</small><p>Переменные соединения, переданные алгоритму: <strong>${esc(c.variable_names.join("; ") || "не указаны")}</strong></p><p class="note">${esc(c.annotation_note)}</p><h3>Входная методика</h3><pre>${esc(c.input_text)}</pre><div class="grid"><div><h3>Целевой шаблон по разметке LLM</h3><pre>${esc(c.target_template)}</pre></div><div><h3>Предсказание алгоритма</h3><pre>${esc(c.actual.template_text)}</pre></div></div><details><summary>Таблицы, ошибки и исходное предсказание</summary><h3>Размеченные сущности</h3><pre>${esc(JSON.stringify(c.expected_entities,null,2))}</pre><h3>Полученная таблица</h3><pre>${esc(JSON.stringify(c.actual.chemicals,null,2))}</pre><h3>Расхождения</h3><pre>${esc(JSON.stringify(c.metrics.differences,null,2))}</pre><h3>Требует заполнения</h3><pre>${esc(JSON.stringify(c.actual.unresolved,null,2))}</pre><h3>До доработок</h3><pre>${esc(c.baseline.template_text)}</pre></details><p>Ваша оценка <select data-id="${c.id}" class="review"><option value="unreviewed">Не проверено</option><option value="correct">Верно</option><option value="parser_error">Ошибка алгоритма</option><option value="annotation_error">Ошибка разметки</option><option value="ambiguous">Неоднозначно</option></select></p><textarea data-id="${c.id}" class="noteinput" placeholder="Что исправить">${esc(reviews[c.id]?.note||'')}</textarea></details>`).join('');document.querySelectorAll('.review').forEach(el=>{el.value=reviews[el.dataset.id]?.status||'unreviewed';el.onchange=()=>save(el.dataset.id,'status',el.value)});document.querySelectorAll('.noteinput').forEach(el=>el.oninput=()=>save(el.dataset.id,'note',el.value))}
function save(id,k,v){reviews[id]={...(reviews[id]||{}),[k]:v};try{localStorage.setItem('acs100-reviews',JSON.stringify(reviews))}catch(e){}}
document.getElementById('query').oninput=render;document.getElementById('filter').onchange=render;document.getElementById('export').onclick=()=>{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({dataset_sha256:data.dataset_sha256,reviews},null,2)],{type:'application/json'}));a.download='acs100-human-review.json';a.click();URL.revokeObjectURL(a.href)};render();</script></html>'''
    path.write_text(page.replace("__DATA__", data), encoding="utf-8")


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--freeze-baseline", action="store_true")
    arg.add_argument("--development-only", action="store_true")
    options = arg.parse_args()
    cases = compile_targets()
    dataset = dict(annotation_status="LLM silver; not independently human validated", normalization=NORMALIZATION, cases=cases)
    encoded = json.dumps(dataset, ensure_ascii=False, indent=2)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    (FOLDER / "targets.json").write_text(encoded, encoding="utf-8")
    baseline_path = FOLDER / "baseline.json"
    if options.freeze_baseline:
        if baseline_path.exists(): raise FileExistsError("Baseline is immutable; use existing baseline.")
        baseline = {c["id"]:parse_procedure(c["input_text"], variable_names=c["variable_names"]) for c in cases}
        baseline_path.write_text(json.dumps({"dataset_sha256":digest,"predictions":baseline},ensure_ascii=False,indent=2),encoding="utf-8")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline["dataset_sha256"] != digest: raise ValueError("Gold labels changed since baseline was frozen")
    selected = [c for c in cases if not options.development_only or c["split"] == "development"]
    for c in selected:
        c["baseline"] = baseline["predictions"][c["id"]]
        c["actual"] = parse_procedure(c["input_text"], variable_names=c["variable_names"])
        c["baseline_metrics"] = evaluate(c,c["baseline"])
        c["metrics"] = evaluate(c,c["actual"])
        if not options.development_only:
            c["unassisted"] = parse_procedure(c["input_text"])
            c["unassisted_metrics"] = evaluate(c,c["unassisted"])
    summary = {"baseline":aggregate([c["baseline_metrics"] for c in selected]), "current":aggregate([c["metrics"] for c in selected])}
    for split in ("development","holdout"):
        subset = [c["metrics"] for c in selected if c["split"] == split]
        if subset: summary[split] = aggregate(subset)
    if not options.development_only:
        summary["unassisted_all"] = aggregate([c["unassisted_metrics"] for c in selected])
    report = dict(dataset_sha256=digest, annotation_status=dataset["annotation_status"], summary=summary, cases=selected)
    tracked = ["scripts/acs_manual_annotations.py", "scripts/benchmark_acs_procedures.py", "src/si_generator/procedure_import.py",
               "src/si_generator/reagent_catalog.py", "src/si_generator/resources/reagents/catalog.json",
               "src/si_generator/resources/reagents/curated_properties.json", "src/si_generator/resources/reagents/density_evidence.json"]
    report["run_metadata"] = {"created_utc":datetime.now(timezone.utc).isoformat(),
                              "file_sha256":{name:hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in tracked},
                              "holdout_policy":"Parser rules tuned on 79 development cases; 21 cases from S14/S15/S16 evaluated after tuning. Later changes only attach density evidence or alter DOCX highlighting/report metadata.",
                              "limitations":["Silver labels authored by the same LLM performing development, not independent expert ground truth.",
                                             "Article-level split; only three holdout articles; related procedures are correlated.",
                                             "Exact-template score canonicalizes alias names but requires literal equality otherwise.",
                                             "Numerical score checks source quantities with 0.5% relative tolerance, including missing values as errors; it does not validate all derived properties.",
                                             "Passing metrics does not remove the mandatory human-review requirement."]}
    suffix = "development" if options.development_only else "100"
    (FOLDER / f"acs_{suffix}_results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    write_html(report,FOLDER / f"acs_{suffix}_review.html")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
