from __future__ import annotations

import csv
import importlib.util
import json
import math
import pickle
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Iterable, Sequence

import numpy as np


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
SRC = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010A_Global_Drought_Recovery_Consensus"
SRC_STD = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Consensus_v01"
RUN = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010C_Recovery_Logic_and_Application_Fix"
OUT = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Corrected_v02"
CACHE = SRC / "_processing_cache"
WORK = RUN / "_working"
MAPS = RUN / "CORRECTED_MAP_RASTERS"
OUT_MAPS = OUT / "CORRECTED_MAP_RASTERS"

RNG = 9021009
WIDTH = 720
TRAIN_END = 240
VALIDATION_END = 275
TOTAL_MONTHS = 288
SCALES = ("D1", "D3", "D6")
FOREST_TYPES = (1, 2, 3, 4, 5)
FOREST_LABELS = {
    1: "Evergreen needleleaf forest",
    2: "Evergreen broadleaf forest",
    3: "Deciduous needleleaf forest",
    4: "Deciduous broadleaf forest",
    5: "Mixed forest",
}
CLIMATE_LABELS = {1: "Tropical", 2: "Arid", 3: "Temperate", 4: "Boreal", 5: "Polar"}
CONS_LABEL = {3: "3/3 Robust Core", 2: "2/3 Consensus only", 1: "1/3 Scale-specific", 0: "0/3 None"}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assert_output(path: Path) -> None:
    resolved = path.resolve()
    forbidden = [SRC.resolve(), SRC_STD.resolve(), (ROOT / "000 GEE Data").resolve()]
    if any(resolved == item or item in resolved.parents for item in forbidden):
        raise RuntimeError(f"Refusing to write into read-only source: {resolved}")
    allowed = [RUN.resolve(), OUT.resolve()]
    if not any(resolved == item or item in resolved.parents for item in allowed):
        raise RuntimeError(f"Output outside TASK0010C roots: {resolved}")


def ensure_dir(path: Path) -> None:
    assert_output(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    assert_output(path)
    ensure_dir(path.parent)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str] | None = None) -> None:
    assert_output(path)
    ensure_dir(path.parent)
    materialized = list(rows)
    if fields is None:
        fields = sorted(set().union(*(row.keys() for row in materialized))) if materialized else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def log(message: str) -> None:
    path = RUN / "COMMAND_LOG.txt"
    assert_output(path)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{utc()}] {message}\n")


