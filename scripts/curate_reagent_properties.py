"""Retain explicit, temperature-qualified densities for a known liquid whitelist."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "src/si_generator/resources/reagents"
CACHE = ROOT / "output/reagent_catalog_build/api"
LIQUIDS = "triethylamine|N,N-diisopropylethylamine|pyridine|2,6-lutidine|1,8-diazabicyclo[5.4.0]undec-7-ene|1,5-diazabicyclo[4.3.0]non-5-ene|1,1,3,3-tetramethylguanidine|acetic anhydride|acetyl chloride|oxalyl chloride|thionyl chloride|methanesulfonyl chloride|trifluoromethanesulfonic anhydride|trifluoroacetic acid|acetic acid|formic acid|trifluoromethanesulfonic acid|diisopropyl azodicarboxylate|diethyl azodicarboxylate|N,N'-diisopropylcarbodiimide|trimethylsilyl chloride|triisopropylsilyl chloride|dimethylformamide|dimethyl sulfoxide|tetrahydrofuran|2-methyltetrahydrofuran|1,4-dioxane|acetonitrile|dichloromethane|chloroform|1,2-dichloroethane|ethyl acetate|diethyl ether|methyl tert-butyl ether|methanol|ethanol|2-propanol|tert-butanol|toluene|benzene|hexane|heptane|acetone|water|N-methyl-2-pyrrolidone|N,N-dimethylacetamide|1,1,1,3,3,3-hexafluoro-2-propanol|2,2,2-trifluoroethanol|chlorobenzene|anisole|nitromethane".split("|")


def infos(node):
    if isinstance(node, dict):
        yield from node.get("Information", [])
        for child in node.get("Section", []): yield from infos(child)


def main():
    catalog = json.loads((RESOURCE / "catalog.json").read_text(encoding="utf-8"))
    curated = {"schema_version":"1.0", "density_policy":"Only exact temperature-qualified mass/volume densities for whitelisted neat liquids. No relative vapor density, solution density, range, or unspecified temperature is used. Values are reference-temperature data, not automatically temperature-corrected.", "by_cid":{}, "identity_overrides":[]}
    for record in catalog["compounds"]:
        if record["name"] not in LIQUIDS: continue
        path = CACHE / f"density_{record['cid']}.json"
        if not path.exists(): continue
        source = json.loads(path.read_text(encoding="utf-8"))["Record"]
        refs = {r["ReferenceNumber"]:r for r in source.get("Reference", [])}
        options = []
        for info in infos(source):
            for value in info.get("Value", {}).get("StringWithMarkup", []):
                text = value["String"]
                match = re.fullmatch(r"(\d+\.\d+)\s*g/(?:cu cm|cm3|cm³|mL|ml)\s+at\s+(\d+(?:\.\d+)?)\s*°?\s*C(?:\s*\(.*\))?", text.strip(), re.I)
                if match and 15 <= float(match[2]) <= 30:
                    ref = refs.get(info["ReferenceNumber"], {})
                    options.append(dict(density_g_ml=float(match[1]), density_temperature_c=float(match[2]),
                                        density_source_url=ref.get("URL",record["source_url"]), density_evidence=text,
                                        density_reference=info.get("Reference", []), density_source_name=ref.get("SourceName"),
                                        density_basis="neat liquid at reference temperature"))
        if options:
            options.sort(key=lambda item:(abs(item["density_temperature_c"]-20), -len(str(item["density_g_ml"]))))
            curated["by_cid"][str(record["cid"])] = options[0]
    # These identities were checked against primary supplier records after the
    # first name lookup returned an incorrect formula. Never adopt that lookup.
    verified = [
        ("sodium tert-butoxide", "C4H9NaO", 96.10, ["NaOtBu","tBuONa","NaOt-Bu","t-BuONa"], "https://www.sigmaaldrich.com/MS/en/product/aldrich/703788"),
        ("lithium bis(trimethylsilyl)amide", "C6H18LiNSi2", 167.33, ["LiHMDS"], "https://www.sigmaaldrich.com/US/en/product/aldrich/225770"),
        ("borane dimethyl sulfide", "C2H9BS", 75.97, ["BH3.SMe2","BH3·SMe2","BH3·DMS","BMS"], "https://www.sigmaaldrich.com/SA/en/product/aldrich/179825"),
        ("TEMPO", "C9H18NO", 156.25, ["2,2,6,6-tetramethylpiperidin-1-oxyl","2,2,6,6-Tetramethylpiperidin-1-yl)oxyl"], "https://pubchem.ncbi.nlm.nih.gov/compound/2724126"),
    ]
    for name, formula, mw, aliases, url in verified:
        curated["identity_overrides"].append(dict(cid=None,name=name,formula=formula,molecular_weight_g_mol=mw,
                                                  aliases=[name,*aliases],source_url=url,core_reagent=True,
                                                  density_g_ml=None, density_temperature_c=None, provenance="identity manually verified against formula"))
    (RESOURCE / "curated_properties.json").write_text(json.dumps(curated, ensure_ascii=False, indent=2),encoding="utf-8")
    print(f"Density records: {len(curated['by_cid'])}; curated identity corrections: {len(verified)}")


if __name__ == "__main__": main()
