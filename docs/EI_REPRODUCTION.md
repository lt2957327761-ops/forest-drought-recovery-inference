# Frozen EI reproduction guide

## Tested numerical verification

Extract the companion data update (historical base directories plus09_EI_UPDATE). Use a disposable environment and a report directory outside the extracted data root:

```text
python -m pip install -r requirements-ei-verification.txt
python code/10_ei_diagnostics/verify_ei_archive.py --data-root <EXTRACTED_DATA_UPDATE> --report <OUTSIDE_DATA_ROOT>/verification.json
```

This checks original Parquet inventory/eligibility, P1/P2 assignment/confirmation, keyed event/model identity, all stored H/H−1 products, invalid records/caps, rank-based AUCs for19groups, unchanged grades and sixTableS1rows/denominators. ER/intervals are not re-estimated; single-class AUC stays undefined. Amazon remains limited and nonnumeric. The test environment was Python3.12.14/NumPy2.3.5/PyArrow26.0.0, distinct from historical fitting pins.

S5NPZ arrays areevent_id,H,offset,q_recovery_hazard,model_sha256. They contain accepted original frozen-model probabilities, not new predictions. FrozenP1weights are supplied but the verifier never unpickles them. Do not deserialize untrusted models. Historical exact-H and identity evidence is under09_EI_UPDATE/provenance.

TableS1verification uses accepted keyed B2 derived fields, not re-created anomalies. The original array-slice audit needs historical anomaly arrays/full workspace, not redistributed here. It is documented but not freshly repeated. No model fit/inference, event identification, bootstrap or upstream acquisition is run.

The exact accepted Stage2C diagnostic function/class bodies are retained in `code/10_ei_diagnostics/provenance/stage2c_diagnostic_functions.py`, with original line/SHA/AST evidence in the data package. This is explicitly PROVENANCE_ONLY: it needs the original globals, model inputs, workspace and arrays, and must not be advertised as a standalone executable. The portable entry above is the tested numerical archive verifier.

## Current display code

CurrentPDFs are under09_EI_UPDATE/Figures, data underSourceData. No renderer was run or figure replaced in this task. Future authorized display reproduction uses the original figure pins (Python3.11.9/Matplotlib3.10.9) and outputs outside frozen data:

```text
python code/09_figures/ei_current/render_current_ei.py --data-root <EXTRACTED_DATA_UPDATE> --output-root <NEW_OUTPUT> --figure 3
python code/09_figures/ei_current/render_current_ei.py --data-root <EXTRACTED_DATA_UPDATE> --output-root <NEW_OUTPUT> --figure 6
python code/09_figures/ei_current/render_current_ei.py --data-root <EXTRACTED_DATA_UPDATE> --output-root <NEW_OUTPUT> --figure S4
```

For MATLABR2024b current copies, setNEE_RELEASE_DATA_ROOT to<EXTRACTED_DATA_UPDATE>/09_EI_UPDATE/figure_renderer_inputs (containsfigure_inputs) andNEE_OUTPUT_ROOT to a new output folder. Addcode/09_figures/ei_current; callFig1_Nature_final_v03,Fig2_Nature_final_v03,Fig4_Nature_final_v09e_final,Fig5_corrected_v09,FigS1_Nature_final_v03,FigS2_Nature_final_v03_editable. Each file includes local helpers; MAT/CSV dependencies are included. Arial/fonts and toolboxes affect pixels/export.

The original map overlays require MATLAB's `coastlines.mat` (Mapping Toolbox data), not redistributed here. It was located in the audit host's installed R2024b; other hosts must provide their licensed vendor resource. Fig1 is a script with local helper functions, not a renamed helper entry. None of these display scripts was executed for this update.

S3's unchanged PDF and historical `ExtendedDataFig4_maps_final_v01.m` reference are retained. An added `FigS3_EI_current.m` wrapper preserves the complete original plotting body and helpers, fixing only its function/file match and input/output paths. Set `EI_ZENODO_DATA_ROOT` to the extracted candidate data root and `NEE_OUTPUT_ROOT` to a new outside output folder. This wrapper was statically verified but not executed; it is not falsely described as the script originally used to create the retained PDF. Workbook formatting remains provenance-only where the original toolchain was not frozen. Static checks do not establish a fresh byte-identical figure export.

## Historical full pipeline and limitations

Original core/figure pins remain unchanged. docs/REPRODUCTION.md remains a historical workflow, including original H-inclusive outputs. It needs upstream products and original workspace/cache conventions; the minimum deposit is not a full raw-data workspace. Original source model inference and array checking were not executed here. Stop on a score error>1e−12, missing key/model identity, changed cohort/labels or TableS1discrepancy. Never repair a failure by changing frozen data or choosing a higher AUC.