def finite(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        return math.nan
    return number if math.isfinite(number) else math.nan


def month_index(label: str) -> int:
    year, month = map(int, label.split("-"))
    return (year - 2001) * 12 + month - 1


def month_label(index: int) -> str:
    return f"{2001 + index // 12:04d}-{index % 12 + 1:02d}"


def area_km2(latitude: float) -> float:
    radius = 6371.0088
    return float(radius**2 * math.radians(0.5) * (math.sin(math.radians(latitude + 0.25)) - math.sin(math.radians(latitude - 0.25))))


def region_label(latitude: float, longitude: float) -> str:
    if -170 <= longitude < -30 and latitude >= 7:
        return "North America"
    if -85 <= longitude < -30 and latitude < 15:
        return "South America"
    if -25 <= longitude < 60 and latitude >= 35:
        return "Europe"
    if -20 <= longitude < 55 and latitude < 35:
        return "Africa"
    if 55 <= longitude < 180 and latitude >= 0:
        return "Asia"
    if 110 <= longitude < 180 and latitude < 0:
        return "Oceania"
    return "Other"


def current_recovery(anomaly: np.ndarray, start: int, end: int, next_start: int | None) -> dict[str, Any] | None:
    negative = np.flatnonzero(np.isfinite(anomaly[start : end + 1]) & (anomaly[start : end + 1] < -0.5))
    if not len(negative):
        return None
    negative_start = start + int(negative[0])
    first = next((index for index in range(negative_start + 1, len(anomaly)) if np.isfinite(anomaly[index]) and anomaly[index] > -0.5), None)
    search_end = first if first is not None else len(anomaly) - 1
    block = anomaly[negative_start : search_end + 1]
    if not np.isfinite(block).any():
        return None
    minimum = negative_start + int(np.nanargmin(block))
    if first is None or first <= minimum:
        first = next((index for index in range(minimum + 1, len(anomaly)) if np.isfinite(anomaly[index]) and anomaly[index] > -0.5), None)
    return recovery_result(anomaly, minimum, first, end, next_start)


def recovery_result(anomaly: np.ndarray, minimum: int, recovery: int | None, end: int, next_start: int | None) -> dict[str, Any]:
    finite_after = np.flatnonzero(np.isfinite(anomaly[minimum:]))
    last_finite = minimum + int(finite_after[-1]) if len(finite_after) else minimum
    censor = recovery if recovery is not None else last_finite
    next_interval = float(next_start - end) if next_start is not None else math.nan
    recovered_before_next = int(recovery is not None and recovery < next_start) if next_start is not None else (1 if recovery is not None else math.nan)
    incomplete_before_next = int(not (recovery is not None and recovery < next_start)) if next_start is not None else math.nan
    return {
        "minimum": int(minimum),
        "recovery": int(recovery) if recovery is not None else None,
        "censor": int(censor),
        "right_censored": int(recovery is None),
        "recovery_from_minimum": float(recovery - minimum) if recovery is not None else math.nan,
        "recovery_from_drought_end": float(recovery - end) if recovery is not None else math.nan,
        "censored_followup": float(max(0, censor - minimum)) if recovery is None else math.nan,
        "recovered_before_next": recovered_before_next,
        "incomplete_before_next": incomplete_before_next,
        "next_interval": next_interval,
        "early_before_drought_end": int(recovery is not None and recovery <= end),
        "missing_uncertainty": int((~np.isfinite(anomaly[minimum : censor + 1])).any()),
    }


def corrected_recovery(anomaly: np.ndarray, start: int, end: int, next_start: int | None, definition: str) -> dict[str, Any] | None:
    block = anomaly[start : end + 1]
    if not np.isfinite(block).any():
        return None
    minimum = start + int(np.nanargmin(block))
    if not np.isfinite(anomaly[minimum]) or anomaly[minimum] >= -0.5:
        return None
    if definition == "R1":
        search_start = minimum + 1
    elif definition == "R2":
        search_start = max(minimum + 1, end + 1)
    else:
        raise ValueError(definition)
    recovery = next((index for index in range(search_start, len(anomaly)) if np.isfinite(anomaly[index]) and anomaly[index] > -0.5), None)
    return recovery_result(anomaly, minimum, recovery, end, next_start)


def analysis_period(start: int, stop: int) -> str:
    if start < TRAIN_END:
        return "TRAIN_2001_2020" if stop < TRAIN_END else "TRAIN_BOUNDARY_EXCLUDED"
    if start <= VALIDATION_END:
        return "TEMPORAL_HOLDOUT_2021_2023"
    return "CURRENT_STATUS_2024_CENSOR_ONLY"


def update_event_with_definition(event: dict[str, Any], result: dict[str, Any], prefix: str) -> None:
    event[f"{prefix}_minimum_month"] = month_label(result["minimum"])
    event[f"{prefix}_recovery_month"] = month_label(result["recovery"]) if result["recovery"] is not None else ""
    event[f"{prefix}_last_observed_month"] = month_label(result["censor"])
    event[f"{prefix}_right_censored"] = result["right_censored"]
    event[f"{prefix}_recovery_time_from_minimum_months"] = result["recovery_from_minimum"]
    event[f"{prefix}_recovery_time_from_drought_end_months"] = result["recovery_from_drought_end"]
    event[f"{prefix}_censored_followup_months"] = result["censored_followup"]
    event[f"{prefix}_recovered_before_next_drought"] = result["recovered_before_next"]
    event[f"{prefix}_incomplete_recovery_before_next_drought"] = result["incomplete_before_next"]
    event[f"{prefix}_early_recovery_before_drought_end"] = result["early_before_drought_end"]
    stop = result["recovery"] if result["recovery"] is not None else result["censor"]
    event[f"{prefix}_analysis_period"] = analysis_period(month_index(event["event_start"]), stop)


def infer_columns(rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    columns: dict[str, Any] = {}
    for field in fields:
        values = [row.get(field, "") for row in rows]
        numeric: list[float] = []
        failed = False
        missing = False
        for item in values:
            if item is None or item == "":
                numeric.append(math.nan)
                missing = True
                continue
            if isinstance(item, str):
                failed = True
                break
            try:
                numeric.append(float(item))
            except Exception:
                failed = True
                break
        if failed:
            columns[field] = ["" if item is None else str(item) for item in values]
        elif not missing and all(math.isfinite(item) and item.is_integer() for item in numeric):
            columns[field] = np.asarray(numeric, dtype=np.int64)
        else:
            columns[field] = np.asarray(numeric, dtype=np.float64)
    return columns


def write_parquet(path: Path, rows: Sequence[dict[str, Any]], metadata: dict[str, str]) -> None:
    assert_output(path)
    library_path = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics" / "task0004_lib.py"
    spec = importlib.util.spec_from_file_location("task0004_lib_for_0010c", library_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen Parquet writer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUN_ROOT = RUN
    module.OUTPUT_ROOT = OUT
    fields = list(rows[0]) if rows else []
    module.write_parquet(path, infer_columns(rows, fields), metadata)


def save_pickle(path: Path, value: Any) -> None:
    assert_output(path)
    ensure_dir(path.parent)
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=5)


def load_pickle(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def base_pixel_rows() -> list[dict[str, Any]]:
    source = read_csv(SRC / "GLOBAL_PIXEL_MULTISCALE_PRIORITY.csv")
    rows: list[dict[str, Any]] = []
    for item in source:
        rows.append(
            {
                "pixel_id": int(item["pixel_id"]),
                "grid_row": int(item["grid_row"]),
                "grid_col": int(item["grid_col"]),
                "latitude": float(item["latitude"]),
                "longitude": float(item["longitude"]),
                "cell_area_km2": float(item["cell_area_km2"]),
                "forest_cover": finite(item["forest_cover"]),
                "forest_type": int(float(item["forest_type"])),
                "forest_type_label": FOREST_LABELS.get(int(float(item["forest_type"])), "Other forest"),
                "biome_label_removed": "not_independent_of_forest_type",
                "biomass": finite(item["biomass"]),
                "human_modification": finite(item["human_modification"]),
                "intact_forest": finite(item["intact_forest"]),
                "climate_zone": int(float(item["climate_zone"])),
                "climate_zone_label": CLIMATE_LABELS.get(int(float(item["climate_zone"])), "Unknown"),
                "large_region": region_label(float(item["latitude"]), float(item["longitude"])),
            }
        )
    return rows


def bootstrap_blocks(rows: Sequence[dict[str, Any]], estimator, reps: int, seed: int) -> tuple[float, float, float, int]:
    if not rows:
        return math.nan, math.nan, math.nan, 0
    point = estimator(rows)
    blocks = sorted({str(row["spatial_block_id"]) for row in rows})
    by_block = {block: [row for row in rows if str(row["spatial_block_id"]) == block] for block in blocks}
    generator = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(reps):
        draw = [row for block in generator.choice(blocks, len(blocks), replace=True) for row in by_block[str(block)]]
        estimate = estimator(draw)
        if math.isfinite(estimate):
            values.append(float(estimate))
    return (
        float(point) if math.isfinite(point) else math.nan,
        float(np.quantile(values, 0.025)) if values else math.nan,
        float(np.quantile(values, 0.975)) if values else math.nan,
        len(rows),
    )


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))
