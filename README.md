# Analytical choices reshape global forest drought-recovery inference — analysis code

## Authors

- Tao Liu
- Xiaozhou Liu

School of Architectural Engineering, Quzhou University, Quzhou 324000, China. Correspondence: 2957327761@qq.com.

## Scope

This repository contains the custom acquisition, harmonization, event, operational recovery, model-evaluation, validation, estimand, functional-analysis, figure and Source Data provenance code supporting the manuscript. Historical script filenames are retained where changing them would weaken import compatibility or provenance.

## Data, code and DOI status

- **Data DOI:** `10.5281/zenodo.22119617` — reserved; it becomes active when the dataset is published.
- **Code repository:** `https://github.com/lt2957327761-ops/forest-drought-recovery-inference`.
- **Software DOI:** not yet assigned.

The separate dataset release is *Data supporting “Analytical choices reshape global forest drought-recovery inference”*, version 1.0.0. The data archive is intentionally not included in this repository.

## Repository structure

- `code/01_acquisition`: product-level Earth Engine export definitions and IFL acquisition notes; optional and not run automatically.
- `code/02_harmonization`: temporal/spatial harmonization, 0.5° forest domain and required helper modules.
- `code/03_event_detection`: frozen drought-event and corrected OLD/R1/R2 event logic.
- `code/04_recovery`: P1/P2 recovery, censoring and persistence sensitivity.
- `code/05_models`: prospective exact-duration, retrospective diagnostic and monthly-hazard models.
- `code/06_validation`: spatial, temporal, structural, calibration and data-integrity checks.
- `code/07_estimands`: event/cell/forest-cell-area estimands, block bootstrap, functional/fire and group evidence.
- `code/08_functional`: navigation notes for shared screen/functional/fire implementations.
- `code/09_figures`: final main/Extended Data renderers and Source Data packaging provenance.

## Reproducibility tiers

- **Core numerical analysis:** Python 3.11.9 with exact verified pins in `requirements-core.txt`.
- **Python figure generation:** exact verified Matplotlib, pandas and Pillow versions in `requirements-figures.txt`; install after the core requirements.
- **MATLAB displays:** MATLAB R2024b; most final display renderers are MATLAB scripts.
- **Optional IFL preprocessing:** `requirements-optional-geospatial.txt`; exact historical geospatial versions were not retained.
- **Source Data workbook builder:** **PROVENANCE_ONLY**. The historical `@oai/artifact-tool` version/public toolchain was not frozen. Frozen Source Data XLSX files are deposited with the Zenodo dataset, and numerical estimands do not depend on rerunning workbook formatting.

The machine-readable environment records the exact verified core and Python figure/runtime tiers. It does not claim that every ancillary historical package version was frozen.

## Reproduction

See `docs/REPRODUCTION.md`. Paths use environment variables or templates in `config/`; no public command depends on the original development drive.

## Scientific boundaries

Recovery definitions are operational satellite definitions. Recovery-period climate variables are retrospective diagnostics, not drought-end forecasts. Functional comparisons are observational, and evidence/status products are screening summaries rather than causal or intervention estimates. The code reproduces frozen reported analyses; it does not imply causal inference.

## Licence and citation

Custom code is released under the MIT License. This licence does not apply to third-party upstream datasets. Cite the software using `CITATION.cff` and cite the data release separately after its reserved DOI becomes active.
