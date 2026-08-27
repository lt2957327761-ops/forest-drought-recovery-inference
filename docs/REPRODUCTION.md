# Reproduction guide

## 1. Clone repository

Clone or download `forest-drought-recovery-inference`. No Git command was executed when this author-review package was assembled.

## 2. Install the appropriate environment tier

```text
Core analysis environment:
    requirements-core.txt

Python figure environment:
    requirements-figures.txt

Optional IFL/geospatial preprocessing:
    requirements-optional-geospatial.txt
```

For core analysis plus Python figures:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-core.txt
python -m pip install -r requirements-figures.txt
```

Alternatively, `conda env create -f environment.yml` installs the exact verified core and Python figure/runtime tiers. It intentionally excludes the optional IFL packages because their exact historical versions were not retained.

For optional IFL reacquisition/harmonization, install the core tier first, then:

```powershell
python -m pip install -r requirements-optional-geospatial.txt
```

The Data16 script actually imports `pyogrio`, `pyproj` and `shapely` in addition to core NumPy/Rasterio. `pandas` and `geopandas` appear only in a retained historical installation-help message and are not imported by that script, so they are not added by convention. MATLAB R2024b is external to the Python environment.

## 3. Obtain the Zenodo dataset

Download and extract dataset version 1.0.0 from `https://doi.org/10.5281/zenodo.22119617` after publication. Until publication, the DOI is reserved. Do not place the archive in Git.

## 4. Optional upstream reacquisition

Review `code/01_acquisition` and `docs/DATA_MANIFEST.md`. Earth Engine files must be run manually in an authenticated Earth Engine environment and require network access. Product-level MOD44B and MERIT scripts are representative batch templates; no automatic job launcher is supplied. Starting from Zenodo skips this stage.

## 5. Configure paths

Copy `config/paths.example.yaml` outside the repository or set environment variables:

```powershell
$env:NEE_PROJECT_ROOT = (Resolve-Path '<FULL_PROJECT_WORKSPACE>').Path
$env:NEE_ZENODO_DATA_ROOT = (Resolve-Path '<EXTRACTED_ZENODO_DATA>').Path
$env:NEE_RELEASE_DATA_ROOT = (Resolve-Path '<FROZEN_RENDERER_INPUT_LAYOUT>').Path
$env:NEE_OUTPUT_ROOT = '<OUTPUT_DIRECTORY>'
$env:NEE_DATA16_ROOT = '<IFL_WORKSPACE>'
$env:NEE_DATA16_DOWNLOAD_DIR = '<IFL_DOWNLOAD_DIRECTORY>'
$codeDirs = Get-ChildItem -LiteralPath '.\code' -Directory | ForEach-Object FullName
$env:PYTHONPATH = $codeDirs -join [IO.Path]::PathSeparator
```

The historical pipelines expect a full-workspace layout beneath `NEE_PROJECT_ROOT`; the Zenodo dataset is a minimum reproduction release, not a reconstruction of the raw development directory tree.

## 6–12. Pipeline stages

| Step | Script / entry point | Expected input | Expected output | Depends on | Network / GEE | MATLAB R2024b |
|---|---|---|---|---|---|---|
| 6a. Forest domain and static inputs | `code/02_harmonization/build_global_inputs.py` | reacquired upstream rasters | 0.5° forest eligibility and harmonized static/monthly inputs | optional acquisition | No after download | No |
| 6b. Monthly state | `code/02_harmonization/task0010a_monthly.py` | harmonized raw inputs and forest mask | monthly kNDVI/climate/SPEI/fire/productivity state | 6a | No | No |
| 6c. Events | `code/03_event_detection/task0010a_events.py` then `task0010c_events.py` | monthly/static state | frozen events and corrected R2 events | 6a–6b | No | No |
| 6d. P2 persistence | `code/04_recovery/task0010e_persistence.py dry-run`, `events`, then `assemble` | corrected P1 events/screen | P1/P2 event endpoints and summaries | 6c and model stage | No | No |
| 7a. Corrected models | `code/05_models/task0010c_models.py` | corrected events and 27-feature prospective design | exact-duration RF and 29-column monthly-hazard validation products | 6c | No | No |
| 7b. Validation | scripts in `code/06_validation` | frozen model outputs | spatial, fixed 2021–2023, structural and calibration summaries | 7a and P2 | No | No |
| 8. Enrichment | `code/07_estimands/task0010c_consensus.py` | modeled events and corrected pixels | event/cell/forest-cell-area estimands and 500-draw block intervals | 7a | No | No |
| 9. Functional/fire/group results | same `task0010c_consensus.py` | D3 2001–2020 training events, GPP/NPP and fire fields | observational functional contrasts and evidence/status tables | 8 | No | No |
| 10. Main figures | MATLAB scripts and `Fig3_Nature_final_v04.py` in `code/09_figures` | frozen renderer-input MAT/CSV files | Figs. 1–5 | stages 7–9 or archived Source Data | No | Yes except Fig. 3 |
| 11. Extended Data figures | `ExtendedDataFig*.m` in `code/09_figures` | frozen renderer-input CSV files | Extended Data Figs. 1–5 | stages 7–9 | No | Yes |
| 12. Source Data provenance | `code/09_figures/source_data/provenance/` | retained source-pack CSV paths | historical workbook-packaging record | archived source packs | No | No |

### Corrected-model execution order

```powershell
python code/05_models/task0010c_models.py --scale D1
python code/05_models/task0010c_models.py --scale D3
python code/05_models/task0010c_models.py --scale D6
python code/05_models/task0010c_models.py --assemble
```

### Source Data workbook builder classification

`NODE_SOURCE_DATA_BUILDER = PROVENANCE_ONLY`.

The retained Node builder imports `@oai/artifact-tool`. Its exact historical version and an independently installable public workbook-packaging toolchain were not frozen. The builder and its Python configuration helper are retained unchanged in `code/09_figures/source_data/provenance/`; no replacement implementation or guessed dependency version is supplied. The frozen Source Data XLSX files are deposited in the Zenodo dataset. Numerical scientific tables and estimands are produced upstream and do not depend on rerunning workbook formatting.

## Metric terminology

The historical output field `pr_auc` is computed with `sklearn.metrics.average_precision_score` and is therefore reported publicly as **average precision**, not trapezoidal precision–recall AUC.

## Fixed scientific boundaries

Training is 2001–2020. Fixed model evaluation is January 2021 through December 2023. The year 2024 is used only for endpoint confirmation/current censoring status, never performance selection. No missing-value interpolation is performed. Retrospective recovery-period climate models are association diagnostics only.
