# Auto Support Generator starter files

These files are safe to copy and edit for a new SI project.

## Files

| File | Purpose |
| --- | --- |
| `compound_table_starter.docx` | Main Word table example based on `test_input_2.docx`. Use this for production because it can contain editable ChemDraw OLE structures. |
| `spectra_2.zip` | Raw spectra example matching the Word table. Select this as `Spectra source`. |
| `SI_template.docx` | Visual formatting template for the generated Supporting Information. |
| `spectra_source_layout.txt` | Minimal folder/zip layout for raw NMR spectra. |
| `Reaction_schema.docx` | Optional reagent equivalents, MW, density and concentration settings for loadings. |
| `Scope.docx` | Optional reaction scope table used to calculate preparation/loadings text. |
| `classic_1H.mngp` | Default MestReNova graphics profile for 1H spectrum images. |
| `classic_13C.mngp` | Default MestReNova graphics profile for 13C spectrum images. |
| `grid_1H.mngp` | MestReNova 1H graphics profile example with grid enabled. |
| `grid_13C.mngp` | MestReNova 13C graphics profile example with grid enabled. |
| `support_information.docx` | Generated output example for visual comparison. |

## Recommended workflow

1. Copy these files to your project folder.
2. Open `compound_table_starter.docx`.
3. Keep `number` values identical to spectra folders, for example `3a`, `3b`, `3c`.
4. Replace structures, color/state, melting point, Rf and HRMS values with your compound data.
5. Use `spectra_2.zip` as the example spectra source, or prepare your own folder/zip following `spectra_source_layout.txt`.
6. If you need a custom SI style, edit `SI_template.docx`.
7. If you need custom spectrum images, select `classic_1H.mngp` / `classic_13C.mngp`, grid examples, or your own `.mngp` files on the Processing page.
8. If you need reagent loadings, edit `Reaction_schema.docx` and `Scope.docx`.
9. In Auto Support Generator select:
   - `Compound table`: your edited `.docx`;
   - `Spectra source`: your spectra folder or zip;
   - `Output folder`: where the generated SI should be saved.
10. Click `Generate SI`.
