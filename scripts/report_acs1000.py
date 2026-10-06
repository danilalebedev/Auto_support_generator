"""Build a reviewable corpus/prediction report without inventing reference labels."""
from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from datetime import datetime,timezone

from acs1000_annotations import FOLDER, ROOT, validate_corpus, compile_case
from acs_corpus_v2 import save
from benchmark_acs1000 import baseline_parser, load_labels
from si_generator.procedure_import import parse_procedure


HTML = r'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>ACS 1000 · корпус и проверка</title>
<style>body{font:16px system-ui;max-width:1440px;margin:30px auto;padding:0 24px;background:#f4f6f8;color:#172637}p{line-height:1.55}.banner{background:#fff1c9;padding:16px;border-left:5px solid #b37616}.toolbar{position:sticky;top:0;background:#f4f6f8;padding:12px 0;z-index:2}input,select,button,textarea{font:inherit;padding:8px;border:1px solid #afbdc9;border-radius:4px;margin:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;background:white;padding:16px;border:1px solid #d3dce4}details{padding:16px;margin:12px 0;background:white;border:1px solid #d3dce4}summary{cursor:pointer;font-weight:600}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.meta{font-size:14px;color:#526478}textarea{width:95%;min-height:85px}a{color:#1d5b98}table{border-collapse:collapse;font-size:14px;width:100%}th,td{border:1px solid #cbd6df;padding:8px;text-align:left}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style>
<h1>ACS: 1 000 фрагментов методик / __PAPERS__ статей</h1>
<p>Не более пяти примеров из одной работы. Каждый вход связан с DOI, PDF и физической страницей. Ограничение применяется к родительскому DOI статьи, а не к отдельному SI. Корпус заморожен до независимой разметки.</p>
<div class="banner"><strong>Это исследовательский корпус, не доказательство высокой точности.</strong> Независимая LLM-разметка получена для __ANNOTATIONS__ из 1 000 примеров. Это проверяемые silver-метки, а не экспертный gold. Ни предсказания скрипта, ни его предупреждения не используются в качестве «истины». Встречаются неполные фрагменты и сложные многостадийные случаи. Результаты старого набора нельзя переносить на эту тысячу.</div>
<p>Разработка: __DEV__; промежуточная проверка: __VAL__; отложенный тест: __TEST__. Статьи не пересекаются между частями. Примеры из ранее изученных статей всегда относятся к разработке. Предсказания ниже получены только из текста, без списка переменных соединений.</p>
__METRICS_HTML__
<div class="toolbar"><input id="query" placeholder="ID, DOI, название, реагент"><select id="split"><option value="all">Все части</option><option value="development">Разработка</option><option value="validation">Промежуточная проверка</option><option value="holdout">Отложенный тест</option></select><select id="eligibility"><option value="all">Любая пригодность</option><option value="clear">Однозначная методика</option><option value="review">Нужен разбор</option><option value="not_synthesis">Не синтез</option><option value="pending">Не размечено</option></select><select id="quality"><option value="all">Любой результат</option><option value="pass">Все поля совпали</option><option value="fail">Есть расхождения</option><option value="quantity">Ошибки чисел</option><option value="entity">Ошибки объектов</option><option value="source">Флаги исходного текста</option></select><button id="prev">Назад</button><span id="position"></span><button id="next">Далее</button><button id="export">Скачать замечания</button></div>
<div id="cards"></div><script>
const report=__DATA__,esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const storage='acs1000-reviews-'+report.dataset_sha256;let reviews={};try{reviews=JSON.parse(localStorage.getItem(storage)||'{}')}catch(e){}let page=0;
function annotationMarkup(c){if(!c.annotation)return '<p>Независимый таргет: <strong>ещё не размечен</strong></p>';const materials=(c.annotation.expected_entities||[]).map(e=>`<tr><td>${esc(e.name)}</td><td>${esc(e.alias)}</td><td>${esc(e.role)}${e.variable?' · переменный':''}</td><td>${e.quantities.map(q=>esc(q.literal)+' → '+esc(q.value)+' '+esc(q.field)).join('<br>')||'Не указаны'}</td></tr>`).join('');return `<p>Разметка: <strong>${esc(c.annotation.eligibility)}</strong> · LLM silver, требуется проверка химиком</p><p>${esc(c.annotation.annotation_note)}</p><p>Предположенные переменные: ${esc(c.annotation.variable_names.join(', ')||'нет')}</p><div class="grid"><div><h3>Независимый таргет</h3><pre>${esc(c.annotation.target_template)}</pre></div><div><h3>Предсказание с отмеченными переменными</h3><pre>${esc(c.assisted_template)}</pre></div></div><details><summary>Независимые объекты и исходные загрузки</summary><table><thead><tr><th>Вещество</th><th>Алиас</th><th>Роль</th><th>Текст → нормализованное число</th></tr></thead><tbody>${materials}</tbody></table></details>${c.metrics?`<p>Сравнение assisted: ${c.metrics.all_checks_pass?'все поля совпали':'есть расхождения'}; точный шаблон: ${c.metrics.template_exact?'да':'нет'}</p><pre>${esc(JSON.stringify(c.metrics.differences,null,2))}</pre>`:''}`}
function record(id,k,v){reviews[id]={...(reviews[id]||{}),[k]:v};try{localStorage.setItem(storage,JSON.stringify(reviews))}catch(e){}}
function render(){const q=document.querySelector('#query').value.toLowerCase(),s=document.querySelector('#split').value,e=document.querySelector('#eligibility').value,k=document.querySelector('#quality').value;
const quality=c=>k==='all'||(k==='source'&&c.extraction_flags.length>0)||(k==='pass'&&c.metrics?.all_checks_pass)||(k==='fail'&&c.metrics&&!c.metrics.all_checks_pass)||(k==='quantity'&&c.metrics?.differences.some(d=>d.type==='quantity'||d.type==='extra_quantity'))||(k==='entity'&&c.metrics?.differences.some(d=>d.type==='missing_entity'||d.type==='extra_entity'));
const filtered=report.cases.filter(c=>(s==='all'||c.split===s)&&(e==='all'||(c.annotation?.eligibility||'pending')===e)&&quality(c)&&(c.id+' '+c.parent_doi+' '+c.source.title+' '+c.input_text).toLowerCase().includes(q));const pages=Math.max(1,Math.ceil(filtered.length/25));page=Math.max(0,Math.min(page,pages-1));document.querySelector('#position').textContent=`${filtered.length} примеров · ${page+1}/${pages}`;
document.querySelector('#cards').innerHTML=filtered.slice(page*25,page*25+25).map(c=>`<details><summary>${c.id} · ${c.split} · PDF стр. ${c.page} · ${c.actual.chemicals.length} распознанных объектов</summary><p><a href="${esc(c.source.source_url)}" target="_blank" rel="noopener">${esc(c.source.title)}</a><br><span class="meta">${esc(c.source.authors.join(', '))}<br>DOI: ${esc(c.parent_doi)} · <a href="${esc(c.source.license.url)}">${esc(c.source.license.name)}</a> · <a href="${esc(c.source.pdf_path.replaceAll('\\','/'))}#page=${c.page}">исходный PDF</a></span></p><p class="meta">Флаги извлечения: ${esc(c.extraction_flags.join(', ')||'нет автоматических флагов; это не гарантия полноты')}</p><div class="grid"><div><h3>Исходный текст</h3><pre>${esc(c.input_text)}</pre></div><div><h3>Предсказание без подсказок</h3><pre>${esc(c.actual.template_text)}</pre></div></div><details><summary>Объекты, нерешённые поля, предсказание до доработок</summary><pre>${esc(JSON.stringify(c.actual.chemicals,null,2))}</pre><pre>${esc(JSON.stringify(c.actual.unresolved,null,2))}</pre><h3>До доработок</h3><pre>${esc(c.baseline_template)}</pre></details>${annotationMarkup(c)}<p>Оценка <select class="rating" data-id="${c.id}"><option value="unreviewed">Не проверено</option><option value="valid">Подходит для разметки</option><option value="fragment">Неполный фрагмент</option><option value="not_synthesis">Не методика синтеза</option><option value="parser_error">Ошибка предсказания</option></select></p><textarea class="note" data-id="${c.id}" placeholder="Комментарий к тексту или предсказанию">${esc(reviews[c.id]?.note||'')}</textarea></details>`).join('');
document.querySelectorAll('.rating').forEach(el=>{el.value=reviews[el.dataset.id]?.status||'unreviewed';el.onchange=()=>record(el.dataset.id,'status',el.value)});document.querySelectorAll('.note').forEach(el=>el.oninput=()=>record(el.dataset.id,'note',el.value));}
document.querySelector('#query').oninput=()=>{page=0;render()};for(const id of ['split','eligibility','quality'])document.querySelector('#'+id).onchange=()=>{page=0;render()};document.querySelector('#prev').onclick=()=>{page--;render()};document.querySelector('#next').onclick=()=>{page++;render()};
document.querySelector('#export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({dataset_sha256:report.dataset_sha256,reviews},null,2)],{type:'application/json'}));a.download='acs1000-human-review.json';a.click();URL.revokeObjectURL(a.href)};render();</script></html>'''


def load_current_evaluations(corpus, labels):
    hashes={key:hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for key,path in {
        "parser_sha256":"src/si_generator/procedure_import.py",
        "scorer_sha256":"scripts/benchmark_acs1000.py",
        "annotation_compiler_sha256":"scripts/acs1000_annotations.py"}.items()}
    rows={}
    sections=[]
    summaries={}
    for split,title in [("holdout","Отложенные статьи"),("validation","Промежуточная проверка"),("all","Весь набор, включая использованную для разработки часть"),("development","Разработка — не тест обобщения"),("development_partial","Промежуточная диагностика development — не тест обобщения")]:
        path=FOLDER / f"results_{split}.json"
        if not path.exists(): continue
        report=json.loads(path.read_text(encoding="utf-8"))
        if report.get("dataset_sha256")!=corpus["dataset_sha256"] or any(report.get(k)!=v for k,v in hashes.items()): continue
        if any(c["id"] not in labels or c.get("annotation_sha256")!=hashlib.sha256(json.dumps(labels[c["id"]],sort_keys=True,ensure_ascii=False).encode()).hexdigest() for c in report["cases"]): continue
        rows.update({c["id"]:c["metrics"] for c in report["cases"]})
        summaries[split]={"summary":report["summary"],"by_eligibility":report.get("by_eligibility",{})}
        table=[]
        for mode,label in [("baseline","До доработок + переменные"),("current","После доработок + переменные"),("unassisted","После доработок, только текст")]:
            m=report["summary"][mode]
            table.append(f"<tr><td>{label}</td><td>{m['exact_templates']}/{m['cases']}</td><td>{m['complete_passes']}/{m['cases']}</td><td>{m['entity_precision']:.1%} / {m['entity_recall']:.1%}</td><td>{m['quantity_precision']:.1%} / {m['quantity_accuracy']:.1%}</td></tr>")
        sections.append(f"<h2>{html.escape(title)}</h2><p>Совпадение с независимой LLM-разметкой, не экспертная химическая верификация. «Все поля» не означает готовность методики к применению или проверку реального расчёта загрузок.</p><table><thead><tr><th>Режим</th><th>Точный шаблон</th><th>Все сравниваемые поля</th><th>Объекты: precision / recall</th><th>Числа: precision / recall</th></tr></thead><tbody>{''.join(table)}</tbody></table>")
    return rows,"".join(sections),summaries


def main():
    corpus=json.loads((FOLDER / "frozen_inputs.json").read_text(encoding="utf-8"))
    stats=validate_corpus(corpus["cases"])
    sources={str(s["figshare_id"]):s for s in json.loads((FOLDER / "sources.json").read_text(encoding="utf-8"))}
    labels=load_labels(corpus["cases"])
    evaluated,metrics_html,summaries=load_current_evaluations(corpus,labels)
    before=baseline_parser()
    results=[]
    for c in corpus["cases"]:
        baseline=before(c["input_text"])
        actual=parse_procedure(c["input_text"])
        row={**c,"actual":actual,"baseline_template":baseline["template_text"],"source":sources[c["paper_id"]]}
        if c["id"] in labels:
            compiled=compile_case(c,labels[c["id"]])
            row["annotation"]={k:compiled[k] for k in ("eligibility","annotation_note","annotation_quality_flags","variable_names","target_template","expected_entities")}
            row["assisted_template"]=parse_procedure(c["input_text"],variable_names=compiled["variable_names"])["template_text"]
        if c["id"] in evaluated: row["metrics"]=evaluated[c["id"]]
        results.append(row)
    hashes={p:hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ["src/si_generator/procedure_import.py","scripts/acs_corpus_v2.py","scripts/benchmark_acs1000.py","scripts/acs1000_annotations.py"]}
    result={"dataset_sha256":corpus["dataset_sha256"],"generated_utc":datetime.now(timezone.utc).isoformat(),
            "stats":stats,"annotation_count":len(labels),"accuracy":summaries or None,"file_hashes":hashes,
            "extraction_flag_counts":dict(Counter(f for c in corpus["cases"] for f in c["extraction_flags"])),"cases":results}
    save(FOLDER / "predictions_review.json",result)
    # Compact view keeps large source-property evidence in JSON, not every DOM card.
    for c in result["cases"]:
        c["actual"]["chemicals"]=[{k:v for k,v in ch.items() if k not in {"property_sources","quantities"}} for ch in c["actual"]["chemicals"]]
    page=HTML.replace("__PAPERS__",str(stats["papers"])).replace("__ANNOTATIONS__",str(len(labels))).replace("__METRICS_HTML__",metrics_html)
    for token,split in [("__DEV__","development"),("__VAL__","validation"),("__TEST__","holdout")]: page=page.replace(token,str(corpus["split_counts"][split]))
    (FOLDER / "acs1000_review.html").write_text(page.replace("__DATA__",json.dumps(result,ensure_ascii=False).replace("</","<\\/")),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="cases"},indent=2))


if __name__=="__main__":main()
