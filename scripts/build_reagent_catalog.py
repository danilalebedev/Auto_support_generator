"""Build an offline 15k-compound catalog using traceable public data.

PubChemLite patent counts are a popularity proxy, not reaction-role counts.
Its exact masses are deliberately NOT used as molar weights. All molar weights
and identities are fetched from PubChem PUG REST for the actual selected CID.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "output" / "reagent_catalog_build"
OUTPUT = ROOT / "src" / "si_generator" / "resources" / "reagents"
PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# name | exact formula | common unambiguous laboratory aliases
# Ambiguous labels (DBP, PDC as a generic abbreviation, ether, petroleum ether)
# are not resolved by fuzzy matching.
SEED_TEXT = """N-bromosuccinimide|C4H4BrNO2|NBS
N-chlorosuccinimide|C4H4ClNO2|NCS
N-iodosuccinimide|C4H4INO2|NIS
potassium carbonate|K2CO3|K2CO3
sodium carbonate|Na2CO3|Na2CO3
cesium carbonate|Cs2CO3|Cs2CO3
sodium bicarbonate|NaHCO3|NaHCO3
potassium bicarbonate|KHCO3|KHCO3
potassium phosphate tribasic|K3PO4|K3PO4
potassium hydroxide|KOH|KOH
sodium hydroxide|NaOH|NaOH
lithium hydroxide|LiOH|LiOH
lithium hydroxide monohydrate|H3LiO2|LiOH.H2O;LiOH·H2O
sodium hydride|NaH|NaH
potassium hydride|KH|KH
potassium tert-butoxide|C4H9KO|KOtBu;tBuOK;t-BuOK;KOt-Bu
sodium tert-butoxide|C4H9NaO|NaOtBu;tBuONa;NaOt-Bu
sodium methoxide|CH3NaO|NaOMe;MeONa
sodium ethoxide|C2H5NaO|NaOEt;EtONa
triethylamine|C6H15N|Et3N;TEA;NEt3
N,N-diisopropylethylamine|C8H19N|DIPEA;DIEA;iPr2NEt
pyridine|C5H5N|Py
4-dimethylaminopyridine|C7H10N2|DMAP
1,8-diazabicyclo[5.4.0]undec-7-ene|C9H16N2|DBU
1,4-diazabicyclo[2.2.2]octane|C6H12N2|DABCO
2,6-lutidine|C7H9N|2,6-lutidine
1,5-diazabicyclo[4.3.0]non-5-ene|C7H12N2|DBN
1,1,3,3-tetramethylguanidine|C5H13N3|TMG
sodium borohydride|BH4Na|NaBH4
lithium aluminum hydride|AlH4Li|LiAlH4;LAH
sodium cyanoborohydride|CH3BNNa|NaBH3CN
sodium triacetoxyborohydride|C6H10BNaO6|NaBH(OAc)3;STAB
diisobutylaluminum hydride|C8H19Al|DIBAL-H;DIBAL
borane dimethyl sulfide|C2H9BS|BH3.SMe2;BH3·SMe2
n-butyllithium|C4H9Li|n-BuLi;BuLi
tert-butyllithium|C4H9Li|t-BuLi;tBuLi
lithium diisopropylamide|C6H14LiN|LDA
lithium bis(trimethylsilyl)amide|C6H18LiNSi2|LiHMDS
sodium bis(trimethylsilyl)amide|C6H18NNaSi2|NaHMDS
potassium bis(trimethylsilyl)amide|C6H18KNSi2|KHMDS
iodine|I2|I2
bromine|Br2|Br2
triphenylphosphine|C18H15P|PPh3;Ph3P
triphenylphosphine oxide|C18H15OP|OPPh3
di-tert-butyl dicarbonate|C10H18O5|Boc2O;(Boc)2O
acetic anhydride|C4H6O3|Ac2O
acetyl chloride|C2H3ClO|AcCl
oxalyl chloride|C2Cl2O2|(COCl)2
thionyl chloride|Cl2OS|SOCl2
methanesulfonyl chloride|CH3ClO2S|MsCl
4-toluenesulfonyl chloride|C7H7ClO2S|TsCl;p-TsCl
trifluoromethanesulfonic anhydride|C2F6O5S2|Tf2O
trifluoroacetic acid|C2HF3O2|TFA
acetic acid|C2H4O2|AcOH;HOAc
formic acid|CH2O2|HCO2H;HCOOH
trifluoromethanesulfonic acid|CHF3O3S|TfOH
hydrochloric acid|HCl|HCl
sulfuric acid|H2SO4|H2SO4
phosphoric acid|H3PO4|H3PO4
magnesium sulfate|MgSO4|MgSO4
sodium sulfate|Na2SO4|Na2SO4
sodium chloride|NaCl|NaCl
ammonium chloride|ClH4N|NH4Cl
sodium iodide|NaI|NaI
potassium iodide|KI|KI
potassium fluoride|KF|KF
cesium fluoride|CsF|CsF
copper(I) iodide|CuI|CuI
copper(II) acetate|C4H6CuO4|Cu(OAc)2
copper(II) bromide|CuBr2|CuBr2
copper(I) bromide|CuBr|CuBr
copper(I) chloride|CuCl|CuCl
palladium(II) acetate|C4H6O4Pd|Pd(OAc)2
palladium(II) chloride|PdCl2|PdCl2
tetrakis(triphenylphosphine)palladium(0)|C72H60P4Pd|Pd(PPh3)4
nickel(II) chloride|NiCl2|NiCl2
zinc chloride|ZnCl2|ZnCl2
iron(III) chloride|FeCl3|FeCl3
silver carbonate|Ag2CO3|Ag2CO3
silver nitrate|AgNO3|AgNO3
potassium persulfate|K2S2O8|K2S2O8
ammonium persulfate|H8N2O8S2|(NH4)2S2O8
hydrogen peroxide|H2O2|H2O2
tert-butyl hydroperoxide|C4H10O2|TBHP;tBuOOH
2,2,6,6-tetramethylpiperidin-1-oxyl|C9H18NO|TEMPO
2,3-dichloro-5,6-dicyano-1,4-benzoquinone|C8Cl2N2O2|DDQ
diisopropyl azodicarboxylate|C8H14N2O4|DIAD
diethyl azodicarboxylate|C6H10N2O4|DEAD
N,N'-dicyclohexylcarbodiimide|C13H22N2|DCC
N,N'-diisopropylcarbodiimide|C7H14N2|DIC
1,1'-carbonyldiimidazole|C7H6N4O|CDI
trimethylsilyl chloride|C3H9ClSi|TMSCl
tert-butyldimethylsilyl chloride|C6H15ClSi|TBSCl;TBDMSCl
triisopropylsilyl chloride|C9H21ClSi|TIPSCl
dimethylformamide|C3H7NO|DMF
dimethyl sulfoxide|C2H6OS|DMSO
tetrahydrofuran|C4H8O|THF
2-methyltetrahydrofuran|C5H10O|2-MeTHF;2-Me-THF
1,4-dioxane|C4H8O2|1,4-dioxane;dioxane
acetonitrile|C2H3N|MeCN;CH3CN;ACN
dichloromethane|CH2Cl2|DCM;CH2Cl2
chloroform|CHCl3|CHCl3
1,2-dichloroethane|C2H4Cl2|DCE
ethyl acetate|C4H8O2|EtOAc;EA
diethyl ether|C4H10O|Et2O
methyl tert-butyl ether|C5H12O|MTBE
methanol|CH4O|MeOH
ethanol|C2H6O|EtOH
2-propanol|C3H8O|iPrOH;IPA;isopropanol
tert-butanol|C4H10O|tBuOH;t-BuOH
toluene|C7H8|PhMe
benzene|C6H6|C6H6
hexane|C6H14|n-hexane
heptane|C7H16|n-heptane
acetone|C3H6O|acetone
water|H2O|H2O
N-methyl-2-pyrrolidone|C5H9NO|NMP
N,N-dimethylacetamide|C4H9NO|DMA;DMAc
1,1,1,3,3,3-hexafluoro-2-propanol|C3H2F6O|HFIP
2,2,2-trifluoroethanol|C2H3F3O|TFE
chlorobenzene|C6H5Cl|PhCl
anisole|C7H8O|anisole
nitromethane|CH3NO2|MeNO2
"""


def get_json(url: str, cache_name: str) -> dict:
    path = CACHE / "api" / (cache_name + ".json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            time.sleep(0.25)
            with urllib.request.urlopen(url, timeout=90) as response:
                result = json.load(response)
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            return result
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def download(url: str, path: Path) -> None:
    if path.exists():
        return
    temp = path.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=120) as response, temp.open("wb") as target:
        while block := response.read(1024 * 1024):
            target.write(block)
    temp.replace(path)


def build(count: int) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metadata = get_json("https://zenodo.org/api/records/22953038", "pubchemlite_metadata")
    file = metadata["files"][0]
    csv_path = CACHE / file["key"]
    download(file["links"]["self"], csv_path)
    expected_md5 = file.get("checksum", "").removeprefix("md5:")
    if expected_md5 and hashlib.md5(csv_path.read_bytes()).hexdigest() != expected_md5:
        raise ValueError("PubChemLite checksum mismatch")
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        ranked = sorted(csv.DictReader(stream), key=lambda row: (-int(row["Patent_Count"]), -int(row["PubMed_Count"]), int(row["Identifier"])))
    seeds = {}
    failures = []
    properties = {}
    for index, line in enumerate(SEED_TEXT.strip().splitlines()):
        name, formula, aliases = line.split("|")
        url = f"{PUG}/compound/name/{urllib.parse.quote(name, safe='')}/property/MolecularWeight,MolecularFormula,Title,IUPACName,InChIKey/JSON"
        try:
            prop = get_json(url, f"seed_{index:03d}")["PropertyTable"]["Properties"][0]
            # Formula order in PubChem need not be Hill order; compare element counts.
            import re
            def counts(value):
                return {a: int(b or 1) for a, b in re.findall(r"([A-Z][a-z]?)(\d*)", value)}
            if counts(prop["MolecularFormula"]) != counts(formula):
                raise ValueError(f"formula mismatch {prop['MolecularFormula']} vs {formula}")
            cid = prop["CID"]
            properties[cid] = prop
            seeds[cid] = {"name": name, "aliases": [name, *aliases.split(";")]}
        except Exception as exc:
            failures.append({"name": name, "error": str(exc)})
        if (index + 1) % 20 == 0:
            print(f"Core reagent identities: {index+1}", flush=True)
    selected = dict.fromkeys(seeds)
    ranking = {}
    for rank, row in enumerate(ranked, 1):
        cid = int(row["Identifier"])
        ranking[cid] = {**row, "patent_rank": rank}
        if len(selected) < count:
            selected[cid] = None
    remaining = [cid for cid in selected if cid not in properties]
    for offset in range(0, len(remaining), 100):
        batch = remaining[offset:offset+100]
        digest = hashlib.sha256(",".join(map(str, batch)).encode()).hexdigest()[:16]
        url = f"{PUG}/compound/cid/{','.join(map(str, batch))}/property/MolecularWeight,MolecularFormula,Title,IUPACName,InChIKey/JSON"
        for prop in get_json(url, f"properties_{digest}")["PropertyTable"]["Properties"]:
            properties[prop["CID"]] = prop
        if offset % 1000 == 0:
            print(f"PubChem properties: {len(properties)}/{count}", flush=True)
    records = []
    for cid in selected:
        prop = properties[cid]
        row = ranking.get(cid, {})
        seed = seeds.get(cid, {})
        names = [seed.get("name"), prop.get("Title"), prop.get("IUPACName"), row.get("CompoundName"), row.get("Synonym"), *seed.get("aliases", [])]
        records.append({"cid": cid, "name": seed.get("name") or prop["Title"],
                        "aliases": sorted({name for name in names if name}), "formula": prop["MolecularFormula"],
                        "molecular_weight_g_mol": float(prop["MolecularWeight"]), "inchikey": prop.get("InChIKey"),
                        "density_g_ml": None, "density_temperature_c": None,
                        "source_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}", "core_reagent": bool(seed),
                        "patent_count": int(row["Patent_Count"]) if row else None,
                        "literature_count": int(row["PubMed_Count"]) if row else None,
                        "patent_rank": row.get("patent_rank")})
    output = {"schema_version": "1.0", "retrieved_date": "2026-10-05", "compound_count": len(records),
              "selection": "Core synthetic reagents plus highest Patent_Count in PubChemLite; tie-break PubMed_Count then CID. This is not a measured ranking of reagents in reactions.",
              "ranking_source": {"url": "https://zenodo.org/records/22953038", "license": "CC BY 4.0", "file": file["key"], "checksum": file.get("checksum")},
              "property_source": "https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest", "seed_resolution_failures": failures, "compounds": records}
    (OUTPUT / "catalog.json").write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (CACHE / "build_summary.json").write_text(json.dumps({key: value for key, value in output.items() if key != "compounds"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(records)} compounds, {len(seeds)} core identities, {len(failures)} unresolved seeds", flush=True)
    # Density assertions remain source text until a curator chooses a value and temperature.
    for record in records:
        if record["core_reagent"]:
            try:
                get_json(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{record['cid']}/JSON?heading=Density", f"density_{record['cid']}")
            except Exception:
                pass
    print("Density source collection complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=15000)
    build(parser.parse_args().count)
