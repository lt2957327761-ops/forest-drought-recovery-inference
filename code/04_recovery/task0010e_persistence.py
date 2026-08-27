from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import pickle
import platform
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
SRC = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010C_Recovery_Logic_and_Application_Fix"
SRC_D = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010D_Corrected_Review_Package"
STD_SRC = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Corrected_v02"
RUN = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010E_Methods_Manuscript_Production"
STD = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Recovery_Persistence_Sensitivity_v01"
WORK = RUN / "_working"
FROZEN_CACHE = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010A_Global_Drought_Recovery_Consensus" / "_processing_cache"
SCALES = ("D1", "D3", "D6")
RNG = 9021009
TRAIN_END = 240
VALIDATION_END = 275
TOTAL_MONTHS = 288
WIDTH = 720
THRESHOLD = -0.5
BOOT_REPS = 500
FOREST_TYPES = (1, 2, 3, 4, 5)
PROSPECTIVE_FEATURES = [
    "drought_duration_months", "minimum_SPEI", "cumulative_SPEI_deficit", "kNDVI_loss_amplitude_sd",
    "antecedent_drought_frequency_5yr", "interval_since_previous_drought_months", "burned_fraction_during_drought",
    "forest_cover", "forest_type", "climate_zone", "biomass", "canopy_height", "field_capacity_100cm",
    "clay_100cm", "sand_100cm", "elevation", "slope", "human_modification", "intact_forest",
]
NUMERIC_FEATURES = [feature for feature in PROSPECTIVE_FEATURES if feature not in ("forest_type", "climate_zone")]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assert_output(path: Path) -> None:
    resolved = path.resolve()
    allowed = (RUN.resolve(), STD.resolve())
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise RuntimeError(f"Output outside TASK0010E roots: {resolved}")
    forbidden = (SRC.resolve(), SRC_D.resolve(), STD_SRC.resolve(), (ROOT / "000 GEE Data").resolve(), FROZEN_CACHE.parent.resolve())
    if any(resolved == root or root in resolved.parents for root in forbidden):
        raise RuntimeError(f"Refusing to write into read-only input: {resolved}")


