# Auto Support Generator

Auto Support Generator assembles organic chemistry Supporting Information (SI)
documents from a compound table and NMR spectra. The program can copy ChemDraw
OLE structures from a Word table, process spectra through MestReNova, generate
NMR descriptions and spectrum images, calculate HRMS values, and build a final
`.docx` file in a journal-like format.

The project is currently Windows-oriented because ChemDraw, Word OLE objects,
and MestReNova automation are used through desktop applications.

## What The Program Produces

For one run, choose an output file such as:

```text
output/support_information.docx
```

The generator creates this folder structure:

```text
output/
  support_information.docx
  processed_spectra.zip
  processed_spectra/
    2a/
      2a_1H.png
      2a_13C.png
      2a.mnova
  processed_mnova/
    2a/
      2a.mnova
  mnova_reports/
    2a/
      2a_1H.txt
      2a_13C.txt
  logs/
    mnova_batch/
    spectrum_images/
    _spectra_zip/
```

`support_information.docx` is the final SI file.

`processed_spectra.zip` is the user-facing archive with one folder per
compound. Each compound folder contains the generated spectrum PNG files and
one processed `.mnova` file containing both 1H and 13C spectra in the same state
used to export the PNG images.

`logs/` contains temporary and diagnostic files. It can be kept for debugging or
deleted after the result is checked.

## Quick Start With The GUI

The easiest way to use the project is the graphical interface.

1. Install the Python dependencies.
2. Open the project folder.
3. Double-click:

```text
SI Generator GUI.bat
```

In the GUI:

1. Select the table type:
   - `Word table with ChemDraw objects` for `.docx` tables where the first
     column contains ChemDraw/ChemSketch OLE structures.
   - `CSV table` for a plain CSV workflow.
2. Choose the compound table.
3. Choose the spectra `.zip` file.
4. Optionally choose a Word template `.docx`.
5. Optionally choose `style_config.yml`.
6. Choose the output `.docx` path.
7. Leave `Check support` enabled if you want NMR/HRMS warnings in the final
   document.
8. Click `Generate SI`.

The log window shows MestReNova processing status and the path to the generated
files.

## Installation

Recommended setup on Windows:

```powershell
cd C:\Users\user\Desktop\Auto_support_generator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

External desktop software used by the full workflow:

- Microsoft Word
- ChemDraw or another compatible OLE structure editor in the input document
- MestReNova installed at:

```text
C:\Program Files\Mestrelab Research S.L\MestReNova\MestReNova.exe
```

## Input Word Table

For the main workflow, prepare a Word document with a table. The first row is a
header row. Each next row describes one compound.

The first column should contain the compound number and the ChemDraw/ChemSketch
OLE structure object. The generator uses this object as the real structure in
the final SI.

Common columns:

| Column | Meaning |
| --- | --- |
| `number` | Compound number, for example `2a` |
| `name` | Compound name. If empty, the program can try to extract it from the structure |
| `preparation` | Synthetic procedure text |
| `yield` | Yield, for example `492 mg (31%)` |
| `color` | Color, for example `white` |
| `state` | State, for example `solid` or `oil` |
| `melting_point` | Melting point without `mp`, for example `81-82 °C` |
| `rf` | TLC/Rf text |
| `formula` | Neutral molecular formula |
| `hrms_adduct` | Adduct, for example `[M+H]+` |
| `hrms_found` | Experimental HRMS value |
| `h1_nmr` | Optional manually written 1H NMR description |
| `c13_nmr` | Optional manually written 13C NMR description |
| `extra_nmr` | Optional extra NMR lines, for example 19F NMR |
| `ir` | Optional IR line |

If spectra are supplied, the generator fills `h1_nmr` and `c13_nmr`
automatically from MestReNova.

## Spectra Zip Format

The spectra archive should contain one folder per compound number:

```text
spectra.zip
  2a/
    2a_1H/
      fid
      acqus
      ...
    2a_13C/
      fid
      acqus
      ...
  2b/
    ...
```

The exact experiment folder names are flexible. The program searches for Bruker
`fid` files and reads `acqus`/`acqu` to detect `1H` or `13C`.

For every compound, the expected result is:

```text
processed_spectra/
  2a/
    2a_1H.png
    2a_13C.png
    2a.mnova
```

## MestReNova Processing

The generator opens all spectra in one MestReNova session for better speed.

Current processing behavior:

- 1H spectra are referenced to the solvent peak:
  - CDCl3: 7.26 ppm
  - DMSO-d6: 2.50 ppm
- 13C spectra are referenced to the solvent peak:
  - CDCl3: 77.16 ppm
  - DMSO-d6: 39.52 ppm
- 13C spectra receive baseline correction before final peak picking.
- 1H images show the -1 to 12 ppm range.
- 13C images show the -10 to 210 ppm range.
- 1H images keep integral labels below the spectrum but hide the upper integral
  curve and multiplet labels.
- 13C images show peak picking only.

## Support Check

The GUI option `Check support` controls validation warnings.

When enabled, the generator checks:

- whether the number of protons in the 1H NMR description matches the molecular
  formula;
- whether the number of carbons in the 13C NMR description matches the molecular
  formula;
- whether experimental HRMS matches the calculated value within tolerance.

Warnings are added to the final `.docx` as red `Support check` notes. Disable
the option if you want a clean document without these warnings.

## Formatting Templates

Formatting has two layers.

### Word Template

Use `--template-docx` or the GUI `Template .docx` field to provide margins, page
setup, default fonts, and named Word styles.

The generator clears the body of the template and inserts the generated SI into
that document, preserving styles and page settings.

### style_config.yml

Use `style_config.yml` for semantic formatting rules: which parts are bold,
italic, superscript, subscript, and how far structures are shifted.

Start from:

```text
style_config.example.yml
```

Important options:

```yaml
compound:
  title:
    bold: true
    italic: false
  structure:
    top_offset_pt: 12

nmr:
  label:
    bold: true
  body:
    bold: false

chem_formatting:
  isotope_numbers:
    superscript: true
  formulas:
    subscripts: true
  coupling_constants:
    j_italic: true
    order_superscript: false
    coupling_partner_subscript: false

hrms:
  label:
    bold: true
  formula:
    subscripts: true
```

For example, set `chem_formatting.coupling_constants.j_italic: true` to make
the `J` symbol in coupling constants italic.

## Command Line Usage

Word table workflow:

```powershell
$env:PYTHONPATH = "src"
python -m si_generator `
  --word-input C:\path\to\input.docx `
  --spectra-zip C:\path\to\spectra.zip `
  --style-config style_config.example.yml `
  --output output\support_information.docx
```

CSV workflow:

```powershell
$env:PYTHONPATH = "src"
python -m si_generator `
  --input data\compounds.csv `
  --output output\support_information.docx
```

Disable support checking:

```powershell
python -m si_generator `
  --word-input C:\path\to\input.docx `
  --spectra-zip C:\path\to\spectra.zip `
  --no-check-support `
  --output output\support_information.docx
```

Launch GUI from command line:

```powershell
$env:PYTHONPATH = "src"
python -m si_generator.gui
```

If the package is installed with `pip install -e .`, these commands are also
available:

```powershell
si-generator
si-generator-gui
```

## Repository Notes

Do not commit generated output folders, temporary MestReNova files, extracted
spectra, `.mnova` batches, or Python cache files. These are ignored by
`.gitignore`.
