# ACS Organic Letters compliance audit

Audit date: 2026-10-07. Target journal: *Organic Letters*. The bundled `acs.orglett` DOCX is an application-owned `house_default`, not an official ACS template and not a submission guarantee.

## Sources checked

- [Organic Letters Author Guidelines](https://researcher-resources.acs.org/publish/author_guidelines?coden=orlef7)
- [ACS Research Data Guidelines](https://researcher-resources.acs.org/publish/data_guidelines)
- [ACS NMR Guidelines](https://pubsapp.acs.org/paragonplus/submission/acs_nmr_guidelines.pdf)
- Mathias Christmann, [What I Learned from Analyzing Accurate Mass Data of 3000 Supporting Information Files](https://pubs.acs.org/doi/10.1021/acs.orglett.4c03458), *Org. Lett.* 2025, 27, 4-7
- [HRMS Checker 2.0 source code](https://github.com/match22lab/HRMS-Checker-2.0)

## What the Org. Lett. preset does

| Requirement | Current behavior | Status |
|---|---|---|
| Separate, readable SI document | Generates a standalone DOCX with procedures, characterization and spectra appendix. | Implemented |
| `1H` and `13C` resonance lists | Preflight warns separately when either list is absent. | Implemented |
| `1H` and `13C` spectrum copies | Preflight warns separately when either spectrum artifact is absent. | Implemented |
| Solvent and spectrometer frequency | Preflight checks both fields for `1H` and `13C`. | Implemented |
| Useful full NMR ranges | Preset uses `-1..10 ppm` for `1H` and `-10..200 ppm` for `13C`, covering the ACS minimum windows. | Implemented |
| Formula evidence | Warns when neither HRMS nor elemental analysis is present. | Implemented |
| HRMS accuracy | Org. Lett. profile applies a 5 ppm warning threshold. | Implemented |
| Elemental analysis | ACS base profile applies `+/-0.4%` per reported element. | Implemented |
| Crystalline compounds and important IR | Warns about missing melting point for a reported solid and missing important IR data. | Implemented |
| Traceable profile | Manifest records profile version, review date, all inherited ACS sources and user overrides. | Implemented |

## Accurate-mass handling

The 3000-file study found recurring errors from neutral-molecule masses, missing adduct atoms, nominal instead of monoisotopic masses, formula typos and charge/electron handling. The generator therefore calculates monoisotopic `m/z` from the formula of the measured ion, includes added or removed adduct atoms, applies electron-mass correction and writes the ion formula used for the calculation. Supported simple forms include `[M+H]+`, `[M+Na]+`, `[M-H]-`, `[M]+`, `[M]-` and multiply charged forms such as `[M+2H]2+`.

Complex cluster expressions with several sequential additions or losses are intentionally rejected instead of guessed. They must be entered as a supported measured ion or calculated independently and reviewed.

## Remaining manual review

- The program cannot determine reliably whether a compound is new, known, or exempt; profile warnings currently apply uniformly.
- It does not prove chemical purity. HRMS is identity/formula evidence, not purity evidence.
- It does not inspect a rendered spectrum image for clipping, baseline quality, peak labels, actual integral visibility or signal-to-noise. Generated Mnova settings and document layout still need visual review.
- It does not enforce an official ACS ChemDraw stylesheet or line-art DPI.
- Safety statements, literature comparisons, special-compound characterization and editorial exceptions remain author decisions.
- CIF/checkCIF and CCDC workflows are assisted, but deposition and final alert review remain external requirements.

## Other journal presets

Every visible profile has a packaged DOCX and can render a document in the automated test suite. Profiles do not all have the same compliance depth. Several publishers share one conservative house layout while their JSON overrides adjust page settings, NMR ranges and available warnings. Declared packaging or purity rules that have no implemented validator must not be read as automatic enforcement. Always compare the manifest sources with the current journal instructions before submission.
