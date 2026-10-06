# Example 5: real 2D NMR processing

This example contains benzodiazepinones **4a-4e** synthesized by one shared GP3 method. Every compound has raw 1H and 13C data; 4a and 4b additionally contain real HSQC and HMBC experiments.

## Input files

- `All_in_one_input.docx`: combined seven-field Compound table, reaction schema, Scope, SI template, and Crystallography template.
- `Reaction_schema.docx`: one loading scheme for 4a-4e.
- `SI_template.docx`: one range-selected GP3 method, Times New Roman 14 pt, with no extra spacing before the method.
- `Spectra_source.zip`: selected raw Bruker 1D and 2D experiments only.
- `Reference_output.docx`: generated with **Show scope** enabled.
- `provenance.json`: source hashes, extracted molecular formulae, and spectrum coverage.

## Reproduce

```powershell
.venv\Scripts\si-generator.exe `
  --all-in-one-input examples\example_5\All_in_one_input.docx `
  --spectra-source examples\example_5\Spectra_source.zip `
  --output output\example_5\support_information.docx `
  --insert-spectra-as png `
  --insert-chemdraw `
  --calculate-elemental-analysis `
  --show-scope
```

The 2D pages use Mnova-rendered spectra with external 1H/13C projections, axis labels, and the compound structure above the spectrum.
