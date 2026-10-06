# Example 4: complete NMR, scope, and crystallography input

This example contains 28 compounds: **2g, 2h, 2k, 3a-3w, 5, and 6**. It demonstrates an all-in-one Word input, calculated reaction loadings, an editable compound scope, raw 1H/13C NMR processing, and optional crystallography data.

## Input files

- `All_in_one_input.docx`: combined Compound table, Reaction schema, Scope, SI template, and Crystallography template.
- `Compound_table.docx`: author-provided methods and analytical data with ChemDraw structures at their original 100% size.
- `Reaction_schema.docx` and `Scope.docx`: editable precursor/product structures and measured masses for all compounds.
- `SI_template.docx`: Times New Roman 14 pt with zero paragraph spacing between the product heading, structure anchor, and method.
- `Spectra_source.zip`: one primary raw 1H and 13C experiment for every compound.
- `Additional_spectra.zip`: optional 19F, coupled 13C, and minor-diastereomer experiments retained separately.
- `CIF_source`: CIF, ORTEP, metadata, and available checkCIF files for the compounds with X-ray data.
- `Source_files/CIF`: the four additional source CIF files supplied without renaming or conversion.
- `Reference_output.docx`: generated reference support with **Show scope** enabled.
- `provenance.json`: source hashes, spectrum coverage, and CIF mapping.

## Reproduce

```powershell
.venv\Scripts\python.exe -m si_generator `
  --all-in-one-input examples\example_4\All_in_one_input.docx `
  --spectra-source examples\example_4\Spectra_source.zip `
  --cif-source examples\example_4\CIF_source `
  --output output\example_4\support_information.docx `
  --insert-spectra-as png `
  --insert-chemdraw `
  --calculate-elemental-analysis `
  --show-scope `
  --scope-title "Compound scope" `
  --scope-conditions "See individual preparation for reaction conditions"
```

The reference output intentionally retains automated NMR and checkCIF warnings for review. They are diagnostics, not suppressed publication claims.

## Rebuild the input bundle

```powershell
.venv\Scripts\python.exe scripts\build_nmr_all_in_one_example.py `
  --source-docx "C:\path\to\Supporting_inf+ACHT.docx" `
  --fid-zip "C:\path\to\fid.zip" `
  --cif-root "C:\path\to\RSA" `
  --source-cif "C:\path\to\da12838.cif" `
  --source-cif "C:\path\to\da12495.cif" `
  --source-cif "C:\path\to\da12490.cif" `
  --source-cif "C:\path\to\da13053.cif" `
  --output examples\example_4
```
