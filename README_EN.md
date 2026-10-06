# Auto Support Generator

## X-ray Crystallography, 2D NMR and Multiple Series

Generate accepts an optional **CIF source** folder/ZIP with compound-number subfolders; CIFs may cover only a subset of compounds. The integrated reader inserts structure figures, experimental descriptions and crystal/refinement tables, and saves editable DOCX reports, source CIFs, images and JSON under `reports/crystallography`. Add and Patch preserve these artifacts without reprocessing old spectra.

An optional sidecar JSON supplies crystal-growth/refinement text, CCDC, an external ORTEP image/caption and geometry-table selection. Without an external image, the program makes a labelled coordinate preview, not a thermal-ellipsoid plot. A custom crystallography template may be selected separately or embedded in all-in-one DOCX. Local checks do not replace official checkCIF or CCDC deposition. The default ACS-oriented DOCX is a house template, not an official publisher form.

Raw Bruker HSQC, HMBC, COSY, NOESY, TOCSY and ROESY experiments are detected from acquisition metadata. Version A uses separately processed 1H/13C external projections, independent 8% trace sizes, contour scaling 4.0 and isotope-labelled `1H / ppm` and `13C / ppm` axes; the 13C projection uses Bernstein baseline correction of order 3.

**Multiple series** assembles a folder of series, each with its own Compound_table, optional SI_template and Reaction_schema/Scope. Processing settings are shared; compound numbers must be unique. See the [field reference and requirements](docs/crystallography.md) and [complete runnable example](examples/example_4). Existing installer binaries have not been rebuilt for these source changes.

**English** | [Русский](README_RU.md)

Auto Support Generator is an open-source project licensed under the Apache License 2.0.

## Contact

Questions, feedback, or bug reports are welcome. Contact the author:

