# Auto Support Generator starter files

These files are safe to copy and edit for a new SI project.

## Files

| File | Purpose |
| --- | --- |
| `compound_table_starter.docx` | Word table template. Use this when you want to paste ChemDraw OLE structures into the first column. |
| `compound_table_starter.csv` | CSV table template with all commonly used fields and 3 filled examples. Use this for quick tests or projects without editable OLE structures. |
| `SI_template.docx` | Visual formatting template for the generated Supporting Information. |
| `spectra_source_layout.txt` | Minimal folder/zip layout for raw NMR spectra. |
| `Reaction_schema.docx` | Reagent equivalents, MW, density and concentration settings for loadings. |
| `Scope.docx` | Reaction scope table used to calculate preparation/loadings text. |
| `grid.mngp` | MestReNova graphics profile example with grid enabled. |
| `classic.mngp` | MestReNova graphics profile example with grid disabled. |

## Recommended workflow

1. Copy these files to your project folder.
2. Open `compound_table_starter.docx`.
3. Keep the first column as a clean compound number, for example `2a`.
4. Paste editable ChemDraw OLE structures into the `structure` column.
5. Replace example formulas, physical properties, HRMS, IR, elemental analysis and spectra paths.
6. Put raw spectra into a folder or zip archive following `spectra_source_layout.txt`.
7. If you need reagent loadings, edit `Reaction_schema.docx` and `Scope.docx`.
8. If you need a custom spectrum image style, select `grid.mngp`, `classic.mngp`, or your own `.mngp` on the Processing page.
9. In Auto Support Generator select:
   - `Compound table`: your edited `.docx`;
   - `Spectra source`: your spectra folder or zip;
   - `Output folder`: where the generated SI should be saved.
10. Click `Generate SI`.

If you use the CSV file instead of Word, structures will not be editable ChemDraw OLE objects unless you also provide structure files and enable the corresponding workflow.
