# Analytical design shapes conclusions about global forest drought recovery

## Version 1.1.0

Author-approved release files by Tao Liu and Xiaozhou Liu, School of Architectural Engineering, Quzhou University. Custom code is MIT licensed. Data, model artifacts and provider-owned products are not relicensed as code. The actual release commit/tag and Zenodo Version DOI are established by the verified release records, not guessed in advance.

Repository: https://github.com/lt2957327761-ops/forest-drought-recovery-inference

Software version series: https://doi.org/10.5281/zenodo.22129069

Data version series: https://doi.org/10.5281/zenodo.22119616

Historical software v1.0.0 used the title *Analytical choices reshape global forest drought-recovery inference — analysis code*. It was published 27 August 2026 at https://doi.org/10.5281/zenodo.22129070 and corresponds to tag v1.0.0 and commit 31dd78e93192e62ca359f4a8a3531f2ce0e073af. Baseline data v1.0.0 were published 28 August 2026 at https://doi.org/10.5281/zenodo.22119617 . Historical identities and scientific files remain unchanged; those version DOIs do not identify the new additions. The older title is a provenance alias.

## Additive scientific support

Historical scientific code, constants, environments and model identities are preserved. The companion data release adds the previously accepted H−1 diagnostic, current figure inputs and Supplementary Table S1. These are not new fits or results selected here for higher AUC.

The tested entry code/10_ei_diagnostics/verify_ei_archive.py checks original inventory/eligibility; keyed P1/P2 assignment and confirmation; three original P1 model hashes without unpickling; frozen H/H−1 products; invalid records/caps; 19 numeric group AUC/grades; the nonnumeric historical Amazon pilot; and Table S1 counts/denominators. The original H-inclusive producer remains historical, not relabelled as strict-before.

The retained diagnostic function bodies under code/10_ei_diagnostics/provenance are PROVENANCE_ONLY and require historical globals/workspace/arrays. They are not a standalone raw-data pipeline. Current plotting entries/helpers are under code/09_figures/ei_current; exact frozen MAT/CSV/table inputs and unchanged PDFs are in the data release. The historical supplementary fire-map wrapper is an I/O portability copy, not a claim that it originally generated the retained PDF.

## Tested verification workflow

Use an isolated Python 3.12 environment; tested versions are Python 3.12.14, NumPy 2.3.5 and PyArrow 26.0.0:

```text
python -m pip install -r requirements-ei-verification.txt
python code/10_ei_diagnostics/verify_ei_archive.py --data-root <EXTRACTED_DATA_RELEASE> --report <OUTSIDE_DATA_ROOT>/verification.json
```

A mismatch in model identity, keys, scores or denominators stops verification. Do not fill invalid records, change labels/thresholds, choose a better AUC or regenerate ER/CI/bootstraps. Report output must stay outside the frozen data root. See docs/EI_REPRODUCTION.md for display entries and docs/REPRODUCTION.md for the historical full-workspace workflow.

## Scientific boundaries and portability

P2 assigns the first qualifying month and confirms in the next adjacent qualifying month. H is realized future inter-drought spacing: strictly-before event AUC is conditional retrospective discrimination, not a prospective prediction. Monthly hazard AUC is distinct. The 240-month cap and H=1 empty product are retained; N_ER/N_AUC differ. Invalid data are not imputed. Fixed performance evaluation ends in 2023; follow-up through 2024 is not refitting. Scales are not independent physical droughts, cell-surface-area weighting is not forest-fraction weighting, and satellite thresholds are not physiological or causal claims. Unsupported/negative results remain.

Inputs use CLI roots or documented environment variables. A literal Windows-path scan found only the retained validation script's drive-detection strings, not operational I/O paths. This does not remove the historical full pipeline's workspace layout and upstream input requirements. MATLAB R2024b, Arial and vendor coastlines.mat are external display dependencies. Current renderer/input checks were static; no fresh drawing export was run. Exact historical Source Data workbook packaging is provenance-only where its toolchain was not frozen.

Frozen-artifact verification was tested. Full raw-to-paper computation, fresh model inference and raw anomaly-array slicing were not rerun. The optional verification environment is separate from unchanged historical fitting/figure pins. CHANGELOG.md and docs/PUBLIC_FILE_MANIFEST.csv document this release; no full raw raster cache, .git directory, dependencies or credentials are distributed.

Use exactly one Zenodo software-archiving route, after checking the account's current GitHub integration setting. An enabled integration archives the authorised GitHub Release; a disabled integration uses the original software record's New version. Do not create competing automatic/manual deposits. Public version citations and links must come from actual verified records.
