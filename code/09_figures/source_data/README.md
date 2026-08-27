# Source Data workbook packaging provenance

Status: **PROVENANCE_ONLY**.

The retained Python configuration helper and Node workbook builder are stored in `provenance/` to document how the frozen Source Data workbooks were assembled. The Node builder imports `@oai/artifact-tool`; the exact historical package version and an independently installable public toolchain were not frozen. No replacement implementation or guessed package version is supplied.

The frozen Source Data XLSX files and the large Fig. 2 map CSV are deposited with the separate Zenodo dataset. The numerical scientific tables and estimands are defined upstream and do not depend on rerunning this workbook-formatting helper.
