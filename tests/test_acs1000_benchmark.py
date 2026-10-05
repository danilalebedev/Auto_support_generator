"""Integrity tests for the independent benchmark, with no network or LLM calls."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "scripts"))
from acs1000_annotations import compile_case, quantities, validate_corpus, schema
from benchmark_acs1000 import evaluate
from acs_corpus_v2 import strip_characterization


def case(text,number=1,doi="10.1021/example"):
    return {"id":f"T{number}","parent_doi":doi,"input_text":text,"text_sha256":hashlib.sha256(text.encode()).hexdigest()}


def test_compiler_uses_exact_label_evidence_not_parser():
    item=case("Substrate A (50 mg, 0.5 mmol) and NBS (1 equiv.) were stirred in 2 mL THF.")
    label={"eligibility":"clear","notes":"","entities":[
        {"name":"Substrate A","role":"reagent","variable":True,"evidence":["Substrate A (50 mg, 0.5 mmol)"]},
        {"name":"NBS","role":"reagent","variable":False,"evidence":["NBS (1 equiv.)"]},
        {"name":"THF","role":"solvent","variable":False,"evidence":["2 mL THF"]}]}
    target=compile_case(item,label)
    assert target["target_template"]=="{Reagent_1.name} ({Reagent_1.mg} mg, {Reagent_1.mmol} mmol) and NBS ({NBS.eq} equiv) were stirred in {Solvent_THF.ml} mL THF."
    assert target["variable_names"]==["Substrate A"]


def test_compiler_rejects_hallucinated_evidence():
    item=case("NBS (1 mmol) was added.")
    label={"eligibility":"clear","notes":"","entities":[{"name":"NBS","role":"reagent","variable":False,"evidence":["NBS (2 mmol)"]}]}
    with pytest.raises(ValueError,match="Evidence absent"):compile_case(item,label)


def test_compiler_rejects_overlapping_entities():
    item=case("ethanol and water (12 mL) were added.")
    label={"eligibility":"review","notes":"","entities":[
        {"name":"ethanol and water","role":"solvent","variable":False,"evidence":["ethanol and water (12 mL)"]},
        {"name":"water","role":"solvent","variable":False,"evidence":["water (12 mL)"]}]}
    with pytest.raises(ValueError,match="Overlapping"):compile_case(item,label)


def test_no_quantity_is_extracted_from_scale_ratio():
    qs=quantities("3 mL, 15 mL/mmol, 2 mol/L",0)
    assert [(q["field"],q["value"]) for q in qs]==[("volume_ml",3),("concentration_m",2)]


def test_independent_compiler_preserves_fractional_quantities():
    qs = quantities("1/2 equiv and 3/4 mL", 10)
    assert [(q["field"], q["value"]) for q in qs] == [("equivalents", .5), ("volume_ml", .75)]
    assert qs[0]["literal"] == "1/2 equiv"
    assert qs[0]["span"] == [10, 19]


def test_corpus_rejects_six_methods_from_one_paper():
    with pytest.raises(AssertionError):validate_corpus([case(f"Method {i}",i) for i in range(6)],expected=6)


def test_corpus_rejects_duplicated_text_across_papers():
    with pytest.raises(AssertionError):validate_corpus([case("Method",1,"a"),case("Method",2,"b")],expected=2)


def test_corpus_rejects_hash_drift():
    item=case("Method")
    item["input_text"]="Edited method"
    with pytest.raises(AssertionError):validate_corpus([item],expected=1)


def test_quantity_scoring_penalizes_missing_entity():
    target=compile_case(case("NBS (1 mmol) was added."),{"eligibility":"clear","notes":"","entities":[{"name":"NBS","role":"reagent","variable":False,"evidence":["NBS (1 mmol)"]}]})
    metric=evaluate(target,{"chemicals":[],"template_text":target["input_text"]})
    assert metric["total_quantities"]==1
    assert metric["correct_quantities"]==0
    assert not metric["all_checks_pass"]


def test_quantity_scoring_requires_correct_occurrence_and_literal_value():
    target=compile_case(case("NBS (1 mmol) was added."),{"eligibility":"clear","notes":"","entities":[{"name":"NBS","role":"reagent","variable":False,"evidence":["NBS (1 mmol)"]}]})
    quantity = {"kind":"amount_mmol", "value":1.004, "derived":False, "span":[5,11]}
    actual = {"chemicals":[{"name":"NBS", "alias":"NBS", "role":"reagent", "variable":False, "quantities":[quantity]}], "template_text":target["target_template"]}
    assert evaluate(target, actual)["correct_quantities"] == 0
    quantity.update(value=1, span=[100,106])
    assert evaluate(target, actual)["correct_quantities"] == 0
    quantity["span"] = [5,11]
    assert evaluate(target, actual)["correct_quantities"] == 1


def test_annotation_schema_forbids_silent_extra_fields():
    spec=schema()
    assert spec["additionalProperties"] is False
    assert spec["properties"]["cases"]["items"]["additionalProperties"] is False


def test_nmr_monitoring_does_not_cut_off_reaction_workup():
    text="Progress was monitored by 1H NMR, then the mixture was extracted and the product isolated. 1H NMR (400 MHz): 7.2 ppm."
    assert strip_characterization(text)=="Progress was monitored by 1H NMR, then the mixture was extracted and the product isolated."


def test_characterization_heading_and_private_use_rotation_are_removed():
    assert strip_characterization("Product was isolated. For 18a: 1H NMR (400 MHz): 7 ppm.")=="Product was isolated."
    assert strip_characterization("Product was isolated. [\uf061]D = -1")=="Product was isolated."


def test_near_duplicate_audit_detects_cross_split_repeated_recipe():
    from audit_acs1000_duplicates import audit
    a={**case("A substrate (2 mmol) was stirred with a reagent (3 mmol) in water overnight.", 1, "a"), "split":"development"}
    b={**case("A substrate (5 mmol) was stirred with a reagent (6 mmol) in water overnight.", 2, "b"), "split":"holdout"}
    pairs=audit([a,b])
    assert len(pairs)==1
    assert pairs[0]["cross_split"] is True


def test_json_artifact_saves_do_not_share_a_temporary_filename(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from acs_corpus_v2 import save
    target=tmp_path / "status.json"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i:save(target,{"writer":i,"payload":"x"*1000}),range(12)))
    assert json.loads(target.read_text(encoding="utf-8"))["writer"] in range(12)
    assert not list(tmp_path.glob("*.tmp"))


def test_annotation_resume_rejects_stale_corpus(tmp_path, monkeypatch):
    import annotate_acs1000_cli as runner
    monkeypatch.setattr(runner, "FOLDER", tmp_path)
    folder = tmp_path / "annotation_runs" / "batch_001"
    folder.mkdir(parents=True)
    (folder / "batch_manifest.json").write_text(json.dumps({"dataset_sha256":"new"}), encoding="utf-8")
    target = tmp_path / "annotations" / "batch_001.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"dataset_sha256":"old", "cases":[]}), encoding="utf-8")
    with pytest.raises(ValueError, match="different corpus"):
        runner.run_batch((folder, []), "must-not-run.exe")


def test_completed_annotation_does_not_start_another_cli_job(tmp_path, monkeypatch):
    import annotate_acs1000_cli as runner
    monkeypatch.setattr(runner, "FOLDER", tmp_path)
    folder = tmp_path / "annotation_runs" / "batch_001"
    folder.mkdir(parents=True)
    (folder / "batch_manifest.json").write_text(json.dumps({"dataset_sha256":"same"}), encoding="utf-8")
    target = tmp_path / "annotations" / "batch_001.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"dataset_sha256":"same", "cases":[{"id":"T1"}]}), encoding="utf-8")
    assert runner.run_batch((folder, [{"id":"T1"}]), "must-not-run.exe")["status"] == "already_complete"


def test_missing_only_batches_reuse_labels_without_overwriting_jobs(tmp_path, monkeypatch):
    import annotate_acs1000_cli as runner
    monkeypatch.setattr(runner, "FOLDER", tmp_path)
    (tmp_path / "frozen_inputs.json").write_text(json.dumps({"dataset_sha256":"same", "cases":[case("A",1),case("B",2)]}), encoding="utf-8")
    labels=tmp_path / "annotations"
    labels.mkdir()
    (labels / "transferred.json").write_text(json.dumps({"dataset_sha256":"same", "cases":[{"id":"T1"}]}), encoding="utf-8")
    tasks=runner.prepare(20, missing_only=True)
    assert len(tasks)==1
    assert [c["id"] for c in tasks[0][1]]==["T2"]
    assert tasks[0][0].name.startswith("batch_missing_")
    assert runner.prepare(20, missing_only=True)[0][0]==tasks[0][0]


def test_curation_replacement_respects_paper_cap_and_rejected_text():
    from collections import Counter
    from curate_acs1000 import select_replacement
    previous={"parent_doi":"a","page":2}
    one={**case("Candidate one",1,"a"),"page":3,"paper_id":"1","extraction_flags":[]}
    two={**case("Candidate two",2,"b"),"page":4,"paper_id":"2","extraction_flags":[]}
    assert select_replacement([one,two],previous,Counter({"a":5}),set(),set())==two
    assert select_replacement([one,two],previous,Counter({"a":5}),set(),{two["text_sha256"]}) is None


def test_held_out_evaluation_requires_immutable_lock(tmp_path, monkeypatch):
    import benchmark_acs1000 as benchmark
    monkeypatch.setattr(benchmark,"FOLDER",tmp_path)
    monkeypatch.setattr(benchmark,"pipeline_fingerprints",lambda:{"parser":"original"})
    corpus={"dataset_sha256":"frozen", "cases":[{"id":"T1"}]}
    labels={"T1":{"entities":[]}}
    with pytest.raises(RuntimeError,match="requires --lock-evaluation"):
        benchmark.evaluation_lock(corpus,labels)
    with pytest.raises(RuntimeError,match="Complete independent"):
        benchmark.evaluation_lock(corpus,{},create=True)
    original=benchmark.evaluation_lock(corpus,labels,create=True)
    assert benchmark.evaluation_lock(corpus,labels)==original
    monkeypatch.setattr(benchmark,"pipeline_fingerprints",lambda:{"parser":"changed"})
    with pytest.raises(RuntimeError,match="lock mismatch"):
        benchmark.evaluation_lock(corpus,labels,create=True)
    assert json.loads((tmp_path / "evaluation_lock.json").read_text(encoding="utf-8"))==original


def test_scorer_accepts_nested_carrier_identity_but_never_its_stock_loading():
    from si_generator.procedure_import import parse_procedure
    item=case("A (1 mmol) and HCl in Et2O (2 M, 5 mL) were stirred.")
    label={"eligibility":"clear","notes":"","entities":[
        {"name":"A","role":"reagent","variable":True,"evidence":["A (1 mmol)"]},
        {"name":"HCl in Et2O","role":"reagent","variable":False,"evidence":["HCl in Et2O (2 M, 5 mL)"]},
        {"name":"Et2O","role":"solvent","variable":False,"evidence":["Et2O"]}]}
    target=compile_case(item,label)
    actual=parse_procedure(item["input_text"],variable_names=["A"])
    assert evaluate(target,actual)["all_checks_pass"]
    target["expected_entities"][-1]["quantities"]=[{"field":"volume_ml","value":5,"span":[31,35]}]
    assert not evaluate(target,actual)["all_checks_pass"]


def test_source_join_restores_split_loading_and_workup_across_pages():
    from acs_corpus_v2 import joined_source_blocks
    pages=[{"page":2,"text":"A mixture of substrate (1 mmol),\n\nNBS (2 mmol) in water (5 mL) was stirred.\n\nAfter extraction the residue was purified by\n\nS2"},
           {"page":3,"text":"column chromatography to afford B.\n\nTo a flask, C (1 mmol) was added."}]
    rows=joined_source_blocks(pages)
    assert len(rows)==2
    assert rows[0]["page"]==2 and rows[0]["end_page"]==3
    assert rows[0]["text"].endswith("to afford B.")
    assert "substrate (1 mmol), NBS" in rows[0]["text"]


def test_source_join_does_not_attach_spectra_or_new_reaction():
    from acs_corpus_v2 import joined_source_blocks
    pages=[{"page":1,"text":"A solution of A (1 mmol) was stirred to afford B.\n\n1H NMR (400 MHz): 7 ppm.\n\nA solution of C (1 mmol) was stirred."}]
    assert len(joined_source_blocks(pages))==3


def test_source_join_does_not_prepend_yield_heading_or_merge_variants():
    from acs_corpus_v2 import joined_source_blocks
    pages=[{"page":1,"text":"Yield: 10 mg (50%) Product A\n\nA solution of B (1 mmol) was stirred.\n\nb) 10 mg C was added."}]
    assert len(joined_source_blocks(pages))==3


def test_source_join_restores_vessel_charge_cut_at_page_end():
    from acs_corpus_v2 import joined_source_blocks
    pages=[{"page":1,"text":"To a flask, A (1 mmol) and THF (75 L/mol,"},
           {"page":2,"text":"22.5 mL) were added. The reaction was filtered through Celite, packed\n\nin a graduated pipette, to afford B."}]
    rows=joined_source_blocks(pages)
    assert len(rows)==1
    assert "75 L/mol, 22.5 mL" in rows[0]["text"]


def test_curation_retains_difficult_complete_recipes_but_flags_source_loss():
    from curate_acs1000 import independent_exclusion
    assert independent_exclusion({"eligibility":"review","notes":"Multistage with ambiguous variables and alternative ligands."}) is None
    label={"eligibility":"review","notes":"The text ends mid-sentence. Organic partners are assumed variable."}
    assert independent_exclusion(label)=="independent_incomplete_source_label"
    assert independent_exclusion(label,has_source_correction=True) is None


def test_curation_is_versioned_and_never_transfers_labels_to_changed_text(tmp_path, monkeypatch):
    import curate_acs1000 as curator
    from acs_corpus_v2 import save
    monkeypatch.setattr(curator,"FOLDER",tmp_path)
    monkeypatch.setattr(curator.collector,"OUT",tmp_path)
    originals=[{**case("Method "+str(i),i,str(i)),"paper_id":str(i),"page":1,"end_page":1,"extraction_flags":[],"split":"development"} for i in range(1,4)]
    parent={"dataset_sha256":"original","cases":originals}
    save(tmp_path / "frozen_inputs.json",parent)
    before=(tmp_path / "frozen_inputs.json").read_bytes()
    save(tmp_path / "discovery.json",[])
    corrected="Full Method 1."
    save(tmp_path / "boundary_revision_proposals.json",{"parent_dataset_sha256":"original","proposals":[{
        "id":"T1","old_sha256":originals[0]["text_sha256"],"new_sha256":hashlib.sha256(corrected.encode()).hexdigest(),
        "new_text":corrected,"page":1,"end_page":2}]})
    labels={c["id"]:{"id":c["id"],"eligibility":"not_synthesis" if c["id"]=="T2" else "clear","notes":"","entities":[]} for c in originals}
    monkeypatch.setattr(curator,"load_labels",lambda _:labels)
    monkeypatch.setattr(curator,"validate_corpus",lambda rows: {"cases":len(rows),"papers":len({c['parent_doi'] for c in rows}),"max_per_paper":1})
    monkeypatch.setattr(curator,"split_cases",lambda rows:([{**c,"split":"development"} for c in rows],[]))
    replacement={**case("Replacement method.",4,"2"),"paper_id":"2","page":2,"end_page":2,"extraction_flags":[]}
    sources={str(i):{"figshare_id":i,"parent_doi":str(i),"pdf_path":f"pdfs/{i}.pdf"} for i in range(1,4)}
    monkeypatch.setattr(curator,"load_pool",lambda _:(sources,[replacement]))
    save(tmp_path / "snapshots/parser_before_1000.py",{})
    monkeypatch.setattr(sys,"argv",["curate_acs1000.py"])
    curator.main()
    output=tmp_path / "curated_v3"
    frozen=json.loads((output / "frozen_inputs.json").read_text(encoding="utf-8"))
    transferred=json.loads((output / "annotations/transferred_parent.json").read_text(encoding="utf-8"))
    assert len(frozen["cases"])==3
    assert [c["id"] for c in transferred["cases"]]==["ACS3-0003"]
    assert frozen["cases"][0]["input_text"]==corrected
    assert frozen["cases"][1]["input_text"]=="Replacement method."
    assert (tmp_path / "frozen_inputs.json").read_bytes()==before
    with pytest.raises(ValueError,match="fresh output directory"):
        curator.main()


def test_source_join_stops_at_numbered_heading_and_reference_ending():
    from acs_corpus_v2 import joined_source_blocks
    pages=[{"page":1,"text":"A (1 mmol) was stirred to afford B.[3] 4.1 Oxidation of B\n\nB (1 mmol) was heated to afford C.[4]\n\n4. Detailed Optimization of Reaction Conditions\n\nEntry Catalyst Yield"}]
    rows=joined_source_blocks(pages)
    assert rows[0]["text"]=="A (1 mmol) was stirred to afford B.[3]"
    assert rows[1]["text"]=="B (1 mmol) was heated to afford C.[4]"
    assert len(rows)==4


def test_source_heading_detection_does_not_cut_molarity():
    from acs_corpus_v2 import joined_source_blocks
    text="A (1 mmol) in THF (2 mL, 0.5 M) was stirred."
    assert joined_source_blocks([{"page":1,"text":text}])[0]["text"]==text