- Email: [lebedevdanilaaa@gmail.com](mailto:lebedevdanilaaa@gmail.com)
- Telegram: [@lebdanchem](https://t.me/lebdanchem)

## Installation without Git or Python

1. Open [`installer/AutoSupportGeneratorSetup.exe`](installer/AutoSupportGeneratorSetup.exe) on GitHub.
2. Click **Download raw file** and save the installer. You do not need to clone the repository or install Git.
3. Run `AutoSupportGeneratorSetup.exe`. If Windows SmartScreen appears, verify that the file came from this repository, then select **More info → Run anyway**.
4. Keep the suggested `%LOCALAPPDATA%` path in **Installation folder**, or click **Browse...** and choose another folder.
5. Keep shortcut creation enabled and click **Install**.
6. Launch **Auto Support Generator** from the desktop or Start Menu shortcut.
7. Before the first generation, open Word, ChemDraw, and MestReNova once and complete their initial setup.

Microsoft Word, ChemDraw, and MestReNova are separate licensed applications and are not included in the installer.

### Uninstall

Open **Windows Settings → Apps → Installed apps → Auto Support Generator → Uninstall**, or select **Start Menu → Auto Support Generator → Uninstall Auto Support Generator**. By default, only application files are removed; generated output, settings, and unknown user files are preserved. Clear the keep-user-data option and confirm it only when you intend to remove the entire installation folder.

## License

Copyright © 2026 Danila Lebedev.

This project is licensed under the Apache License, Version 2.0.

See the [LICENSE](LICENSE) file for details.

![Auto Support Generator interface](docs/assets/gui_overview.png)

## Purpose

Auto Support Generator builds organic-chemistry Supporting Information (SI). It transfers ChemDraw structures, physical properties and analytical data into Word, processes NMR spectra in MestReNova, calculates reaction loadings and writes validation reports.

## Features

| Page | What it does |
|---|---|
| **Generate** | Creates a new SI from a compound table and raw spectra and applies a publication preset. |
| **Generate templates** | Parses a method `.docx` into a ready all-in-one input, classic Word inputs, a loadings review table and an audit report. |
| **Processing** | Controls NMR processing, appendix type and analytical validation. |
| **Check** | Checks a previous output: manifest/DOCX/artifact integrity, 1H and 13C counts against the molecular formula, HRMS and elemental analysis; writes a mismatch report. |
| **Patch** | Creates a modified SI copy without reprocessing spectra: renumber, remove, reorder, swap or journal reformatting. |
| **Add** | Appends new compounds without rebuilding old compound blocks. |
| **Instructions** | Provides built-in help, alias tables and downloadable examples. |

The application also preserves editable ChemDraw OLE structures, obtains structure names from ChemDraw, exports PNG or clickable Mnova spectra, calculates HRMS/elemental analysis, validates NMR/HRMS/Anal, calculates reaction amounts and saves processed `.mnova` files, reports, manifests and logs.

## Requirements

| Software | Purpose | Tested version |
|---|---|---|
| Windows 10/11 | application runtime | 64-bit |
| Microsoft Word desktop | DOCX and OLE automation | Microsoft 365 / Word 2021 |
| ChemDraw | structures and names | 22.2.0.3300 |
| MestReNova | NMR processing | 14.2.0-26256 |

Licensed installers are available through the [official ChemDraw download guidance](https://support.revvitysignals.com/hc/en-us/articles/4408210538132-How-do-I-download-the-MSI-installer-for-ChemDraw) and the [official Mnova downloads page](https://mestrelab.com/download). ChemDraw and MestReNova are not bundled with Auto Support Generator and require their own valid licenses.

The packaged application does not require a separate Python installation. Open Word, ChemDraw and MestReNova manually once before the first run and complete their initial setup. If MestReNova is not detected, select its `.exe` on Generate.

## Run from source

This section is for developers. Install Python 3.12, run `Setup Auto SI Generator.bat`, then `Run Auto SI Generator.bat`. Regular users should use the packaged installer described at the beginning of this README.

## Quick start

1. Open **Instructions → Example files → Copy all examples**.
2. Start with `example_1`: edit either the separate Word files or the single `All_in_one_input.docx`.
3. On **Generate**, select a publication preset and choose **Separate files** or **Single all-in-one DOCX**.
4. Select `Spectra_source` and an output folder. Optionally adjust `.mngp` and Processing settings.
5. Review spectrum settings on **Processing**.
6. Click **Generate SI**.
7. When complete, click **Open support** or **Open output folder**.

## Generate fields

### Main inputs

| GUI field | Input |
|---|---|
| **Publication preset** | Target journal. Selection applies its Word template, MNGP profiles, ppm windows and appendix rules; **Apply** restores preset values after manual edits. |
| **Input format** | **Separate files** for the conventional document set or **Single all-in-one DOCX** for one combined file. |
| **Compound table** | `Compound_table.docx`: one row per compound with number, properties, HRMS/IR/Anal and a ChemDraw OLE structure. |
| **All-in-one input** | `All_in_one_input.docx` containing Compound table and optional Reaction schema, Scope, SI template and Crystallography template sections. The X-ray template can therefore travel inside the same file. |
| **Spectra source** | A `Spectra_source` folder or `Spectra_source.zip`, organized by compound number. |
| **Output folder** | Parent folder for results. The app creates a separate run directory and sorts DOCX files, editable Mnova files, PNG images, input copies, reports and logs into subfolders. |

### Optional inputs

| GUI field | Input |
|---|---|
| **SI template .docx** | `SI_template.docx` controlling text, formatting and aliases. This is the custom method template: lay it out like the desired SI and change wording, field order, bold/italic styling and displayed values. When empty, the selected publication template is used. |
| **MestReNova .exe** | `MestReNova.exe` when automatic detection fails. |
| **1H .mngp** | Custom 1H display profile; built-in classic is used when empty. |
| **13C .mngp** | Custom 13C display profile; built-in classic is used when empty. |

### Reagent Loadings

| GUI field | Input |
|---|---|
| **Reaction schema .docx** | `Reaction_schema.docx`: `Reagent_1`, `Reagent_2`, named reagents and solvents with eq, MW, density or concentration. |
| **Scope .docx** | `Scope.docx`: per-product reaction data and structures for variable reagents. |

Enable loadings only when both files are supplied. Product numbers in Compound table and Scope must match.

### Generate templates from a written method

Open **Generate templates** and select the experimental method as a `.docx` file. Explicit masses, amounts, volumes, equivalents, `mol%` and concentrations are parsed locally. The page creates one folder containing:

- `All_in_one_input.docx` with Compound table, Reaction schema, Scope and a complete SI template;
- the same classic inputs as separate `Compound_table.docx`, `Reaction_schema.docx`, `Scope.docx` and `SI_template.docx` files;
- `Loadings_table.docx`, an auditable source-to-mg/mmol/mL/eq/M review table;
- `Method.docx`, a copy of the source method, and `procedure_import_report.json` with unresolved fields and value provenance.

Enter variable compound names exactly as written in the method and in `Reagent_1`, `Reagent_2`, ... order. Optional product numbers prefill both product tables. The importer never invents structures: review every yellow cell, add editable ChemDraw OLE structures and measured masses, then use either the generated all-in-one input or the separate files on **Generate**.

### Preparing the Word inputs

Start with the files under **Instructions → Example files**. Keep their column headers and replace the demonstration values and OLE structures instead of creating new tables from scratch.

**1. Configure the SI template first**

`SI_template.docx` represents one finished compound block. An object names the entity, such as `Product`, `Reagent_1`, `NBS` or `Solvent_CHCl3`; the attribute after the dot selects a property such as `.name`, `.mg`, `.mmol` or `.ml`. Thus `{NBS.mg}` means “calculated NBS mass”, while `{Product.yield.percent}` means “product yield in percent”. The application repeats the block for every product and replaces aliases with values. Bold or italic formatting applied to an alias in Word is inherited by the inserted value.

Include only fields you want in the final SI. A value may be calculated but is displayed only where its alias occurs. For a custom method, change the normal text around aliases and the reagent objects used. In all-in-one mode, place the same template after `[AUTO SI: SI TEMPLATE]`.

**2. Fill Compound table**

| Column | How to fill it |
|---|---|
| `number` | Unique product number such as `2a`. It must exactly match Scope and the spectrum folder name. |
| `structure` | Editable ChemDraw OLE object pasted into the Word cell. Do not replace it with a PNG. The app obtains formula, molecular weight, SMILES and name from this structure. |
| `color` | Appearance such as `white solid`; `-` disables the field for that compound. |
| `mp` | Melting point without `°C`; `-` disables the field. |
| `Rf` | Value and system, for example `0.38 (petroleum ether : ethyl acetate = 7 : 1)`; `-` disables the field. |
| `HRMS` | Experimental found `m/z`; the calculated value and ion formula come from the structure. `-` disables HRMS. |
| `Elemental_analysis` | Experimental values such as `C, 48.38; H, 3.69`; `-` disables Anal. |
| `IR` | IR peak list when this column is used; `-` disables IR. |

**3. Fill Reaction schema**

| Column | How to fill it |
|---|---|
| `Reagents` | Use `Reagent_1`, `Reagent_2`, ... for variable Scope structures; a normal name (`NBS`, `DBP`) for a constant reagent; or `Solvent_CHCl3` for a solvent. `Reagent_1` defines the reaction scale. |
| `equiv.` | Equivalents relative to `Reagent_1`; normally use `1` for `Reagent_1`. |
| `MW, g/mol` | Molecular weight of a constant reagent. For `Reagent_N`, it is extracted from the Scope OLE structure and may remain blank. |
| `Density, g/ml` | Density of a liquid reagent when a calculated volume is required. |
| `Concentration, M` | Solution or solvent concentration when volume is calculated from reaction scale. |

The number of `Reagent_N` objects is not limited to two: add matching `Reagent_3`, `Reagent_4`, and later rows and columns as needed. Each Reaction schema object name must match the start of its alias in SI template.

**4. Fill Scope**

| Column | How to fill it |
|---|---|
| `Reagent_N` | ChemDraw OLE structure of the variable reagent for that series row. |
| `Mass of Reagent_1, mg` | Actual mass of limiting `Reagent_1`; this determines reaction scale. |
| `Product` | Product OLE structure used for molecular weight and name calculation. |
| `Product_number` | The same number as Compound table and Spectra source. |
| `Mass of product, mg` | Isolated product mass used to calculate amount and yield. |

**5. Loading calculation**

1. Molecular weights of variable reagents and products come from ChemDraw; constant reagents use `MW` from Reaction schema.
2. Reaction scale is based on `Reagent_1`: `mmol = mass_mg / MW / equiv`.
3. For each following reagent: `mmol = reaction_scale × equiv`, then `mass_mg = mmol × MW`.
4. For a liquid with density: `volume_mcl = mass_mg / density_g_ml`. For a solution with concentration: `volume_ml = reaction_scale_mmol / concentration_M`.
5. For the product: `product_mmol = product_mass_mg / product_MW`; `yield_percent = product_mmol / reaction_scale_mmol × 100`.
6. The `.g`, `.kg`, `.mol`, `.ml` and `.l` aliases convert the calculated base value; mL volumes are displayed to two decimal places.

If both loading tables are absent, SI generation continues without these calculations. If only one file is supplied or product numbers differ, the app reports the problem instead of silently calculating against mismatched inputs.

### Single all-in-one DOCX

The file is divided by fixed labels:

- `[AUTO SI: COMPOUND TABLE]` — required compound table;
- `[AUTO SI: REACTION SCHEMA]` — optional reagent calculation rules;
- `[AUTO SI: SCOPE]` — optional series data;
- `[AUTO SI: SI TEMPLATE]` — optional output text and formatting;
- `[AUTO SI: CRYSTALLOGRAPHY TEMPLATE]` — optional X-ray description/table template;
- `[AUTO SI: END]` — end of input data.

Standard bundled `All_in_one_input.docx` files contain Compound table, Reaction schema, Scope and SI template. The crystallography example additionally embeds `[AUTO SI: CRYSTALLOGRAPHY TEMPLATE]`; both templates are extracted automatically. If the SI template is absent, the selected publication preset is used. If the X-ray template is absent, the separate field or built-in ACS-oriented template is used. Publication preset, Spectra source, CIF source, Output folder, MestReNova, `.mngp` and Processing remain application settings.

### Reaction and aligned compound scope

Enable **Generate → Show scope** and provide `Reaction_schema.docx` and `Scope.docx`, or their all-in-one sections. Scope contains editable reagent/product structures, matching product numbers and measured masses; yields can also come from percentage yields in the compound table.

The first product row supplies the reaction at the top, with named reagents above the arrow (no equivalents) and solvent below; no `Representative reaction` caption is printed. Enter known conditions in **Reaction conditions**. Each structure has a one-line label such as **2a**, 80%: only the compound number is bold.

The `scope` folder contains editable CDXML, native ChemDraw PNG previews and saved layout data. The PNG overview appears before characterization in Word. Patch updates the overview without NMR processing; Add extends the same series or keeps new methods separate. Installed ChemDraw is required. Turning the option off skips scope generation entirely.

Each numbered example contains the editable input files and a `Reference_output.docx` generated with **Show scope** enabled. Start with [example_1](examples/example_1), use [example_4](examples/example_4) for the complete NMR/X-ray workflow, or [example_5](examples/example_5) for real HSQC/HMBC processing.

## Processing

| Setting | Meaning |
|---|---|
| **Check support** | Validate NMR, HRMS and elemental analysis during generation. |
| **Calculate elemental analysis** | Calculate Anal. from the formula unless the row disables it with `-`. |
| **Spectra appendix** | `png` for static images, `mnova` for clickable objects, `none` to omit the appendix. |
| **1H/13C threshold** | Minimum relative peak height. Increase it when noise or minor impurities are picked. |
| **Signal height** | Fraction of page height used by the tallest signal. |
| **1H/13C ppm range** | X-axis range in exported images. |
| **Highlight solvent peaks** | Show or suppress solvent peaks identified by MestReNova. |
| **Baseline mode** | `auto`, `off`, `Bernstein` or `Whittaker`. |
| **Apply to 1H/13C** | Select nuclei receiving baseline correction. |
| **Whittaker / polynomial parameters** | Expert parameters for the selected baseline algorithm. |

During `13C NMR` validation, the program applies graph-symmetry correction only to isolated phenyl rings. Other carbon atoms are counted individually because local stereochemistry and conformation can remove apparent graph equivalence. If the structure or SMILES is unavailable or inconsistent with the formula, validation uses the full carbon count.

### Chemical validation logic

- **1H NMR:** integral labels such as `1H`, `2H` and `3H` are summed and compared with the number of H atoms in the molecular formula.
- **13C NMR:** symmetry correction is limited to isolated phenyl rings; all other carbons use the full formula count. A single phenyl peak annotated `(2C)` counts as one signal, not two.
- **HRMS:** found `m/z` is compared with the calculated value for the formula and adduct. The base tolerance is 5 ppm, while a publication profile may add journal-specific requirements.
- **Elemental analysis:** experimental element percentages are compared with values calculated from the formula.

This check does not prove a structure and does not replace manual spectrum interpretation. It identifies mismatches that should be reviewed in the input, integration, peak picking or molecular formula.

## Spectra source layout

```text
Spectra_source/
  2a/
    experiment_1H/fid
    experiment_13C/fid
  2b/
    experiment_1H/fid
    experiment_13C/fid
```

Inner experiment names may vary; acquisition metadata identifies 1H and 13C. Top-level compound numbers must match Compound table.

Raw 2D experiment folders contain `ser`. Acquisition metadata identifies HSQC, HMBC, COSY, NOESY, TOCSY and ROESY. Version A uses external 1H/13C projections (8% each), contour scaling 4.0 and isotope-labelled axes; HSQC/HMBC use 13C vertically, while homonuclear experiments use 1H on both axes.

## Check

Select `support_information.manifest.json` from the old run's `docx` folder, optionally override a moved support DOCX, then click **Check support**. Check validates the manifest, compound order, DOCX/artifacts, bookmarks and unresolved aliases. It then repeats the formula-based 1H, 13C, HRMS and elemental-analysis checks from compound snapshots stored in the manifest and writes mismatches to `support_information.check_report.json`. MestReNova is not opened.

## Patch

Choose **Existing output folder**, select exactly one operation and click **Apply patch**. The original SI remains unchanged.

| Operation | Input | Result |
|---|---|---|
| **Renumber** | `2a=3a,2b=3b` | Changes compound numbers and linked references. |
| **Remove** | `2a,2c` | Removes compounds and their appendix pages. |
| **Reorder** | Full list such as `2c,2a,2b` | Reorders blocks; every existing number is required. |
| **Swap compounds** | `2a=3a` | Exchanges complete compound assignments while preserving visible number order. |
| **Reformat existing SI** | Select a target Publication preset | Rebuilds formatting from the manifest while reusing existing data, spectra and ChemDraw OLE. |

Patch reuses processed PNG and Mnova OLE artifacts and does not start new spectrum processing. Every operation creates a new run and leaves the source SI unchanged.

## Add

1. Select **Previous output folder**; manifest and support are detected automatically.
2. Select the Compound table and Spectra source containing only new compounds.
3. Choose a mode and click **Add compounds**.

| Mode | Behavior |
|---|---|
| **Same series** | Reuses the old publication preset, template, Reaction schema and Processing settings. Supply a new Scope. |
| **New method** | Accepts a new publication preset, SI template, Reaction schema and Scope; Processing settings can be adjusted. |

Old blocks are not rebuilt. Duplicate numbers or mismatched numbers across input files stop the operation with an error message.

## Publication presets

On Generate, choose a **Publication preset** and click **Apply**, then adjust individual Processing values if needed. The preset controls the built-in Word template, page/font settings, spectrum windows, default MNGP files, appendix layout and journal-specific validation warnings. Processing values changed after applying a preset are treated as user overrides and recorded in the manifest. In Patch, **Reformat existing SI** applies another preset to an existing SI without rerunning Mnova processing.

| Publisher | Available profiles |
|---|---|
| **ACS** | The Journal of Organic Chemistry (JOC), Organic Letters (Org. Lett.), Journal of Medicinal Chemistry, JACS |
| **RSC** | Organic Chemistry |
| **Wiley** | Angewandte Chemie, Chemistry Europe / EurJOC, Archiv der Pharmazie |
| **Elsevier** | Tetrahedron, Tetrahedron Letters, European Journal of Medicinal Chemistry, Bioorganic & Medicinal Chemistry |
| **Nature Portfolio** | Nature Chemistry, Communications Chemistry |
| **Other** | Molecules, Beilstein Journal of Organic Chemistry, Chemical Papers, General Organic SI |

Profiles use a publisher base plus journal-specific overrides. Bundled DOCX files are reproducible application templates derived from current author guidance, not official publisher templates. Always check the target journal before submission. Source URLs and review dates are written to `support_information.manifest.json`; see [`docs/journal_si_template_requirements.md`](docs/journal_si_template_requirements.md) for the requirements matrix.

## SI template aliases

The SI template looks like the intended output and defines the style of a particular method. Place `{Object.attribute}` aliases directly in Word; bold/italic formatting applied to an alias is inherited by the generated value. The object before the dot identifies the entity (`Product`, `Reagent_1`, `NBS`), and the attribute after it selects the required property (`name`, `mg`, `mmol`, `yield.percent`). For example, `{Reagent_1.name}` and `{Reagent_1.mmol}` refer to one object but display different properties.

- Product: `{Product.name}`, `{Product.number}`, `{Product.structure}`, `{Product.mg}`, `{Product.mmol}`, `{Product.yield.percent}`, `{Product.appearance}`, `{Product.mp}`, `{Product.rf.value}`, `{Product.rf.system}`, `{Product.nmr.1h.picture}`, `{Product.nmr.13c.picture}`.
- Reagents: `{Reagent_1.name}` and `.mg`, `.g`, `.kg`, `.mmol`, `.mol`, `.mcl`, `.ml`, `.l`, `.eq`, `.number`. The same attributes work for named reagents and solvents.
- NMR: `{nmr.1h.label}`, `{nmr.1h.conditions}`, `{nmr.1h.peaks}`; equivalent `nmr.13c` fields; `{nmr.extra}`.
- HRMS: `{hrms.label}`, `{hrms.adduct}`, `{hrms.formula}`, `{hrms.calculated}`, `{hrms.found}`.
- Anal: `{anal.label}`, `{anal.formula}`, `{anal.calculated}`, `{anal.found}`.
- IR: `{ir.label}`, `{ir.method}`, `{ir.peaks}`.

The full field-by-field alias table is available under **Instructions → Template aliases**.

## Examples

The repository and **Instructions → Example files** include base and extended examples:

| Folder | Contents |
|---|---|
| [`examples/example_1`](examples/example_1) | First series, compounds 2a–2d; Spectra source folder. |
| [`examples/example_2`](examples/example_2) | Series continuation, compounds 2e–2f. |
| [`examples/example_3`](examples/example_3) | New method, compounds 3a, 3b, 3c, 3d, 3i; Spectra source folder and zip. |
| [`examples/example_4`](examples/example_4) | Complete all-in-one example with 28 compounds, editable scope, raw 1H/13C for every compound and X-ray data for the available subset. |
| [`examples/example_5`](examples/example_5) | Five benzodiazepinones with raw 1H/13C for every compound and real HSQC/HMBC experiments for 4a and 4b. |

Every set uses GUI-matching names and includes a `Reference_output.docx` generated with **Show scope**.

## Output

Each run creates `output/runs/YYYYMMDD_HHMMSS_name/`:

| Folder | Contents |
|---|---|
| `docx/` | `support_information.docx`, `support_information.manifest.json`, and `support_information.run_summary.json` |
| `input/` | copies of Word inputs, `.mngp` profiles, and the Spectra source used for the run |
| `spectra/` | `processed_spectra/`, PNG files, and `processed_spectra.zip` when spectra were processed |
| `mnova/` | `processed/` with processed and single-spectrum `.mnova` files used by clickable objects |
| `logs/` | run, Word/ChemDraw/Mnova automation logs, and `mnova_reports/` |
| `reports/` | NMR text and validation reports; Add and Patch runs also write their operation-specific JSON report |

Each generation has its own folder, so an earlier SI is never overwritten. `mnova/processed/` contains separate editable 1H and 13C `.mnova` files, while `spectra/` contains the corresponding PNG images. In `mnova` appendix mode, double-click a spectrum picture inside `support_information.docx`, edit it in MestReNova, then save it back to Word. This supports manual correction of labels, peaks and scale after automatic processing.

`support_information.manifest.json` connects compounds, DOCX blocks, settings and artifacts and is required by Check, Patch and Add. `support_information.run_summary.json` contains the run result and warning list. If a run fails, inspect its `logs/` folder first. Do not keep the output DOCX open while regenerating because Word locks it. Attach the run summary and `logs/` folder when reporting a problem.