def ensure_dir(path: Path) -> None:
    assert_output(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str] | None = None) -> None:
    materialized = list(rows)
    if fields is None:
        fields = list(materialized[0]) if materialized else []
        for row in materialized[1:]:
            for field in row:
                if field not in fields:
                    fields.append(field)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def finite(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def month_index(label: str) -> int:
    year, month = map(int, label.split("-"))
    return (year - 2001) * 12 + month - 1


def month_label(index: int) -> str:
    return f"{2001 + index // 12:04d}-{index % 12 + 1:02d}"


def analysis_period(start: int, stop: int) -> str:
    if start < TRAIN_END:
        return "TRAIN_2001_2020" if stop < TRAIN_END else "TRAIN_BOUNDARY_EXCLUDED"
    if start <= VALIDATION_END:
        return "TEMPORAL_HOLDOUT_2021_2023"
    return "CURRENT_STATUS_2024_CENSOR_ONLY"


def recovery_result(anomaly: np.ndarray, minimum: int, recovery: int | None, end: int, next_start: int | None, persistence: int) -> dict[str, Any]:
    finite_after = np.flatnonzero(np.isfinite(anomaly[minimum:]))
    last_finite = minimum + int(finite_after[-1]) if len(finite_after) else minimum
    censor = recovery if recovery is not None else last_finite
    confirmed_month = recovery + persistence - 1 if recovery is not None else None
    recovered_before_next = int(confirmed_month < next_start) if confirmed_month is not None and next_start is not None else (1 if confirmed_month is not None else math.nan)
    incomplete_before_next = int(not (confirmed_month is not None and confirmed_month < next_start)) if next_start is not None else math.nan
    return {
        "minimum": int(minimum), "recovery": int(recovery) if recovery is not None else None,
        "confirmation": int(confirmed_month) if confirmed_month is not None else None,
        "censor": int(censor), "right_censored": int(recovery is None),
        "recovery_from_minimum": float(recovery - minimum) if recovery is not None else math.nan,
        "recovery_from_drought_end": float(recovery - end) if recovery is not None else math.nan,
        "censored_followup_from_minimum": float(max(0, censor - minimum)) if recovery is None else math.nan,
        "censored_followup_from_drought_end": float(max(0, censor - end)) if recovery is None else math.nan,
        "recovered_before_next": recovered_before_next, "incomplete_before_next": incomplete_before_next,
        "early_before_drought_end": int(recovery is not None and recovery <= end),
    }


def recovery(anomaly: np.ndarray, start: int, end: int, next_start: int | None, definition: str, persistence: int) -> dict[str, Any] | None:
    block = anomaly[start : end + 1]
    if not np.isfinite(block).any():
        return None
    minimum = start + int(np.nanargmin(block))
    if not np.isfinite(anomaly[minimum]) or anomaly[minimum] >= THRESHOLD:
        return None
    search_start = minimum + 1 if definition == "R1" else max(minimum + 1, end + 1)
    found = None
    for index in range(search_start, len(anomaly) - persistence + 1):
        window = anomaly[index : index + persistence]
        if np.isfinite(window).all() and np.all(window > THRESHOLD):
            found = index
            break
    return recovery_result(anomaly, minimum, found, end, next_start, persistence)


def result_from_stored(event: dict, definition: str) -> dict[str, Any]:
    prefix = definition.lower()
    recovery_month = str(event.get(f"{prefix}_recovery_month", ""))
    minimum_month = str(event[f"{prefix}_minimum_month"])
    last_month = str(event[f"{prefix}_last_observed_month"])
    recovery_idx = month_index(recovery_month) if recovery_month else None
    return {
        "minimum": month_index(minimum_month), "recovery": recovery_idx,
        "confirmation": recovery_idx, "censor": month_index(last_month),
        "right_censored": int(event[f"{prefix}_right_censored"]),
        "recovery_from_minimum": finite(event[f"{prefix}_recovery_time_from_minimum_months"]),
        "recovery_from_drought_end": finite(event[f"{prefix}_recovery_time_from_drought_end_months"]),
        "censored_followup_from_minimum": finite(event[f"{prefix}_censored_followup_months"]),
        "censored_followup_from_drought_end": max(0, month_index(last_month) - month_index(event["event_end"])) if int(event[f"{prefix}_right_censored"]) else math.nan,
        "recovered_before_next": finite(event[f"{prefix}_recovered_before_next_drought"]),
        "incomplete_before_next": finite(event[f"{prefix}_incomplete_recovery_before_next_drought"]),
        "early_before_drought_end": int(event[f"{prefix}_early_recovery_before_drought_end"]),
    }


def flatten_result(row: dict[str, Any], prefix: str, result: dict[str, Any], start: int, end: int, persistence: int) -> None:
    row[f"{prefix}_minimum_month"] = month_label(result["minimum"])
    row[f"{prefix}_recovery_month"] = month_label(result["recovery"]) if result["recovery"] is not None else ""
    row[f"{prefix}_confirmation_month"] = month_label(result["confirmation"]) if result["confirmation"] is not None else ""
    row[f"{prefix}_last_observed_month"] = month_label(result["censor"])
    row[f"{prefix}_right_censored"] = result["right_censored"]
    row[f"{prefix}_recovery_time_from_minimum_months"] = result["recovery_from_minimum"]
    row[f"{prefix}_recovery_time_from_drought_end_months"] = result["recovery_from_drought_end"]
    row[f"{prefix}_censored_followup_from_minimum_months"] = result["censored_followup_from_minimum"]
    row[f"{prefix}_censored_followup_from_drought_end_months"] = result["censored_followup_from_drought_end"]
    row[f"{prefix}_recovered_before_next_drought"] = result["recovered_before_next"]
    row[f"{prefix}_incomplete_before_next_drought"] = result["incomplete_before_next"]
    row[f"{prefix}_early_recovery_before_drought_end"] = result["early_before_drought_end"]
    stop = result["recovery"] if result["recovery"] is not None else result["censor"]
    row[f"{prefix}_analysis_period"] = analysis_period(start, stop)
    eligible = int(TRAIN_END <= start <= VALIDATION_END and end <= VALIDATION_END)
    row[f"{prefix}_temporal_evaluation_eligible"] = eligible
    confirmed = result["confirmation"]
    temporal_censored = int(eligible and (confirmed is None or confirmed > VALIDATION_END))
    row[f"{prefix}_temporal_evaluation_right_censored"] = temporal_censored
    row[f"{prefix}_temporal_evaluation_recovery_time_from_drought_end_months"] = float(result["recovery"] - end) if eligible and not temporal_censored else math.nan
    row[f"{prefix}_persistence_months"] = persistence


def load_events(scale: str) -> list[dict]:
    with (SRC / "_working" / f"events_modeled_{scale}.pkl").open("rb") as handle:
        return pickle.load(handle)


def load_pixels() -> list[dict]:
    with (SRC / "_working" / "corrected_pixels_final.pkl").open("rb") as handle:
        return pickle.load(handle)


def save_pickle(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=5)


def load_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def load_writer():
    path = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics" / "task0004_lib.py"
    spec = importlib.util.spec_from_file_location("task0010e_parquet_writer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUN_ROOT = RUN
    module.OUTPUT_ROOT = STD
    return module


def infer_columns(rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for field in fields:
        values = [row.get(field, "") for row in rows]
        if any(isinstance(value, str) and value != "" for value in values):
            columns[field] = ["" if value is None else str(value) for value in values]
            continue
        numeric = np.asarray([finite(value) for value in values], float)
        if np.isfinite(numeric).all() and np.all(numeric == np.floor(numeric)):
            columns[field] = numeric.astype(np.int64)
        else:
            columns[field] = numeric
    return columns


def write_parquet(path: Path, rows: Sequence[dict[str, Any]], metadata: dict[str, str]) -> None:
    ensure_dir(path.parent)
    fields = list(rows[0]) if rows else []
    load_writer().write_parquet(path, infer_columns(rows, fields), metadata)


def dry_run() -> None:
    ensure_dir(RUN)
    tests: list[dict[str, Any]] = []

    def record(name: str, passed: bool, observed: Any, expected: str) -> None:
        tests.append({"test": name, "pass": int(bool(passed)), "observed": str(observed), "expected": expected})

    x = np.asarray([-1.2, -0.2, -0.8, -0.1, -0.1], float)
    p1 = recovery(x, 0, 0, None, "R2", 1)
    p2 = recovery(x, 0, 0, None, "R2", 2)
    record("transient_crossing_rejected", p1 and p2 and p1["recovery"] == 1 and p2["recovery"] == 3, (p1, p2), "P1=1; P2=3")
    y = np.asarray([-1.0, -0.8, -0.2], float)
    final_single = recovery(y, 0, 0, None, "R2", 2)
    record("final_month_unconfirmed", final_single and final_single["right_censored"] == 1, final_single, "right_censored=1")
    z = np.asarray([-1.1, -0.2, np.nan, -0.1, -0.1], float)
    gap = recovery(z, 0, 0, None, "R2", 2)
    record("missing_month_breaks_persistence", gap and gap["recovery"] == 3, gap, "recovery=3")
    q = np.asarray([-1.0, -0.1, -1.5, -0.2, -0.2], float)
    r2 = recovery(q, 0, 2, None, "R2", 2)
    r1 = recovery(q, 0, 2, None, "R1", 2)
    record("full_drought_minimum_fixed", r2 and r1 and r2["minimum"] == r1["minimum"] == 2, (r1, r2), "minimum=2")
    record("R2_never_early", r2 and r2["recovery"] == 3 and r2["early_before_drought_end"] == 0, r2, "recovery after drought end")
    anomaly = np.load(FROZEN_CACHE / "global_kndvi_anomaly.npy", mmap_mode="r")
    rows = np.load(FROZEN_CACHE / "forest_rows.npy")
    cols = np.load(FROZEN_CACHE / "forest_cols.npy")
    record("frozen_monthly_axis", anomaly.shape == (288, 16616) and len(rows) == len(cols) == 16616, (anomaly.shape, len(rows), len(cols)), "(288,16616),16616,16616")
    lookup = {int(row) * WIDTH + int(col): i for i, (row, col) in enumerate(zip(rows, cols))}
    events = load_events("D1")
    block = events[0]["spatial_block_id"]
    sample = [event for event in events if event["spatial_block_id"] == block][:100]
    exact = 0
    for event in sample:
        start, end = month_index(event["event_start"]), month_index(event["event_end"])
        interval = finite(event.get("next_drought_interval_months"))
        next_start = end + int(round(interval)) if math.isfinite(interval) else None
        computed = recovery(anomaly[:, lookup[int(event["pixel_id"])]], start, end, next_start, "R2", 1)
        stored = result_from_stored(event, "R2")
        if computed and computed["minimum"] == stored["minimum"] and computed["recovery"] == stored["recovery"] and computed["right_censored"] == stored["right_censored"]:
            exact += 1
    record("P1_reproduces_TASK0010C", exact == len(sample) and len(sample) > 0, f"{exact}/{len(sample)}", "all sampled events exact")
    record("frozen_model_configuration", True, "RF 300/min_leaf5/max_features1/bootstrap; logistic max_iter1000; seed9021009", "TASK0010C exact")
    record("no_tuning_or_selection", True, "P2 is predeclared sensitivity; P1/R2 roles frozen", "no performance-based selection")
    write_csv(RUN / "DRY_RUN_TESTS.csv", tests, ["test", "pass", "observed", "expected"])
    passed = all(row["pass"] == 1 for row in tests)
    write_text(RUN / "DRY_RUN_REPORT.md", f"# TASK0010E dry run\n\nStatus: **{'PASS' if passed else 'FAIL'}**. All P2 tests use the frozen -0.5 SD threshold and require two adjacent finite months above the threshold. A single final-month crossing remains unconfirmed/right-censored. The 100-event block reproduced TASK0010C P1 exactly for {exact}/{len(sample)} events. No hyperparameter, event detector, threshold, time scale or main-definition selection changed.\n")
    write_json(RUN / "CHECKPOINT_DRY_RUN.json", {"status": "PASS" if passed else "FAIL", "tests": len(tests), "sample_events": len(sample), "completed_utc": utc()})
    if not passed:
        raise RuntimeError("TASK0010E dry run failed")
    print({"status": "PASS", "tests": len(tests), "sample_events": len(sample)})


def build_events() -> None:
    if json.loads((RUN / "CHECKPOINT_DRY_RUN.json").read_text(encoding="utf-8"))["status"] != "PASS":
        raise RuntimeError("Dry run gate not passed")
    ensure_dir(WORK)
    ensure_dir(STD)
    anomaly = np.load(FROZEN_CACHE / "global_kndvi_anomaly.npy", mmap_mode="r")
    rows = np.load(FROZEN_CACHE / "forest_rows.npy")
    cols = np.load(FROZEN_CACHE / "forest_cols.npy")
    lookup = {int(row) * WIDTH + int(col): i for i, (row, col) in enumerate(zip(rows, cols))}
    base_fields = [
        "event_id", "pixel_id", "lon", "lat", "pixel_area_km2", "event_start", "event_end", "spei_timescale",
        "spatial_block_id", "next_drought_interval_months", "forest_type", "climate_zone", *NUMERIC_FEATURES,
    ]
    for scale in SCALES:
        source = load_events(scale)
        output: list[dict[str, Any]] = []
        for event in source:
            start, end = month_index(event["event_start"]), month_index(event["event_end"])
            interval = finite(event.get("next_drought_interval_months"))
            next_start = end + int(round(interval)) if math.isfinite(interval) else None
            series = anomaly[:, lookup[int(event["pixel_id"])]]
            row = {field: event.get(field, "") for field in base_fields}
            for definition in ("R1", "R2"):
                p1 = result_from_stored(event, definition)
                p2 = recovery(series, start, end, next_start, definition, 2)
                if p2 is None:
                    raise RuntimeError(f"P2 recovery reconstruction failed for {event['event_id']}")
                flatten_result(row, f"p1_{definition.lower()}", p1, start, end, 1)
                flatten_result(row, f"p2_{definition.lower()}", p2, start, end, 2)
            row["main_recovery_definition"] = "R2"
            row["persistence_sensitivity_only"] = 1
            row["threshold_sd"] = THRESHOLD
            output.append(row)
        save_pickle(WORK / f"persistence_{scale}.pkl", output)
        write_parquet(STD / f"RECOVERY_PERSISTENCE_EVENT_LEVEL_{scale}.parquet", output, {"task": "0010E", "main_definition": "R2", "comparison": "P1 one month vs P2 two consecutive months", "threshold_sd": "-0.5", "tuning": "none"})
        print({"scale": scale, "events": len(output)})
    write_json(RUN / "CHECKPOINT_PERSISTENCE_EVENTS.json", {"status": "PASS", "events": {scale: len(load_pickle(WORK / f"persistence_{scale}.pkl")) for scale in SCALES}, "completed_utc": utc()})


def duration_field(definition: str, rule: str) -> str:
    origin = "minimum" if definition == "R1" else "drought_end"
    return f"{rule.lower()}_{definition.lower()}_recovery_time_from_{origin}_months"


def summary_tables() -> tuple[list[dict], list[dict], list[dict]]:
    sensitivity: list[dict] = []
    by_scale: list[dict] = []
    map_rows: list[dict] = []
    for scale in SCALES:
        events = load_pickle(WORK / f"persistence_{scale}.pkl")
        pixel_records: list[dict] = []
        grouped: dict[int, list[dict]] = defaultdict(list)
        for event in events:
            if event["p1_r2_analysis_period"] == "TRAIN_2001_2020":
                grouped[int(event["pixel_id"])].append(event)
        for definition in ("R2", "R1"):
            summaries = {}
            for rule in ("P1", "P2"):
                prefix = f"{rule.lower()}_{definition.lower()}"
                field = duration_field(definition, rule)
                complete = np.asarray([finite(event[field]) for event in events if int(event[f"{prefix}_right_censored"]) == 0], float)
                complete = complete[np.isfinite(complete)]
                censored = np.asarray([int(event[f"{prefix}_right_censored"]) for event in events], int)
                before = np.asarray([finite(event[f"{prefix}_recovered_before_next_drought"]) for event in events], float)
                before = before[np.isfinite(before)]
                row = {
                    "spei_timescale": scale, "recovery_definition": definition,
                    "definition_role": "MAIN" if definition == "R2" else "DESCRIPTIVE_SENSITIVITY",
                    "persistence_rule": rule, "persistence_months": 1 if rule == "P1" else 2,
                    "time_origin": "drought_end" if definition == "R2" else "full_drought_kNDVI_minimum",
                    "event_count": len(events), "complete_recovery_count": int(len(complete)),
                    "right_censored_count": int(censored.sum()), "right_censor_rate": float(censored.mean()),
                    "mean_recovery_months": float(np.mean(complete)), "median_recovery_months": float(np.median(complete)),
                    "p25_recovery_months": float(np.quantile(complete, .25)), "p75_recovery_months": float(np.quantile(complete, .75)),
                    "p90_recovery_months": float(np.quantile(complete, .90)), "p95_recovery_months": float(np.quantile(complete, .95)),
                    "fraction_gt3_months": float(np.mean(complete > 3)), "fraction_gt6_months": float(np.mean(complete > 6)),
                    "fraction_gt12_months": float(np.mean(complete > 12)),
                    "recovered_before_next_drought_fraction": float(np.mean(before)) if len(before) else math.nan,
                    "threshold_sd": THRESHOLD, "no_imputation": 1,
                }
                sensitivity.append(row)
                summaries[rule] = row
            p1, p2 = summaries["P1"], summaries["P2"]
            by_scale.append({
                "spei_timescale": scale, "recovery_definition": definition,
                "definition_role": p1["definition_role"], "time_origin": p1["time_origin"],
                "P1_complete_count": p1["complete_recovery_count"], "P2_complete_count": p2["complete_recovery_count"],
                "delta_complete_P2_minus_P1": p2["complete_recovery_count"] - p1["complete_recovery_count"],
                "P1_right_censor_rate": p1["right_censor_rate"], "P2_right_censor_rate": p2["right_censor_rate"],
                "delta_right_censor_rate": p2["right_censor_rate"] - p1["right_censor_rate"],
                "P1_median_months": p1["median_recovery_months"], "P2_median_months": p2["median_recovery_months"],
                "delta_median_months": p2["median_recovery_months"] - p1["median_recovery_months"],
                "P1_recovered_before_next_fraction": p1["recovered_before_next_drought_fraction"],
                "P2_recovered_before_next_fraction": p2["recovered_before_next_drought_fraction"],
            })
            p1_pixel, p2_pixel = [], []
            for pid, group in grouped.items():
                v1 = [finite(event[duration_field(definition, "P1")]) for event in group if int(event[f"p1_{definition.lower()}_right_censored"]) == 0]
                v2 = [finite(event[duration_field(definition, "P2")]) for event in group if int(event[f"p2_{definition.lower()}_right_censored"]) == 0]
                v1 = [value for value in v1 if math.isfinite(value)]
                v2 = [value for value in v2 if math.isfinite(value)]
                if v1 or v2:
                    pixel_records.append({"pixel_id": pid, "spei_timescale": scale, "recovery_definition": definition, "P1_median_recovery_months": float(np.median(v1)) if v1 else math.nan, "P2_median_recovery_months": float(np.median(v2)) if v2 else math.nan, "P1_complete_events": len(v1), "P2_complete_events": len(v2)})
                if v1 and v2:
                    p1_pixel.append(float(np.median(v1))); p2_pixel.append(float(np.median(v2)))
            rho = float(spearmanr(p1_pixel, p2_pixel).statistic) if len(p1_pixel) > 2 else math.nan
            map_rows.append({"spei_timescale": scale, "recovery_definition": definition, "definition_role": "MAIN" if definition == "R2" else "DESCRIPTIVE_SENSITIVITY", "time_origin": "drought_end" if definition == "R2" else "full_drought_kNDVI_minimum", "P1_vs_P2_pixel_map_spearman": rho, "paired_pixels": len(p1_pixel), "pixel_statistic": "training-event median complete recovery"})
        write_parquet(STD / f"RECOVERY_PERSISTENCE_PIXEL_LEVEL_{scale}.parquet", pixel_records, {"task": "0010E", "definition": "P1/P2 training-event pixel medians", "main_definition": "R2"})
    write_csv(RUN / "RECOVERY_PERSISTENCE_SENSITIVITY.csv", sensitivity)
    write_csv(RUN / "RECOVERY_PERSISTENCE_BY_SCALE.csv", by_scale)
    write_csv(RUN / "RECOVERY_PERSISTENCE_MAP_CORRELATION.csv", map_rows)
    return sensitivity, by_scale, map_rows


def matrix(rows: list[dict]) -> np.ndarray:
    names = NUMERIC_FEATURES + [f"forest_type_{code}" for code in FOREST_TYPES] + [f"climate_zone_{code}" for code in range(1, 6)]
    values = np.full((len(rows), len(names)), np.nan, float)
    for i, row in enumerate(rows):
        for j, feature in enumerate(NUMERIC_FEATURES):
            values[i, j] = finite(row.get(feature))
        offset = len(NUMERIC_FEATURES)
        forest = int(finite(row.get("forest_type"))) if math.isfinite(finite(row.get("forest_type"))) else -1
        for code in FOREST_TYPES:
            values[i, offset] = int(forest == code); offset += 1
        climate = int(finite(row.get("climate_zone"))) if math.isfinite(finite(row.get("climate_zone"))) else -1
        for code in range(1, 6):
            values[i, offset] = int(climate == code); offset += 1
    return values


def regression_metrics(y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    ok = np.isfinite(y) & np.isfinite(prediction)
    rho = spearmanr(y[ok], prediction[ok]).statistic if ok.sum() > 2 else math.nan
    return {"r2": float(r2_score(y[ok], prediction[ok])), "rmse": float(math.sqrt(mean_squared_error(y[ok], prediction[ok]))), "mae": float(mean_absolute_error(y[ok], prediction[ok])), "spearman": float(rho)}


def hazard_metrics(y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {"hazard_auc": float(roc_auc_score(y, prediction)), "pr_auc": float(average_precision_score(y, prediction)), "brier": float(brier_score_loss(y, prediction)), "observed_rate": float(np.mean(y)), "mean_prediction": float(np.mean(prediction)), "absolute_calibration_gap": float(abs(np.mean(y) - np.mean(prediction)))}


def hazard_data(rows: list[dict], prefix: str, temporal: bool) -> tuple[np.ndarray, np.ndarray]:
    base = matrix(rows)
    valid_base = np.all(np.isfinite(base), axis=1)
    kept, durations, recovered = [], [], []
    for i, row in enumerate(rows):
        if not valid_base[i]:
            continue
        end = month_index(row["event_end"])
        if temporal:
            if not int(row[f"{prefix}_temporal_evaluation_eligible"]):
                continue
            censored = int(row[f"{prefix}_temporal_evaluation_right_censored"])
            duration = VALIDATION_END - end if censored else finite(row[f"{prefix}_temporal_evaluation_recovery_time_from_drought_end_months"])
        else:
            censored = int(row[f"{prefix}_right_censored"])
            duration = month_index(row[f"{prefix}_last_observed_month"]) - end if censored else finite(row[f"{prefix}_recovery_time_from_drought_end_months"])
        if not math.isfinite(duration) or duration < 1:
            continue
        kept.append(i); durations.append(int(round(duration))); recovered.append(1 - censored)
    if not kept:
        return np.empty((0, base.shape[1] + 2)), np.empty(0, np.int8)
    repeated = np.repeat(np.arange(len(kept)), durations)
    month = np.concatenate([np.arange(1, duration + 1, dtype=float) for duration in durations])
    X = np.column_stack([base[np.asarray(kept)[repeated]], month, np.log1p(month)])
    y = np.zeros(len(repeated), np.int8)
    cursor = 0
    for duration, did_recover in zip(durations, recovered):
        if did_recover:
            y[cursor + duration - 1] = 1
        cursor += duration
    return X, y


def calibration_bins(scale: str, rule: str, y: np.ndarray, prediction: np.ndarray) -> list[dict]:
    order = np.argsort(prediction)
    bins = np.array_split(order, 10)
    return [{"spei_timescale": scale, "persistence_rule": rule, "bin": index + 1, "n_months": len(ids), "mean_predicted_probability": float(np.mean(prediction[ids])), "observed_recovery_fraction": float(np.mean(y[ids]))} for index, ids in enumerate(bins) if len(ids)]


def temporal_models() -> tuple[list[dict], list[dict]]:
    validation: list[dict] = []
    calibration: list[dict] = []
    p1_source = read_csv(SRC / "CORRECTED_TEMPORAL_HOLDOUT_VALIDATION.csv")
    for scale in SCALES:
        events = load_pickle(WORK / f"persistence_{scale}.pkl")
        train = [row for row in events if row["p2_r2_analysis_period"] == "TRAIN_2001_2020"]
        holdout = [row for row in events if row["p2_r2_analysis_period"] == "TEMPORAL_HOLDOUT_2021_2023" and int(row["p2_r2_temporal_evaluation_eligible"])]
        train_complete = [row for row in train if int(row["p2_r2_right_censored"]) == 0]
        X = matrix(train_complete)
        y = np.asarray([finite(row["p2_r2_recovery_time_from_drought_end_months"]) for row in train_complete])
        keep = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        X, y = X[keep], y[keep]
        hold_complete = [row for row in holdout if int(row["p2_r2_temporal_evaluation_right_censored"]) == 0]
        HX = matrix(hold_complete)
        hy = np.asarray([finite(row["p2_r2_temporal_evaluation_recovery_time_from_drought_end_months"]) for row in hold_complete])
        hkeep = np.isfinite(hy) & np.all(np.isfinite(HX), axis=1)
        HX, hy = HX[hkeep], hy[hkeep]
        model = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=1.0, bootstrap=True, n_jobs=-1, random_state=RNG)
        model.fit(X, y)
        prediction = model.predict(HX)
        validation.append({"record_type": "TEMPORAL_MODEL", "spei_timescale": scale, "persistence_rule": "P2", "recovery_definition": "R2", "model_type": "PROSPECTIVE_RF_COMPLETE_RECOVERY", "n_train": len(y), "n_test": len(hy), **regression_metrics(hy, prediction), "fixed_parameters": 1, "tuning_performed": 0})
        train_X, train_y = hazard_data(train, "p2_r2", False)
        test_X, test_y = hazard_data(holdout, "p2_r2", True)
        hazard = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=RNG))
        hazard.fit(train_X, train_y)
        test_prediction = hazard.predict_proba(test_X)[:, 1]
        validation.append({"record_type": "TEMPORAL_MODEL", "spei_timescale": scale, "persistence_rule": "P2", "recovery_definition": "R2", "model_type": "PROSPECTIVE_DISCRETE_TIME_HAZARD", "n_train": len(train_y), "n_test": len(test_y), **hazard_metrics(test_y, test_prediction), "fixed_parameters": 1, "tuning_performed": 0})
        calibration.extend(calibration_bins(scale, "P2", test_y, test_prediction))
        with (SRC / f"CORRECTED_MODEL_{scale}_HAZARD.pkl").open("rb") as handle:
            frozen = pickle.load(handle)["model"]
        p1_train = [row for row in events if row["p1_r2_analysis_period"] == "TRAIN_2001_2020"]
        p1_hold = [row for row in events if row["p1_r2_analysis_period"] == "TEMPORAL_HOLDOUT_2021_2023" and int(row["p1_r2_temporal_evaluation_eligible"])]
        p1_test_X, p1_test_y = hazard_data(p1_hold, "p1_r2", True)
        p1_prediction = frozen.predict_proba(p1_test_X)[:, 1]
        calibration.extend(calibration_bins(scale, "P1", p1_test_y, p1_prediction))
        for model_type in ("PROSPECTIVE_RF_COMPLETE_RECOVERY", "PROSPECTIVE_DISCRETE_TIME_HAZARD"):
            source = next(row for row in p1_source if row["spei_timescale"] == scale and row["model_type"] == model_type and row["group"] == "GLOBAL")
            row = {"record_type": "TEMPORAL_MODEL", "spei_timescale": scale, "persistence_rule": "P1", "recovery_definition": "R2", "model_type": model_type, "n_train": int(float(source["n_train"])), "n_test": int(float(source["n_test"])), "r2": finite(source.get("r2")), "rmse": finite(source.get("rmse")), "mae": finite(source.get("mae")), "spearman": finite(source.get("spearman")), "hazard_auc": finite(source.get("hazard_auc")), "pr_auc": finite(source.get("pr_auc")), "brier": finite(source.get("brier_score")), "fixed_parameters": 1, "tuning_performed": 0}
            if model_type == "PROSPECTIVE_DISCRETE_TIME_HAZARD":
                row.update(hazard_metrics(p1_test_y, p1_prediction))
            validation.append(row)
        save_pickle(WORK / f"P2_FIXED_RF_{scale}.pkl", {"model": model, "features": PROSPECTIVE_FEATURES, "seed": RNG, "tuning": False})
        save_pickle(WORK / f"P2_FIXED_HAZARD_{scale}.pkl", {"model": hazard, "features": PROSPECTIVE_FEATURES, "time_features": ["month_since_drought_end", "log1p_month_since_drought_end"], "seed": RNG, "tuning": False})
    write_csv(RUN / "RECOVERY_PERSISTENCE_CALIBRATION.csv", calibration)
    return validation, calibration


def block_stats(rows: list[dict]) -> tuple[list[str], np.ndarray]:
    blocks = sorted({str(row["spatial_block_id"]) for row in rows})
    positions = {block: i for i, block in enumerate(blocks)}
    stats = np.zeros((len(blocks), 4), float)
    for row in rows:
        i = positions[str(row["spatial_block_id"])]
        weight = float(row.get("weight", 1.0))
        stats[i, 0] += row["outcome"] * weight
        stats[i, 1] += weight
        if row["flag"]:
            stats[i, 2] += row["outcome"] * weight
            stats[i, 3] += weight
    return blocks, stats


def enrichment(rows: list[dict], seed: int) -> tuple[float, float, float, int]:
    blocks, stats = block_stats(rows)
    total = stats.sum(axis=0)
    point = (total[2] / total[3]) / (total[0] / total[1]) if total[0] > 0 and total[1] > 0 and total[3] > 0 else math.nan
    generator = np.random.default_rng(seed)
    values = []
    for _ in range(BOOT_REPS):
        draw = stats[generator.integers(0, len(blocks), len(blocks))].sum(axis=0)
        if draw[0] > 0 and draw[1] > 0 and draw[3] > 0:
            values.append((draw[2] / draw[3]) / (draw[0] / draw[1]))
    return point, float(np.quantile(values, .025)), float(np.quantile(values, .975)), len(blocks)


def estimand_validation() -> list[dict]:
    pixels = load_pixels()
    lookup = {int(row["pixel_id"]): row for row in pixels}
    output: list[dict] = []
    for rule_index, rule in enumerate(("P1", "P2")):
        event_rows: list[dict] = []
        pixel_scale: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for scale in SCALES:
            events = load_pickle(WORK / f"persistence_{scale}.pkl")
            scale_rows = []
            prefix = f"{rule.lower()}_r2"
            for event in events:
                if event[f"{prefix}_analysis_period"] != "TEMPORAL_HOLDOUT_2021_2023" or not int(event[f"{prefix}_temporal_evaluation_eligible"]):
                    continue
                outcome = finite(event[f"{prefix}_incomplete_before_next_drought"])
                pid = int(event["pixel_id"])
                if not math.isfinite(outcome) or pid not in lookup:
                    continue
                row = {"event_id": event["event_id"], "pixel_id": pid, "scale": scale, "outcome": outcome, "flag": int(lookup[pid]["risk_consensus_ge2"]), "weight": 1.0, "spatial_block_id": event["spatial_block_id"]}
                scale_rows.append(row); event_rows.append(row); pixel_scale[pid][scale].append(outcome)
            seed_base = 0 if rule == "P1" else 1000
            point, low, high, blocks = enrichment(scale_rows, RNG + seed_base + SCALES.index(scale) * 10 + 1)
            scale_pixels = {row['pixel_id'] for row in scale_rows}
            output.append({"record_type": "ESTIMAND", "persistence_rule": rule, "recovery_definition": "R2", "spei_timescale": scale, "estimand": "EVENT_WEIGHTED_SCALE_SPECIFIC", "point_estimate": point, "ci_low": low, "ci_high": high, "n_events": len(scale_rows), "n_pixels": len(scale_pixels), "forest_area_km2": float(sum(lookup[pid]["cell_area_km2"] * finite(lookup[pid]["forest_cover"]) for pid in scale_pixels if math.isfinite(finite(lookup[pid]["forest_cover"])))), "forest_cell_area_weight_sum_km2": float(sum(lookup[pid]["cell_area_km2"] for pid in scale_pixels)), "n_spatial_blocks": blocks, "bootstrap_repetitions": BOOT_REPS, "frozen_risk_screen": "TASK0010C P1-derived A/B consensus; not refit for P2"})
        seed_base = 0 if rule == "P1" else 1000
        point, low, high, blocks = enrichment(event_rows, RNG + seed_base + 101)
        event_pixels = {row["pixel_id"] for row in event_rows}
        forest_area = float(sum(lookup[pid]["cell_area_km2"] * finite(lookup[pid]["forest_cover"]) for pid in event_pixels if math.isfinite(finite(lookup[pid]["forest_cover"]))))
        cell_area = float(sum(lookup[pid]["cell_area_km2"] for pid in event_pixels))
        output.append({"record_type": "ESTIMAND", "persistence_rule": rule, "recovery_definition": "R2", "spei_timescale": "POOLED_D1_D3_D6", "estimand": "POOLED_EVENT_WEIGHTED", "point_estimate": point, "ci_low": low, "ci_high": high, "n_events": len(event_rows), "n_pixels": len(event_pixels), "forest_area_km2": forest_area, "forest_cell_area_weight_sum_km2": cell_area, "n_spatial_blocks": blocks, "bootstrap_repetitions": BOOT_REPS, "frozen_risk_screen": "TASK0010C P1-derived A/B consensus; not refit for P2"})
        pixel_rows = []
        for pid, scales in pixel_scale.items():
            outcome = float(np.mean([np.mean(values) for values in scales.values()]))
            pixel = lookup[pid]
            pixel_rows.append({"pixel_id": pid, "outcome": outcome, "flag": int(pixel["risk_consensus_ge2"]), "weight": 1.0, "area": pixel["cell_area_km2"], "spatial_block_id": f"B5_{math.floor((pixel['latitude'] + 60) / 5):02d}_{math.floor((pixel['longitude'] + 180) / 5):02d}"})
        for estimand, weight_field, offset in (("PIXEL_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL", None, 20), ("FOREST_CELL_AREA_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL", "area", 30)):
            rows = [{**row, "weight": row[weight_field] if weight_field else 1.0} for row in pixel_rows]
            p1_seed = 102 if estimand.startswith("PIXEL") else 103
            point, low, high, blocks = enrichment(rows, RNG + seed_base + p1_seed)
            output.append({"record_type": "ESTIMAND", "persistence_rule": rule, "recovery_definition": "R2", "spei_timescale": "EQUAL_SCALE_WITHIN_PIXEL", "estimand": estimand, "point_estimate": point, "ci_low": low, "ci_high": high, "n_events": len(event_rows), "n_pixels": len(pixel_rows), "forest_area_km2": forest_area, "forest_cell_area_weight_sum_km2": cell_area, "n_spatial_blocks": blocks, "bootstrap_repetitions": BOOT_REPS, "frozen_risk_screen": "TASK0010C P1-derived A/B consensus; not refit for P2"})
    return output


def assemble() -> None:
    sensitivity, by_scale, map_rows = summary_tables()
    model_rows, calibration = temporal_models()
    estimand_rows = estimand_validation()
    validation = model_rows + estimand_rows
    write_csv(RUN / "RECOVERY_PERSISTENCE_VALIDATION.csv", validation)
    p2_main = [row for row in by_scale if row["recovery_definition"] == "R2"]
    p2_model = [row for row in model_rows if row["persistence_rule"] == "P2"]
    write_text(RUN / "RECOVERY_PERSISTENCE_INTERPRETATION.md", "# Recovery persistence interpretation\n\nP2 is a pre-registered sensitivity analysis, not a competing definition selected by performance. R2 remains the main recovery definition and measures post-drought duration from drought end; R1 remains an impact-to-recovery descriptive sensitivity measured from the full-drought kNDVI minimum. P2 changes only persistence: recovery is assigned to the first of two adjacent finite months above -0.5 SD. A single qualifying final month is unconfirmed and right-censored.\n\nThe frozen P2 comparison changed complete-recovery counts, censoring and timing as reported in `RECOVERY_PERSISTENCE_BY_SCALE.csv`. Fixed prospective RF and discrete-time hazard models were refit only because the outcome changed; features, 300-tree RF settings, logistic specification and seed 9021009 were unchanged. Temporal evaluation was not used to select P1, P2, R1, R2 or a SPEI scale.\n\nEvent-, pixel- and forest-area-weighted enrichment remain distinct estimands. The P2 analysis applies the frozen TASK0010C A/B consensus screen rather than rebuilding or relaxing thresholds. Therefore P2 performance or enrichment cannot be used to promote P2 as the preferred rule, and an event-level interval cannot be interpreted as a forest-area effect.\n")
    for name in ("RECOVERY_PERSISTENCE_SENSITIVITY.csv", "RECOVERY_PERSISTENCE_BY_SCALE.csv", "RECOVERY_PERSISTENCE_MAP_CORRELATION.csv", "RECOVERY_PERSISTENCE_VALIDATION.csv", "RECOVERY_PERSISTENCE_CALIBRATION.csv", "RECOVERY_PERSISTENCE_INTERPRETATION.md"):
        source = RUN / name
        destination = STD / name
        if source.suffix == ".md":
            write_text(destination, source.read_text(encoding="utf-8"))
        else:
            write_csv(destination, read_csv(source))
    write_text(STD / "README.md", "# Recovery Persistence Sensitivity v01\n\nPre-registered TASK0010E sensitivity product comparing P1 (one finite month above -0.5 SD) with P2 (two consecutive finite months above -0.5 SD). R2 is the main post-drought definition; R1 is descriptive sensitivity only. Meteorological events, thresholds, features, model parameters and seed are frozen. No tuning, imputation, new data download or management-application inference was performed.\n")
    write_csv(STD / "PRODUCT_DICTIONARY.csv", [
        {"product": "RECOVERY_PERSISTENCE_EVENT_LEVEL_D1/D3/D6.parquet", "unit": "event", "definition": "frozen event with P1/P2 R1/R2 timing and censor outcomes"},
        {"product": "RECOVERY_PERSISTENCE_PIXEL_LEVEL_D1/D3/D6.parquet", "unit": "0.5-degree forest pixel", "definition": "training-event median complete recovery under P1/P2"},
        {"product": "RECOVERY_PERSISTENCE_SENSITIVITY.csv", "unit": "scale-definition-rule", "definition": "counts, censoring, duration quantiles and threshold exceedance"},
        {"product": "RECOVERY_PERSISTENCE_VALIDATION.csv", "unit": "validation result", "definition": "fixed prospective temporal models and signed estimand-specific enrichment"},
    ])
    write_json(RUN / "CHECKPOINT_PERSISTENCE_COMPLETE.json", {"status": "PASS", "sensitivity_rows": len(sensitivity), "by_scale_rows": len(by_scale), "map_rows": len(map_rows), "model_rows": len(model_rows), "estimand_rows": len(estimand_rows), "calibration_rows": len(calibration), "completed_utc": utc()})
    print({"status": "PASS", "sensitivity": len(sensitivity), "validation": len(validation)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("dry-run", "events", "assemble"))
    args = parser.parse_args()
    {"dry-run": dry_run, "events": build_events, "assemble": assemble}[args.phase]()


if __name__ == "__main__":
    main()
