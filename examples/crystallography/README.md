# Crystallography example

Four compounds from the author-supplied Supporting Information: 3a, 3c, 3f and 3s.
Only 3c, 3f and 3s have CIF data. Original ORTEP figures and crystal-growth descriptions are preserved.

1. Generate: select `Compound_table.docx`, `Spectra_source.zip` and `CIF_source`.
2. Leave Crystallography template blank for the built-in template, or choose `Crystallography_template.docx` to edit it.
3. Click Generate SI. Word and licensed MestReNova are needed for the complete raw-spectra workflow.
4. Alternatively, choose Multiple series and the `Multiple_series` folder to assemble methods A and B together.

Preparation/loadings text is copied from the supplied SI, not recalculated in this example.
NMR validation warnings must be reviewed by a chemist. The template does not imply journal acceptance or completed CCDC/checkCIF submission.

## Example output

[Reference_output.docx](Reference_output.docx) is the actual generated 15-page draft for these four compounds: eight processed NMR spectra and three crystallography figures/tables. It is a compact integration example, not the complete source article.

The red NMR warnings are intentionally preserved. Peak picking and integrals need review; existing spectrum labels can overlap the structure overlay. This document demonstrates CIF integration, not a publication-ready or scientifically approved SI. The supplied ORTEP figures are reused; the automatic coordinate preview is not a thermal-ellipsoid plot.

The DOCX snapshot alone is not a portable Patch/Add package. Generate a fresh output folder to obtain its manifest, reports, editable spectra and copied CIF files; keep that folder together.

See [the Russian guide and field reference](../../docs/crystallography.md).
Rebuild from the author's original files using `scripts/build_crystallography_example.py`.
