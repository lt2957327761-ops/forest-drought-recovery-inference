# v1.0.0 — Manuscript submission release

Release date: pending author publication.

This is the frozen code release supporting the manuscript. The public data are archived separately on Zenodo under reserved DOI `10.5281/zenodo.22119617`; a software DOI will be assigned only after a later GitHub–Zenodo release archive is created by the authors.

## Scientific status

- No data were recomputed, models refitted, hyperparameters tuned, events reidentified or scientific values changed while assembling this repository.
- Core scripts were taken from the vetted V15 release snapshot.
- Two required helper modules omitted from that snapshot were restored from their frozen source locations.
- Active Figure 3 helper files were retained because the v04 renderer imports them.
- Obsolete manuscript builders, snapshots, contact-sheet tools, duplicate/historical renderers and third-party replication code were excluded and remain documented in `SCRIPT_INVENTORY.csv`.

## Portability-only changes

- Local development roots in `task0004_lib.py`, `task0008a_lib.py` and `audit_spei_fire_inputs.py` now read `NEE_PROJECT_ROOT`.
- Source Data preparation now reads `NEE_SOURCE_PACK_ROOT`, `NEE_OUTPUT_ROOT` and `NEE_SOURCE_DATA_CONFIG`.
- Source Data workbook generation now reads its JSON configuration and preview directory from environment variables.
- The optional IFL acquisition note now reads `NEE_DATA16_DOWNLOAD_DIR` instead of a development-machine path.
- V15 scripts that already used environment variables were copied without further content edits.

These changes alter paths only. All formulas, scientific constants, cohort rules, features, filters, seeds, model specifications and estimands remain frozen.
