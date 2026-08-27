from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path


SOURCE_PACK_ROOT = Path(os.environ["NEE_SOURCE_PACK_ROOT"]).expanduser().resolve()
OUT = Path(os.environ["NEE_OUTPUT_ROOT"]).expanduser().resolve() / "source_data"
CONFIG_PATH = Path(os.environ.get("NEE_SOURCE_DATA_CONFIG", OUT / "source_workbook_config.json"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_info(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        n_rows = sum(1 for _ in reader)
    return {"path": str(path), "columns": header, "n_rows": n_rows, "sha256": sha256(path)}


def filter_fig2_r2(source: Path, target: Path) -> None:
    with source.open("r", encoding="utf-8-sig", newline="") as fin, target.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.DictReader(fin)
        if reader.fieldnames is None or "recovery_definition" not in reader.fieldnames:
            raise RuntimeError("Fig. 2 map source lacks recovery_definition")
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            if row["recovery_definition"].strip().upper() == "R2":
                writer.writerow(row)


def p(text: str) -> Path:
    path = Path(text)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    fig2_map_source = p(SOURCE_PACK_ROOT / Path("FIG2_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG2_panel_a_current_map_rows.csv"))
    fig2_map_target = OUT / "SourceData_Fig2_panel_a_map.csv"
    filter_fig2_r2(fig2_map_source, fig2_map_target)

    workbooks = [
        {
            "filename": "SourceData_Fig1.xlsx",
            "display_item": "Fig. 1",
            "notes": "Panels a and c are conceptual/illustrative; the workbook supplies the frozen representative observed event and metadata used by panel b.",
            "sheets": [
                ["RepresentativeEvent", p(SOURCE_PACK_ROOT / Path("FIG1_SOURCE_PACK_20260818/03_source_data/FIG1_representative_event_source.csv"))],
                ["EventMetadata", p(SOURCE_PACK_ROOT / Path("FIG1_SOURCE_PACK_20260818/03_source_data/FIG1_representative_event_metadata.csv"))],
            ],
        },
        {
            "filename": "SourceData_Fig2.xlsx",
            "display_item": "Fig. 2",
            "notes": "Panel a plotting rows are supplied separately as SourceData_Fig2_panel_a_map.csv because the map table is large. Only R2 rows plotted by the current final renderer are included.",
            "sheets": [
                ["Panel_b_duration", p(SOURCE_PACK_ROOT / Path("FIG2_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG2_panel_b_median_upper_tail.csv"))],
                ["Panel_c_tails", p(SOURCE_PACK_ROOT / Path("FIG2_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG2_panel_c_tail_probabilities.csv"))],
                ["Panel_d_counts", p(SOURCE_PACK_ROOT / Path("FIG2_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG2_panel_d_completion_counts.csv"))],
                ["Panel_e_censor", p(SOURCE_PACK_ROOT / Path("FIG2_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG2_panel_e_right_censor_rates.csv"))],
            ],
            "external_files": [fig2_map_target],
        },
        {
            "filename": "SourceData_Fig3.xlsx",
            "display_item": "Fig. 3",
            "notes": "Frozen audited feature roles, spatial-block RMSE diagnostic, fixed 2021–2023 exact-duration metrics and monthly-hazard metrics.",
            "sheets": [
                ["Panel_b_features", p(SOURCE_PACK_ROOT / Path("FIG3_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG3_panel_b_feature_roles.csv"))],
                ["Panel_c_RMSE", p(SOURCE_PACK_ROOT / Path("FIG3_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG3_panel_c_RMSE.csv"))],
                ["Panel_d_R2", p(SOURCE_PACK_ROOT / Path("FIG3_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG3_panel_d_temporal_R2.csv"))],
                ["Panel_e_hazard", p(SOURCE_PACK_ROOT / Path("FIG3_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG3_panel_e_hazard_metrics.csv"))],
            ],
        },
        {
            "filename": "SourceData_Fig4.xlsx",
            "display_item": "Fig. 4",
            "notes": "Panel a contains observed-support display geometry rather than archived fold identities; row-level fold assignments/predictions are unavailable. Panels b-e are frozen summaries.",
            "sheets": [
                ["Panel_a_geometry", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_a_geometry.csv"))],
                ["Panel_b_folds", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_b_fold_metrics.csv"))],
                ["Panel_c_temporal", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_c_temporal_metrics.csv"))],
                ["Panel_d_holdouts", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_d_forest_holdouts.csv"))],
                ["Panel_e_bins", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_e_calibration_bins.csv"))],
                ["Panel_e_summary", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG4_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG4_panel_e_calibration_summary.csv"))],
            ],
        },
        {
            "filename": "SourceData_Fig5.xlsx",
            "display_item": "Fig. 5",
            "notes": "The frozen values and target definitions are authoritative. The current final MATLAB renderer has a pooled-row label/order conflict documented in the manuscript audit; this workbook preserves the correctly keyed source rows.",
            "sheets": [
                ["Panel_a_pooled", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG5_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG5_panel_a_pooled_estimands.csv"))],
                ["Panel_b_scales", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG5_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG5_panel_b_scale_specific.csv"))],
                ["Panel_c_targets", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIG5_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIG5_panel_c_target_definitions.csv"))],
            ],
        },
        {
            "filename": "SourceData_ExtendedDataFig1.xlsx",
            "display_item": "Extended Data Fig. 1",
            "notes": "Frozen domain/QC plotting summaries; no inferential analysis.",
            "sheets": [
                ["Domain_map", p(SOURCE_PACK_ROOT / Path("S1_DOMAIN_COVERAGE_QUALITY_REDRAW_20260819/02_DERIVED_SUMMARIES/S1_domain_map_qc.csv"))],
                ["Availability", p(SOURCE_PACK_ROOT / Path("S1_DOMAIN_COVERAGE_QUALITY_REDRAW_20260819/02_DERIVED_SUMMARIES/S1_data_availability_summary.csv"))],
                ["Event_inventory", p(SOURCE_PACK_ROOT / Path("S1_DOMAIN_COVERAGE_QUALITY_REDRAW_20260819/02_DERIVED_SUMMARIES/S1_event_inventory_summary.csv"))],
                ["Regional_QC", p(SOURCE_PACK_ROOT / Path("S1_DOMAIN_COVERAGE_QUALITY_REDRAW_20260819/02_DERIVED_SUMMARIES/S1_regional_qc_summary.csv"))],
            ],
        },
        {
            "filename": "SourceData_ExtendedDataFig2.xlsx",
            "display_item": "Extended Data Fig. 2",
            "notes": "Per-cell all-period right-censor fraction and categorical 2024 endpoint state. 2024 is an endpoint/confirmation year, not a model-evaluation year.",
            "sheets": [
                ["Censor_endpoint_map", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIGS8_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIGS8_censor_endpoint_maps.csv"))],
            ],
        },
        {
            "filename": "SourceData_ExtendedDataFig3.xlsx",
            "display_item": "Extended Data Fig. 3",
            "notes": "Frozen observational GPP/NPP contrasts and descriptive cross-metric interval classification; no causal interpretation.",
            "sheets": [
                ["Functional_contrasts", p(SOURCE_PACK_ROOT / Path("S3_SENSITIVITY_RULE_ROBUSTNESS_20260819/03_DERIVED_DATA/S3_FUNCTIONAL_ROBUSTNESS_DERIVED.csv"))],
                ["Cross_metric", p(SOURCE_PACK_ROOT / Path("S3_SENSITIVITY_RULE_ROBUSTNESS_20260819/03_DERIVED_DATA/S3_CROSS_METRIC_SUMMARY.csv"))],
            ],
        },
        {
            "filename": "SourceData_ExtendedDataFig4.xlsx",
            "display_item": "Extended Data Fig. 4",
            "notes": "Frozen recovery-risk agreement, recurrence-monitoring agreement and conservative evidence-status maps.",
            "sheets": [
                ["Agreement_maps", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIGS5_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIGS5_current_agreement_maps.csv"))],
                ["Evidence_map", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIGS6_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIGS6_current_evidence_maps.csv"))],
            ],
        },
        {
            "filename": "SourceData_ExtendedDataFig5.xlsx",
            "display_item": "Extended Data Fig. 5",
            "notes": "Archived group-level enrichment, hazard AUC, sample support and conservative evidence-status components.",
            "sheets": [
                ["Group_evidence", p(SOURCE_PACK_ROOT / Path("REMAINING_FIGURES_SOURCE_PACK_20260818/FIGS6_SOURCE_PACK_20260818/03_source_data/matlab_ready/FIGS6_archived_group_evidence_components.csv"))],
            ],
        },
    ]

    config = []
    for wb in workbooks:
        row = {k: v for k, v in wb.items() if k not in {"sheets", "external_files"}}
        row["output"] = str(OUT / wb["filename"])
        row["sheets"] = []
        for sheet_name, source in wb["sheets"]:
            info = csv_info(source)
            info["sheet_name"] = sheet_name
            row["sheets"].append(info)
        row["external_files"] = [csv_info(x) for x in wb.get("external_files", [])]
        config.append(row)

    config_path = CONFIG_PATH
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"workbooks": len(config), "fig2_map": csv_info(fig2_map_target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
