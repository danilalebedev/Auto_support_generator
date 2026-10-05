# Crystallography integration verification

Verified locally on Windows on 2026-10-05. Tests ran against a clean snapshot of the staged CIF/multiple-series changes, excluding unrelated in-progress changes in the shared checkout.

## Automated checks

- Complete snapshot suite: 327 tests passed, including 6 subtests.
- Final focused rerun: 59 tests passed (crystallography, multiple-series and GUI workflows).
- Covered partial CIF coverage, wrong compound labels, malformed CIF, multiblock CIF, archive traversal rejection, field extraction and diffraction-temperature precedence.
- Covered Generate, Add, renumber, remove and journal reformat with saved crystallography artifacts, including a relocated output folder.
- Covered independent reaction loadings for two series, duplicate labels and incomplete Reaction schema/Scope input.

```powershell
python -m pytest -q
python -m pytest -q tests/test_crystallography_node.py tests/test_series_workflow.py tests/test_gui_workflow.py
```

## Real data

Both the single-input and Multiple series examples completed with installed MestReNova and the supplied raw data. Each output contains four compounds, eight NMR spectra and three crystal structures. The 15-page single-input output and its Word input tables/template were rendered using Microsoft Word and visually inspected. CIF table values and CCDC mappings were checked against the supplied sources. The example uses original ORTEP images, not generated substitutes.

## Remaining review

- Raw NMR processing reports carbon-count mismatches and one proton-count mismatch. These warnings are preserved, not treated as successful chemical validation.
- Existing spectrum structure overlays can overlap peak labels. The non-CIF NMR renderer was not redesigned in this change.
- The existing analytical-text formatter displays one digit in the C22 formula for 3s as superscript; check formula typography before publication. CIF tables preserve the source formula text.
- No official checkCIF submission, CCDC deposition or journal acceptance check was performed.
- The generated coordinate preview is not an ORTEP/thermal-ellipsoid image and does not symmetry-complete molecules.
- Installer dependency collection was updated, but an installer was not built or installation-tested in this task.
- The four-compound example is not a conversion of the complete source article. Original preparation/loadings are retained as text; calculated multi-method loadings are covered separately by automated tests.
