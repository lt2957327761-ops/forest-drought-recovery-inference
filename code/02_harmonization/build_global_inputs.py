from __future__ import annotations

import calendar
import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import re
import struct
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW = ROOT / "000 GEE Data"
WORKBENCH = ROOT / "010_Research_Workbench"
RUN = WORKBENCH / "02_Runs" / "RUN_0008B_FAST_PAPER_Global_Production"
DERIVED = (
    WORKBENCH
    / "04_Standardized_Data"
    / "FastPaper_Greening_Resilience_Global_v01"
)
WORK = RUN / "_processing_cache"
GLOBAL = (-180.0, -60.0, 180.0, 85.0)
HEIGHT, WIDTH = 290, 720
YEARS = list(range(2001, 2021))
MONTHS = [f"{year:04d}-{month:02d}" for year in YEARS for month in range(1, 13)]
DATA_PREFIX = {
    "Data01": "1 ",
    "Data03": "3 ",
    "Data04": "4 ",
    "Data07": "7 ",
    "Data09": "9 ",
    "Data10": "10 ",
    "Data11": "11 ",
    "Data12": "12 ",
    "Data13": "13 ",
    "Data14": "14 ",
    "Data15": "15 ",
    "Data16": "16 ",
}
LIB8A_DIR = (
    WORKBENCH
    / "02_Runs"
    / "RUN_0008A_FAST_PAPER_Input_Freeze_and_Pilot"
)
sys.path.insert(0, str(LIB8A_DIR))
import task0008a_lib as L8  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    with (RUN / "COMMAND_LOG.txt").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def data_dir(label: str) -> Path:
    prefix = DATA_PREFIX[label]
    return next(p for p in RAW.iterdir() if p.is_dir() and p.name.startswith(prefix))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def open_mmap(name: str, dtype: Any, shape: tuple[int, ...], fill: Any) -> np.memmap:
    path = WORK / f"{name}.npy"
    array = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)
    array[...] = fill
    return array


def existing_mmap(name: str, mode: str = "r") -> np.memmap:
    return np.load(WORK / f"{name}.npy", mmap_mode=mode)


def write_tif(path: Path, values: np.ndarray, dtype: str, nodata: Any) -> None:
    profile = {
        "driver": "GTiff",
        "height": HEIGHT,
        "width": WIDTH,
        "count": 1,
        "dtype": dtype,
        "crs": "EPSG:4326",
        "transform": from_origin(-180.0, 85.0, 0.5, 0.5),
        "nodata": nodata,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(values.astype(dtype), 1)


class HoldoutLog:
    fields = [
        "event_id",
        "timestamp_utc",
        "stage",
        "dataset",
        "variable",
        "requested_period",
        "holdout_overlap_requested",
        "scientific_array_read",
        "scientific_bytes_read",
        "holdout_scientific_bytes_read",
        "decision",
        "purpose",
        "notes",
    ]

    def __init__(self, resume: bool = False) -> None:
        self.path = RUN / "HOLDOUT_ACCESS_LOG.csv"
        if resume and self.path.exists():
            with self.path.open(encoding="utf-8-sig", newline="") as handle:
                self.counter = sum(1 for _ in csv.DictReader(handle))
        else:
            write_csv(self.path, [], self.fields)
            self.counter = 0

    def add(self, **values: Any) -> None:
        self.counter += 1
        row = {
            "event_id": self.counter,
            "timestamp_utc": utc_now(),
            "stage": "TASK0008B",
            "dataset": "",
            "variable": "",
            "requested_period": "",
            "holdout_overlap_requested": False,
            "scientific_array_read": False,
            "scientific_bytes_read": 0,
            "holdout_scientific_bytes_read": 0,
            "decision": "",
            "purpose": "",
            "notes": "",
            **values,
        }
        with self.path.open("a", encoding="utf-8-sig", newline="") as handle:
            csv.DictWriter(handle, fieldnames=self.fields).writerow(row)

    def allow(self, dataset: str, variable: str, period: str, nbytes: int, purpose: str, notes: str = "") -> None:
        if any(year in period for year in ("2021", "2022", "2023", "2024")):
            self.add(
                dataset=dataset,
                variable=variable,
                requested_period=period,
                holdout_overlap_requested=True,
                decision="DENIED_BEFORE_IO",
                purpose=purpose,
                notes="Holdout firewall rejected period before array I/O.",
            )
            raise RuntimeError(f"Holdout firewall: {period}")
        self.add(
            dataset=dataset,
            variable=variable,
            requested_period=period,
            scientific_array_read=True,
            scientific_bytes_read=nbytes,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_PRIMARY_OR_STATIC",
            purpose=purpose,
            notes=notes,
        )

    def self_test(self) -> None:
        try:
            self.allow("Data01", "kNDVI", "2021-01", 0, "firewall self-test")
        except RuntimeError:
            return
        raise RuntimeError("Holdout firewall self-test failed")


_TILE_RE = re.compile(r"_(E|W)(\d{3})_(E|W)(\d{3})_(N|S)(\d{2})_(N|S)(\d{2})_")


def _coord(hemi: str, number: str) -> float:
    value = float(number)
    return -value if hemi in ("W", "S") else value


def nominal_bounds(path: Path) -> tuple[float, float, float, float]:
    match = _TILE_RE.search(path.name)
    if not match:
        raise RuntimeError(f"Cannot parse tile bounds: {path.name}")
    x1, x2 = _coord(match[1], match[2]), _coord(match[3], match[4])
    y1, y2 = _coord(match[5], match[6]), _coord(match[7], match[8])
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def tile_target_geometry(bounds: tuple[float, float, float, float]) -> tuple[int, int, Any, int, int]:
    west, south, east, north = bounds
    height = int(round((north - south) / 0.5))
    width = int(round((east - west) / 0.5))
    row = int(round((85.0 - north) / 0.5))
    col = int(round((west + 180.0) / 0.5))
    return height, width, from_origin(west, north, 0.5, 0.5), row, col


def aggregate_reprojected_tiles(
    paths: Sequence[Path], value_band: int, support_band: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    out = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    support_out = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    source_count = np.zeros((HEIGHT, WIDTH), dtype=np.int16)
    for path in sorted(paths):
        bounds = nominal_bounds(path)
        if bounds[3] <= -60.0 or bounds[1] >= 85.0:
            continue
        west = max(-180.0, bounds[0])
        south = max(-60.0, bounds[1])
        east = min(180.0, bounds[2])
        north = min(85.0, bounds[3])
        if east <= west or north <= south:
            continue
        clipped = (west, south, east, north)
        height, width, transform, row, col = tile_target_geometry(clipped)
        with rasterio.open(path) as src:
            value = src.read(value_band, masked=True).filled(np.nan).astype(np.float32)
            support = src.read(support_band, masked=True).filled(np.nan).astype(np.float32)
            valid = np.isfinite(value) & np.isfinite(support) & (support > 0)
            numerator = np.where(valid, value * support, np.nan).astype(np.float32)
            denominator = np.where(valid, support, np.nan).astype(np.float32)
            dst_num = np.full((height, width), np.nan, dtype=np.float32)
            dst_den = np.full((height, width), np.nan, dtype=np.float32)
            common = {
                "src_transform": src.transform,
                "src_crs": src.crs,
                "dst_transform": transform,
                "dst_crs": "EPSG:4326",
                "src_nodata": np.nan,
                "dst_nodata": np.nan,
                "resampling": Resampling.average,
            }
            reproject(numerator, dst_num, **common)
            reproject(denominator, dst_den, **common)
        ok = np.isfinite(dst_num) & np.isfinite(dst_den) & (dst_den > 0)
        target = out[row : row + height, col : col + width]
        target_support = support_out[row : row + height, col : col + width]
        target_count = source_count[row : row + height, col : col + width]
        target[ok] = dst_num[ok] / dst_den[ok]
        target_support[ok] = dst_den[ok]
        target_count[ok] = 1
    return out, support_out, source_count


def process_d03_year(year: int, directory: str) -> tuple[int, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    paths = sorted(Path(directory, str(year)).glob("*.tif"))
    paths = [p for p in paths if p.name.startswith("MOD44B_native1km_g010_tile_")]
    values, support, count = aggregate_reprojected_tiles(paths, 1, 2)
    return year, values / 100.0, support, count, [str(p) for p in paths]


def build_forest_domain(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    log("Phase A: Data03 support-weighted global forest-cover domain")
    d03 = data_dir("Data03")
    annual = open_mmap("annual_forest_cover", np.float32, (20, HEIGHT, WIDTH), np.nan)
    support = open_mmap("annual_forest_cover_support", np.float32, (20, HEIGHT, WIDTH), np.nan)
    count = open_mmap("annual_forest_cover_source_count", np.int16, (20, HEIGHT, WIDTH), 0)
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        futures = {pool.submit(process_d03_year, year, str(d03)): year for year in YEARS}
        for future in as_completed(futures):
            year, values, supports, counts, paths = future.result()
            index = year - 2001
            annual[index] = values
            support[index] = supports
            count[index] = counts
            nbytes = values.nbytes + supports.nbytes + counts.nbytes
            logger.allow(
                "Data03",
                "tree_cover_fraction/support/source_count",
                str(year),
                nbytes,
                "main forest domain and threshold sensitivity",
                "Support-weighted native-Sinusoidal reprojection; only annual directories 2001-2020.",
            )
            for path in paths:
                manifest.append(
                    input_record("Data03", Path(path), str(year), "bands 1-2", "forest domain")
                )
            log(f"Data03 year {year} complete ({len(paths)} canonical tiles)")
    annual.flush()
    support.flush()
    count.flush()
    valid = np.isfinite(annual) & (support > 0)
    valid_years = valid.sum(axis=0).astype(np.int16)
    total = np.sum(np.where(valid, annual, 0.0), axis=0, dtype=np.float64)
    mean = np.divide(
        total,
        valid_years,
        out=np.full((HEIGHT, WIDTH), np.nan, dtype=np.float64),
        where=valid_years > 0,
    ).astype(np.float32)
    masks: dict[str, np.ndarray] = {}
    for threshold in (30, 40, 50):
        mask = (valid_years >= 16) & (mean >= threshold / 100.0)
        masks[str(threshold)] = mask
        write_tif(
            DERIVED / f"GLOBAL_FOREST_MASK_{threshold}.tif",
            mask.astype(np.uint8),
            "uint8",
            0,
        )
    write_tif(DERIVED / "GLOBAL_FOREST_COVER_MEAN_2001_2020.tif", mean, "float32", np.nan)
    np.save(WORK / "forest_cover_mean.npy", mean)
    np.save(WORK / "forest_cover_valid_years.npy", valid_years)
    for threshold, mask in masks.items():
        np.save(WORK / f"forest_mask_{threshold}.npy", mask)
    rows, cols = np.indices((HEIGHT, WIDTH))
    lat = 84.75 - rows * 0.5
    lon = -179.75 + cols * 0.5
    area = cell_area_km2(lat)
    eligibility = {
        "pixel_id": (rows.astype(np.int64) * WIDTH + cols).ravel(),
        "grid_row": rows.astype(np.int32).ravel(),
        "grid_col": cols.astype(np.int32).ravel(),
        "latitude": lat.astype(np.float32).ravel(),
        "longitude": lon.astype(np.float32).ravel(),
        "cell_area_km2": area.astype(np.float32).ravel(),
        "forest_cover_mean_2001_2020": mean.ravel(),
        "forest_cover_valid_years": valid_years.ravel(),
        "forest_mask_30": masks["30"].astype(np.int32).ravel(),
        "forest_mask_40": masks["40"].astype(np.int32).ravel(),
        "forest_mask_50": masks["50"].astype(np.int32).ravel(),
    }
    write_parquet(DERIVED / "GLOBAL_FOREST_ELIGIBILITY.parquet", eligibility, {
        "definition": "mean supported Data03 tree cover 2001-2020; >=16 valid years",
        "main_threshold": "0.30",
    })
    area_rows = []
    for threshold, mask in masks.items():
        area_rows.append(
            {
                "threshold_pct": int(threshold),
                "eligible_cells": int(mask.sum()),
                "eligible_area_km2": float(area[mask].sum()),
                "valid_year_requirement": 16,
            }
        )
    write_csv(
        RUN / "FOREST_AREA_SUMMARY.csv",
        area_rows,
        ["threshold_pct", "eligible_cells", "eligible_area_km2", "valid_year_requirement"],
    )
    return {"mean": mean, "valid_years": valid_years, **masks}


def cell_area_km2(latitude: np.ndarray) -> np.ndarray:
    radius = 6371.0088
    half = math.radians(0.25)
    dlon = math.radians(0.5)
    latr = np.deg2rad(latitude)
    return radius**2 * dlon * (np.sin(latr + half) - np.sin(latr - half))


def input_record(dataset: str, path: Path, period: str, bands: str, role: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "dataset": dataset,
        "input_path": str(path),
        "period_selected": period,
        "bands_selected": bands,
        "scientific_role": role,
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "checksum_policy": "RAW_METADATA_SIZE_MTIME_IMMUTABILITY",
        "read_only": True,
    }


def interval_overlaps(start: date, end: date) -> list[tuple[int, int]]:
    output: list[tuple[int, int]] = []
    cursor = date(start.year, start.month, 1)
    while cursor < end:
        next_month = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
        days = (min(end, next_month) - max(start, cursor)).days
        if days > 0 and 2001 <= cursor.year <= 2020:
            output.append(((cursor.year - 2001) * 12 + cursor.month - 1, days))
        cursor = next_month
    return output


def build_kndvi(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> None:
    log("Data01: actual-date, cross-month overlap-weighted monthly kNDVI")
    d01 = data_dir("Data01") / "0.5"
    files = {
        int(re.search(r"_(20\d{2})_", p.name).group(1)): p
        for p in d01.glob("*_g050_global_*_v07.tif")
        if re.search(r"_(20\d{2})_", p.name)
    }
    selected = {year: files[year] for year in YEARS}
    all_dates: list[date] = []
    file_records: dict[int, list[tuple[date, dict[str, str]]]] = {}
    for year, path in selected.items():
        grouped: dict[str, dict[date, str]] = {
            "kNDVI": {},
            "supportFrac": {},
            "validFracSupport": {},
            "goodFracSupport": {},
        }
        with rasterio.open(path) as src:
            for description in src.descriptions:
                match = re.fullmatch(
                    r"(kNDVI|supportFrac|validFracSupport|goodFracSupport)_(\d{8})",
                    description or "",
                )
                if not match:
                    raise RuntimeError(f"Unexpected Data01 band description: {description}")
                day = datetime.strptime(match.group(2), "%Y%m%d").date()
                grouped[match.group(1)][day] = str(description)
        dates = sorted(grouped["kNDVI"])
        if any(set(grouped[key]) != set(dates) for key in grouped):
            raise RuntimeError(f"Data01 date mismatch: {path}")
        file_records[year] = [
            (day, {key: grouped[key][day] for key in grouped}) for day in dates
        ]
        all_dates.extend(dates)
    all_dates.sort()
    end_lookup = {
        day: all_dates[index + 1] if index + 1 < len(all_dates) else date(2021, 1, 1)
        for index, day in enumerate(all_dates)
    }
    shape = (240, HEIGHT, WIDTH)
    kndvi = open_mmap("monthly_kndvi", np.float32, shape, np.nan)
    source = open_mmap("monthly_kndvi_support", np.float32, shape, np.nan)
    valid_area = open_mmap("monthly_kndvi_valid_area", np.float32, shape, np.nan)
    effective_out = open_mmap("monthly_kndvi_effective_weight", np.float32, shape, 0.0)
    count_out = open_mmap("monthly_kndvi_source_count", np.int16, shape, 0)
    temporal_rows: list[dict[str, Any]] = []
    for year in YEARS:
        path = selected[year]
        records = file_records[year]
        descriptions = [name for _, names in records for name in names.values()]
        with rasterio.open(path) as src:
            index = {name: i for i, name in enumerate(src.descriptions, start=1)}
            block = src.read([index[name] for name in descriptions], masked=True)
            block = block.filled(np.nan).astype(np.float32)
        k_num = np.zeros((12, HEIGHT, WIDTH), dtype=np.float64)
        effective = np.zeros((12, HEIGHT, WIDTH), dtype=np.float64)
        support_num = np.zeros((12, HEIGHT, WIDTH), dtype=np.float64)
        support_days = np.zeros((12, HEIGHT, WIDTH), dtype=np.float32)
        valid_num = np.zeros((12, HEIGHT, WIDTH), dtype=np.float64)
        valid_days = np.zeros((12, HEIGHT, WIDTH), dtype=np.float32)
        contributing = np.zeros((12, HEIGHT, WIDTH), dtype=np.int16)
        offset = 0
        for start, names in records:
            values = {
                variable: block[offset + i].astype(np.float64)
                for i, variable in enumerate(names)
            }
            offset += 4
            support_value = values["supportFrac"]
            valid_fraction = values["validFracSupport"]
            support_defined = np.isfinite(support_value)
            valid_defined = support_defined & (
                (support_value == 0) | np.isfinite(valid_fraction)
            )
            usable = np.where(support_value == 0, 0.0, support_value * valid_fraction)
            usable[~valid_defined] = np.nan
            k = values["kNDVI"]
            k_valid = np.isfinite(k) & np.isfinite(usable) & (usable > 0)
            for target, days in interval_overlaps(start, end_lookup[start]):
                if target // 12 != year - 2001:
                    raise RuntimeError("Unexpected cross-year Data01 overlap")
                month = target % 12
                support_num[month] += np.where(
                    support_defined, days * support_value, 0.0
                )
                support_days[month] += support_defined.astype(np.float32) * days
                valid_num[month] += np.where(valid_defined, days * usable, 0.0)
                valid_days[month] += valid_defined.astype(np.float32) * days
                weight = days * usable
                k_num[month] += np.where(k_valid, weight * k, 0.0)
                effective[month] += np.where(k_valid, weight, 0.0)
                contributing[month] += k_valid.astype(np.int16)
                temporal_rows.append(
                    {
                        "dataset": "Data01",
                        "source_date": start.isoformat(),
                        "source_end_exclusive": end_lookup[start].isoformat(),
                        "target_month": MONTHS[target],
                        "overlap_days": days,
                        "mapping": "actual_date_half_open_interval_overlap_days",
                    }
                )
        for month in range(12):
            target = (year - 2001) * 12 + month
            days = calendar.monthrange(year, month + 1)[1]
            kndvi[target] = np.divide(
                k_num[month],
                effective[month],
                out=np.full((HEIGHT, WIDTH), np.nan),
                where=effective[month] > 0,
            )
            source[target] = np.divide(
                support_num[month],
                days,
                out=np.full((HEIGHT, WIDTH), np.nan),
                where=np.isclose(support_days[month], days),
            )
            valid_area[target] = np.divide(
                valid_num[month],
                days,
                out=np.full((HEIGHT, WIDTH), np.nan),
                where=np.isclose(valid_days[month], days),
            )
            effective_out[target] = effective[month]
            count_out[target] = contributing[month]
        manifest.append(input_record("Data01", path, str(year), "all dated kNDVI/support QA bands", "monthly state"))
        logger.allow(
            "Data01",
            "kNDVI/support/valid_area/effective_weight/source_count",
            str(year),
            block.nbytes,
            "monthly actual-date aggregation",
            "No interpolation; 2021-2024 files were not opened.",
        )
        log(f"Data01 year {year} complete")
    for array in (kndvi, source, valid_area, effective_out, count_out):
        array.flush()
    write_csv(
        RUN / "DATE_WEIGHT_MAPPING.csv",
        temporal_rows,
        [
            "dataset",
            "source_date",
            "source_end_exclusive",
            "target_month",
            "overlap_days",
            "mapping",
        ],
    )


def aligned_aggregate(
    value: np.ndarray, common_valid: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if value.shape != (2900, 7200):
        raise RuntimeError(f"Expected global g005 grid, got {value.shape}")
    lat_weights = np.cos(
        np.deg2rad(84.975 - np.arange(2900, dtype=np.float64) * 0.05)
    ).astype(np.float32)
    result = np.full((HEIGHT, WIDTH), np.nan, dtype=np.float32)
    support = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    count = np.zeros((HEIGHT, WIDTH), dtype=np.int16)
    # Row-blocked exact aggregation keeps peak memory bounded. The formula and
    # cosine(latitude-center) weights are identical to TASK 0002/0008A.
    for target_row0 in range(0, HEIGHT, 29):
        target_row1 = min(HEIGHT, target_row0 + 29)
        source_row0, source_row1 = target_row0 * 10, target_row1 * 10
        block = value[source_row0:source_row1].reshape(
            target_row1 - target_row0, 10, WIDTH, 10
        )
        weights = lat_weights[source_row0:source_row1].reshape(
            target_row1 - target_row0, 10, 1, 1
        )
        if common_valid is None:
            valid = np.isfinite(block)
        else:
            valid = (
                common_valid[source_row0:source_row1].reshape(
                    target_row1 - target_row0, 10, WIDTH, 10
                )
                & np.isfinite(block)
            )
        numerator = np.sum(
            np.where(valid, block * weights, 0.0),
            axis=(1, 3),
            dtype=np.float64,
        )
        denominator = np.sum(
            np.where(valid, weights, 0.0),
            axis=(1, 3),
            dtype=np.float64,
        )
        full_den = np.sum(weights[:, :, 0, 0], axis=1, dtype=np.float64)[:, None] * 10.0
        result[target_row0:target_row1] = np.divide(
            numerator,
            denominator,
            out=np.full(numerator.shape, np.nan),
            where=denominator > 0,
        )
        support[target_row0:target_row1] = np.divide(
            denominator,
            full_den,
            out=np.zeros(denominator.shape),
            where=full_den > 0,
        )
        count[target_row0:target_row1] = np.sum(valid, axis=(1, 3)).astype(np.int16)
    return result, support, count


def read_band(src: rasterio.io.DatasetReader, index: int) -> np.ndarray:
    value = src.read(index, masked=True)
    return value.astype(np.float32).filled(np.nan)


def build_landcover(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> None:
    log("Data04: area-weighted class fractions; categorical codes are not averaged")
    d04 = data_dir("Data04")
    annual_type = open_mmap("annual_forest_type", np.int16, (20, HEIGHT, WIDTH), -1)
    annual_support = open_mmap("annual_forest_type_support", np.float32, (20, HEIGHT, WIDTH), np.nan)
    annual_count = open_mmap("annual_forest_type_source_count", np.int16, (20, HEIGHT, WIDTH), 0)
    forest_fraction = open_mmap("annual_igbp_forest_fraction", np.float32, (20, HEIGHT, WIDTH), np.nan)
    qc_rows: list[dict[str, Any]] = []
    for year in YEARS:
        path = next(d04.glob(f"*_g005_global_{year}_v01.tif"))
        with rasterio.open(path) as src:
            common = np.ones((2900, 7200), dtype=bool)
            for band in range(2, 20):
                common &= np.isfinite(read_band(src, band))
            best = np.full((HEIGHT, WIDTH), -np.inf, dtype=np.float32)
            dominant = np.full((HEIGHT, WIDTH), -1, dtype=np.int16)
            forest = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
            closure = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
            for class_code, band in enumerate(range(3, 20)):
                aggregated, support, count = aligned_aggregate(read_band(src, band), common)
                fraction = aggregated / 100.0
                closure += np.where(np.isfinite(fraction), fraction, 0.0)
                if 1 <= class_code <= 5:
                    forest += np.where(np.isfinite(fraction), fraction, 0.0)
                update = np.isfinite(fraction) & (fraction > best)
                dominant[update] = class_code
                best[update] = fraction[update]
        i = year - 2001
        annual_type[i] = dominant
        annual_support[i] = support
        annual_count[i] = count
        forest_fraction[i] = forest
        valid = dominant >= 0
        error = np.abs(closure[valid] - 1.0)
        qc_rows.append(
            {
                "year": year,
                "valid_cells": int(valid.sum()),
                "mean_source_support": float(np.nanmean(support)),
                "max_absolute_fraction_closure_error": float(np.max(error)),
                "closure_tolerance": 0.03,
                "closure_pass": bool(np.max(error) <= 0.03),
                "categorical_code_averaged": False,
                "dominant_recomputed_from_fractions": True,
            }
        )
        manifest.append(input_record("Data04", path, str(year), "confidence and IGBP fractions c00-c16", "forest type/biome"))
        logger.allow("Data04", "IGBP fractions/dominant type", str(year), path.stat().st_size, "annual forest-type covariate")
        log(f"Data04 year {year} complete")
    for array in (annual_type, annual_support, annual_count, forest_fraction):
        array.flush()
    write_csv(
        RUN / "LANDCOVER_QC.csv",
        qc_rows,
        [
            "year",
            "valid_cells",
            "mean_source_support",
            "max_absolute_fraction_closure_error",
            "closure_tolerance",
            "closure_pass",
            "categorical_code_averaged",
            "dominant_recomputed_from_fractions",
        ],
    )


def mosaic_band(opened: Sequence[rasterio.io.DatasetReader], description: str) -> np.ndarray:
    output = np.full((2900, 7200), np.nan, dtype=np.float32)
    for src in opened:
        descriptions = {name: i for i, name in enumerate(src.descriptions, start=1)}
        if description not in descriptions:
            raise RuntimeError(f"Missing {description} in {src.name}")
        block = read_band(src, descriptions[description])
        col = int(round((src.transform.c + 180.0) / 0.05))
        row = int(round((85.0 - src.transform.f) / 0.05))
        r1, c1 = min(2900, row + src.height), min(7200, col + src.width)
        if r1 <= row or c1 <= col:
            continue
        target = output[row:r1, col:c1]
        source = block[: r1 - row, : c1 - col]
        overlap = np.isfinite(target) & np.isfinite(source)
        if np.any(overlap & (np.abs(target - source) > 1e-6)):
            raise RuntimeError(f"Conflicting raster parts for {description}")
        fill = ~np.isfinite(target) & np.isfinite(source)
        target[fill] = source[fill]
    return output


def part_files(dataset: str, year: int, marker: str) -> list[Path]:
    return sorted(
        p for p in data_dir(dataset).rglob("*.tif") if f"_{year}_{marker}-" in p.name
    )


def mosaic_bands_window(
    opened: Sequence[rasterio.io.DatasetReader],
    descriptions: Sequence[str],
    source_row0: int,
    source_row1: int,
    source_col0: int,
    source_col1: int,
) -> np.ndarray:
    output = np.full(
        (len(descriptions), source_row1 - source_row0, source_col1 - source_col0),
        np.nan,
        dtype=np.float32,
    )
    for src in opened:
        indexes = {name: i for i, name in enumerate(src.descriptions, start=1)}
        missing = [name for name in descriptions if name not in indexes]
        if missing:
            raise RuntimeError(f"Missing descriptions in {src.name}: {missing}")
        part_col0 = int(round((src.transform.c + 180.0) / 0.05))
        part_row0 = int(round((85.0 - src.transform.f) / 0.05))
        part_col1, part_row1 = part_col0 + src.width, part_row0 + src.height
        c0, c1 = max(part_col0, source_col0), min(part_col1, source_col1)
        r0, r1 = max(part_row0, source_row0), min(part_row1, source_row1)
        if c1 <= c0 or r1 <= r0:
            continue
        window = rasterio.windows.Window(
            c0 - part_col0, r0 - part_row0, c1 - c0, r1 - r0
        )
        block = src.read(
            [indexes[name] for name in descriptions], window=window, masked=True
        ).astype(np.float32).filled(np.nan)
        target = output[
            :,
            r0 - source_row0 : r1 - source_row0,
            c0 - source_col0 : c1 - source_col0,
        ]
        overlap = np.isfinite(target) & np.isfinite(block)
        if np.any(overlap & (np.abs(target - block) > 1e-6)):
            raise RuntimeError("Conflicting part overlap in tiled hydroclimate read")
        fill = ~np.isfinite(target) & np.isfinite(block)
        target[fill] = block[fill]
    return output


def aggregate_tile_exact(
    value: np.ndarray, global_source_row0: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source_rows, source_cols = value.shape
    if source_rows % 10 or source_cols % 10:
        raise RuntimeError("Hydroclimate tile is not aligned to 0.5-degree cells")
    height, width = source_rows // 10, source_cols // 10
    block = value.reshape(height, 10, width, 10).astype(np.float64)
    source_lat = 84.975 - (global_source_row0 + np.arange(source_rows)) * 0.05
    weights = np.cos(np.deg2rad(source_lat)).astype(np.float64).reshape(
        height, 10, 1, 1
    )
    valid = np.isfinite(block)
    numerator = np.sum(
        np.where(valid, block * weights, 0.0), axis=(1, 3), dtype=np.float64
    )
    denominator = np.sum(
        np.where(valid, weights, 0.0), axis=(1, 3), dtype=np.float64
    )
    full = np.sum(weights[:, :, 0, 0], axis=1)[:, None] * 10.0
    result = np.divide(
        numerator,
        denominator,
        out=np.full((height, width), np.nan),
        where=denominator > 0,
    ).astype(np.float32)
    support = np.divide(
        denominator,
        full,
        out=np.zeros((height, width)),
        where=full > 0,
    ).astype(np.float32)
    count = np.sum(valid, axis=(1, 3)).astype(np.int16)
    return result, support, count


def process_hydro_year(
    year: int,
    p14_text: Sequence[str],
    p15_text: Sequence[str],
    target_tiles: Sequence[tuple[int, int, int, int]],
) -> tuple[int, dict[str, np.ndarray]]:
    p14 = [Path(value) for value in p14_text]
    p15 = [Path(value) for value in p15_text]
    output = {
        "vpd": np.full((12, HEIGHT, WIDTH), np.nan, dtype=np.float32),
        "vpd_support": np.full((12, HEIGHT, WIDTH), np.nan, dtype=np.float32),
        "vpd_count": np.zeros((12, HEIGHT, WIDTH), dtype=np.int16),
        "soil": np.full((12, HEIGHT, WIDTH), np.nan, dtype=np.float32),
        "soil_support": np.full((12, HEIGHT, WIDTH), np.nan, dtype=np.float32),
        "soil_count": np.zeros((12, HEIGHT, WIDTH), dtype=np.int16),
    }
    opened14 = [rasterio.open(path) for path in p14]
    opened15 = [rasterio.open(path) for path in p15]
    try:
        descriptions14 = [
            name
            for month in range(1, 13)
            for name in (
                f"vpd_mean_m{month:02d}_kPa",
                f"temporal_valid_m{month:02d}_frac",
            )
        ]
        descriptions15 = [
            name
            for month in range(1, 13)
            for name in (
                f"swvl1_mean_m{month:02d}_m3m3",
                f"swvl2_mean_m{month:02d}_m3m3",
                f"swvl3_mean_m{month:02d}_m3m3",
                f"temporal_valid_m{month:02d}_frac",
            )
        ]
        for target_row0, target_row1, target_col0, target_col1 in target_tiles:
            source_row0, source_row1 = target_row0 * 10, target_row1 * 10
            source_col0, source_col1 = target_col0 * 10, target_col1 * 10
            raw14 = mosaic_bands_window(
                opened14,
                descriptions14,
                source_row0,
                source_row1,
                source_col0,
                source_col1,
            )
            raw15 = mosaic_bands_window(
                opened15,
                descriptions15,
                source_row0,
                source_row1,
                source_col0,
                source_col1,
            )
            target_slice = (
                slice(target_row0, target_row1),
                slice(target_col0, target_col1),
            )
            for month in range(12):
                vv, _, vc = aggregate_tile_exact(raw14[month * 2], source_row0)
                vs, _, _ = aggregate_tile_exact(raw14[month * 2 + 1], source_row0)
                layers = [
                    aggregate_tile_exact(raw15[month * 4 + offset], source_row0)
                    for offset in range(3)
                ]
                ss, _, _ = aggregate_tile_exact(raw15[month * 4 + 3], source_row0)
                output["vpd"][(month, *target_slice)] = vv
                output["vpd_support"][(month, *target_slice)] = vs
                output["vpd_count"][(month, *target_slice)] = vc
                output["soil"][(month, *target_slice)] = (
                    0.07 * layers[0][0]
                    + 0.21 * layers[1][0]
                    + 0.72 * layers[2][0]
                )
                output["soil_support"][(month, *target_slice)] = ss
                output["soil_count"][(month, *target_slice)] = np.minimum(
                    np.minimum(layers[0][2], layers[1][2]), layers[2][2]
                )
            del raw14, raw15
    finally:
        for src in [*opened14, *opened15]:
            src.close()
    return year, output


def build_hydroclimate(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> None:
    log("Data14/15: monthly VPD and 0-100 cm root-zone soil moisture")
    shape = (240, HEIGHT, WIDTH)
    vpd = open_mmap("monthly_vpd", np.float32, shape, np.nan)
    vpd_support = open_mmap("monthly_vpd_support", np.float32, shape, np.nan)
    vpd_count = open_mmap("monthly_vpd_source_count", np.int16, shape, 0)
    soil = open_mmap("monthly_soil_moisture", np.float32, shape, np.nan)
    soil_support = open_mmap("monthly_soil_moisture_support", np.float32, shape, np.nan)
    soil_count = open_mmap("monthly_soil_moisture_source_count", np.int16, shape, 0)
    paths_by_year: dict[int, tuple[list[Path], list[Path]]] = {}
    for year in YEARS:
        p14 = part_files("Data14", year, "60band_v04")
        p15 = part_files("Data15", year, "96band_v02")
        if len(p14) != 8 or len(p15) != 8:
            raise RuntimeError(f"Expected eight parts per year: {year}, {len(p14)}, {len(p15)}")
        paths_by_year[year] = (p14, p15)
    forest = np.load(WORK / "forest_mask_30.npy")
    target_tiles: list[tuple[int, int, int, int]] = []
    for row0 in range(0, HEIGHT, 20):
        row1 = min(HEIGHT, row0 + 20)
        for col0 in range(0, WIDTH, 20):
            col1 = min(WIDTH, col0 + 20)
            if np.any(forest[row0:row1, col0:col1]):
                target_tiles.append((row0, row1, col0, col1))
    log(
        f"Hydroclimate production tiles: {len(target_tiles)} 10-degree analysis-support tiles; "
        "multi-band pixel-interleaved reads prevent redundant LZW decompression"
    )
    with ProcessPoolExecutor(max_workers=min(6, os.cpu_count() or 1)) as pool:
        futures = {
            pool.submit(
                process_hydro_year,
                year,
                [str(path) for path in paths_by_year[year][0]],
                [str(path) for path in paths_by_year[year][1]],
                target_tiles,
            ): year
            for year in YEARS
        }
        for future in as_completed(futures):
            year, output = future.result()
            start = (year - 2001) * 12
            stop = start + 12
            vpd[start:stop] = output["vpd"]
            vpd_support[start:stop] = output["vpd_support"]
            vpd_count[start:stop] = output["vpd_count"]
            soil[start:stop] = output["soil"]
            soil_support[start:stop] = output["soil_support"]
            soil_count[start:stop] = output["soil_count"]
            p14, p15 = paths_by_year[year]
            for path in p14:
                manifest.append(input_record("Data14", path, str(year), "vpd_mean_mXX_kPa; temporal_valid_mXX_frac", "hydroclimate"))
            for path in p15:
                manifest.append(input_record("Data15", path, str(year), "swvl1-3 mean; temporal_valid_mXX_frac", "hydroclimate"))
            logger.allow("Data14", "VPD kPa/support/source_count", str(year), sum(p.stat().st_size for p in p14), "monthly hydroclimate")
            logger.allow("Data15", "root-zone soil moisture/support/source_count", str(year), sum(p.stat().st_size for p in p15), "monthly hydroclimate", "0.07*L1 + 0.21*L2 + 0.72*L3")
            log(f"Data14/15 year {year} complete")
    for array in (vpd, vpd_support, vpd_count, soil, soil_support, soil_count):
        array.flush()


def aggregate_weighted_global(path: Path, value_band: int, support_band: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        value = read_band(src, value_band)
        support = read_band(src, support_band)
    value4 = value.reshape(HEIGHT, 10, WIDTH, 10).astype(np.float64)
    support4 = support.reshape(HEIGHT, 10, WIDTH, 10).astype(np.float64)
    valid = np.isfinite(value4) & np.isfinite(support4) & (support4 > 0)
    denominator = np.sum(np.where(valid, support4, 0.0), axis=(1, 3))
    numerator = np.sum(np.where(valid, value4 * support4, 0.0), axis=(1, 3))
    result = np.divide(
        numerator,
        denominator,
        out=np.full((HEIGHT, WIDTH), np.nan),
        where=denominator > 0,
    ).astype(np.float32)
    return result, (denominator / 100.0).astype(np.float32), np.sum(valid, axis=(1, 3)).astype(np.int16)


def build_productivity(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> None:
    log("Data07: annual GPP/NPP functional-validation cube")
    d07 = data_dir("Data07")
    gpp = open_mmap("annual_gpp", np.float32, (20, HEIGHT, WIDTH), np.nan)
    npp = open_mmap("annual_npp", np.float32, (20, HEIGHT, WIDTH), np.nan)
    support = open_mmap("annual_productivity_support", np.float32, (20, HEIGHT, WIDTH), np.nan)
    count = open_mmap("annual_productivity_source_count", np.int16, (20, HEIGHT, WIDTH), 0)
    for year in YEARS:
        path = next(d07.rglob(f"*_{year}_v04.tif"))
        gv, gs, gc = aggregate_weighted_global(path, 2, 1)
        nv, ns, nc = aggregate_weighted_global(path, 3, 1)
        i = year - 2001
        gpp[i], npp[i] = gv, nv
        support[i] = np.minimum(gs, ns)
        count[i] = np.minimum(gc, nc)
        manifest.append(input_record("Data07", path, str(year), "bands 1-3", "GPP/NPP validation"))
        logger.allow("Data07", "GPP/NPP/support/source_count", str(year), path.stat().st_size, "functional validation")
        log(f"Data07 year {year} complete")
    for array in (gpp, npp, support, count):
        array.flush()


def find_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one match {root} {pattern}: {len(matches)}")
    return matches[0]


def build_static(logger: HoldoutLog, manifest: list[dict[str, Any]]) -> None:
    log("Data09/10/11/12/13/16: static backgrounds")
    d09 = data_dir("Data09")
    hm_paths = sorted((d09 / "01_downloaded_tiles").glob("*.tif"))
    hm, hm_support, hm_count = aggregate_reprojected_tiles(hm_paths, 6, 1)
    for path in hm_paths:
        manifest.append(input_record("Data09", path, "nominal 2020 static", "band 6 with support band 1", "human modification"))
    logger.allow("Data09", "human modification", "static nominal 2020", sum(p.stat().st_size for p in hm_paths), "matching/control")

    d10 = data_dir("Data10")
    climate_path = find_one(d10, "*.tif")
    climate, climate_support, climate_count = L8.aggregate_global_mode(climate_path, GLOBAL, 14, 1)
    manifest.append(input_record("Data10", climate_path, "static", "climate class band 14; support band 1", "climate stratification"))
    logger.allow("Data10", "climate_zone", "static", climate_path.stat().st_size, "climate stratification")

    d11 = data_dir("Data11")
    biomass_path = find_one(d11, "*.tif")
    biomass, biomass_support, biomass_count = L8.aggregate_global_weighted(biomass_path, GLOBAL, 8, 3)
    manifest.append(input_record("Data11", biomass_path, "nominal 2010 static", "total living biomass band 8; support band 3", "biomass control"))
    logger.allow("Data11", "biomass", "static nominal 2010", biomass_path.stat().st_size, "biomass control")

    d12 = data_dir("Data12")
    soil_paths = sorted((d12 / "01_downloaded_tiles").glob("*.tif"))
    soil_bg, soil_bg_support, soil_bg_count = aggregate_reprojected_tiles(soil_paths, 19, 1)
    for path in soil_paths:
        manifest.append(input_record("Data12", path, "static", "field capacity 100cm band 19; support band 1", "soil background"))
    logger.allow("Data12", "field_capacity_100cm", "static", sum(p.stat().st_size for p in soil_paths), "background control")

    d13 = data_dir("Data13")
    topo_paths = sorted((d13 / "02_downloaded_land368").glob("*.tif"))
    topo, topo_support, topo_count = aggregate_reprojected_tiles(topo_paths, 2, 1)
    for path in topo_paths:
        manifest.append(input_record("Data13", path, "static", "mean elevation band 2; support band 1", "topographic background"))
    logger.allow("Data13", "elevation", "static", sum(p.stat().st_size for p in topo_paths), "background control")

    d16 = data_dir("Data16")
    ifl_path = d16 / "03 Global Production" / "01 GLOBAL_v01" / "Data16_IFL_fraction_g005_global_2000_2025_10band_v01.tif"
    intact, intact_support, intact_count = L8.aggregate_global_mean(ifl_path, GLOBAL, 4)
    manifest.append(input_record("Data16", ifl_path, "nominal 2020 static", "IFL 2020 fraction band 4 only", "intact forest matching"))
    logger.allow("Data16", "IFL_2020_fraction", "static nominal 2020", ifl_path.stat().st_size, "intact/non-intact strata", "2025 and loss bands were not read")

    arrays = {
        "human_modification": hm,
        "human_modification_support": hm_support,
        "human_modification_source_count": hm_count,
        "climate_zone": climate,
        "climate_zone_support": climate_support,
        "climate_zone_source_count": climate_count,
        "biomass": biomass,
        "biomass_support": biomass_support,
        "biomass_source_count": biomass_count,
        "soil_background": soil_bg,
        "soil_background_support": soil_bg_support,
        "soil_background_source_count": soil_bg_count,
        "topography": topo,
        "topography_support": topo_support,
        "topography_source_count": topo_count,
        "intact_forest": intact,
        "intact_forest_support": intact_support,
        "intact_forest_source_count": intact_count,
    }
    np.savez_compressed(WORK / "static_background.npz", **arrays)


def write_parquet(path: Path, columns: dict[str, Any], metadata: dict[str, str]) -> None:
    task4 = WORKBENCH / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics"
    sys.path.insert(0, str(task4))
    import task0004_lib as P
    P.RUN_ROOT = RUN
    P.OUTPUT_ROOT = DERIVED
    P.write_parquet(path, columns, metadata=metadata)
    check = P.validate_parquet(path)
    if not check["pass"]:
        raise RuntimeError(f"Parquet validation failed: {path}")


def write_partitioned_cubes(forest: dict[str, np.ndarray]) -> None:
    log("Writing global annual and static partitioned Parquet products")
    rows, cols = np.where(forest["30"])
    pixel_id = (rows.astype(np.int64) * WIDTH + cols).astype(np.int64)
    latitude = (84.75 - rows * 0.5).astype(np.float32)
    longitude = (-179.75 + cols * 0.5).astype(np.float32)
    annual_names = [
        "annual_forest_cover",
        "annual_forest_cover_support",
        "annual_forest_cover_source_count",
        "annual_forest_type",
        "annual_forest_type_support",
        "annual_forest_type_source_count",
        "annual_igbp_forest_fraction",
        "annual_gpp",
        "annual_npp",
        "annual_productivity_support",
        "annual_productivity_source_count",
    ]
    annual = {name: existing_mmap(name) for name in annual_names}
    root = DERIVED / "GLOBAL_ANNUAL_CUBE.parquet"
    for index, year in enumerate(YEARS):
        path = root / f"year={year}" / "part-000.parquet"
        columns = {
            "pixel_id": pixel_id,
            "grid_row": rows.astype(np.int32),
            "grid_col": cols.astype(np.int32),
            "latitude": latitude,
            "longitude": longitude,
            "year": np.full(len(rows), year, dtype=np.int32),
            "tree_cover_fraction": annual["annual_forest_cover"][index, rows, cols],
            "tree_cover_support": annual["annual_forest_cover_support"][index, rows, cols],
            "tree_cover_source_count": annual["annual_forest_cover_source_count"][index, rows, cols].astype(np.int32),
            "tree_cover_qc": (np.isfinite(annual["annual_forest_cover"][index, rows, cols]) & (annual["annual_forest_cover_support"][index, rows, cols] > 0)).astype(np.int32),
            "forest_type_igbp": annual["annual_forest_type"][index, rows, cols].astype(np.int32),
            "forest_type_support": annual["annual_forest_type_support"][index, rows, cols],
            "forest_type_source_count": annual["annual_forest_type_source_count"][index, rows, cols].astype(np.int32),
            "forest_type_qc": (annual["annual_forest_type"][index, rows, cols] >= 0).astype(np.int32),
            "igbp_forest_fraction": annual["annual_igbp_forest_fraction"][index, rows, cols],
            "gpp_kgC_m2_yr": annual["annual_gpp"][index, rows, cols],
            "npp_kgC_m2_yr": annual["annual_npp"][index, rows, cols],
            "productivity_support": annual["annual_productivity_support"][index, rows, cols],
            "productivity_source_count": annual["annual_productivity_source_count"][index, rows, cols].astype(np.int32),
            "productivity_qc": (
                np.isfinite(annual["annual_gpp"][index, rows, cols])
                & np.isfinite(annual["annual_npp"][index, rows, cols])
                & (annual["annual_productivity_support"][index, rows, cols] > 0)
            ).astype(np.int32),
        }
        write_parquet(path, columns, {"partition": str(year), "forest_domain": "Data03 mean >=0.30"})
    static = np.load(WORK / "static_background.npz")
    forest_type_mode = mode_over_years(annual["annual_forest_type"][:, rows, cols])
    static_columns = {
        "pixel_id": pixel_id,
        "grid_row": rows.astype(np.int32),
        "grid_col": cols.astype(np.int32),
        "latitude": latitude,
        "longitude": longitude,
        "cell_area_km2": cell_area_km2(latitude).astype(np.float32),
        "forest_cover_mean_2001_2020": forest["mean"][rows, cols],
        "forest_cover_valid_years": forest["valid_years"][rows, cols].astype(np.int32),
        "forest_mask_30": np.ones(len(rows), dtype=np.int32),
        "forest_mask_40": forest["40"][rows, cols].astype(np.int32),
        "forest_mask_50": forest["50"][rows, cols].astype(np.int32),
        "forest_type_igbp_mode_2001_2020": forest_type_mode.astype(np.int32),
    }
    for name in static.files:
        static_columns[name] = static[name][rows, cols]
    write_parquet(
        DERIVED / "GLOBAL_STATIC_BACKGROUND.parquet",
        static_columns,
        {
            "forest_domain": "Data03 mean >=0.30 and >=16 supported years",
            "categorical_aggregation": "weighted mode or fraction argmax; never arithmetic mean of codes",
        },
    )


def mode_over_years(values: np.ndarray) -> np.ndarray:
    result = np.full(values.shape[1], -1, dtype=np.int16)
    best_count = np.zeros(values.shape[1], dtype=np.int16)
    for code in range(17):
        count = np.sum(values == code, axis=0)
        update = count > best_count
        result[update] = code
        best_count[update] = count[update]
    return result


def zarr_dtype(dtype: np.dtype) -> str:
    value = np.dtype(dtype)
    if value.byteorder in ("=", "|") and value.kind in "iufc" and value.itemsize > 1:
        value = value.newbyteorder("<")
    return value.str


def write_zarr_array(store: Path, name: str, data: np.ndarray, dimensions: Sequence[str], chunks: Sequence[int], attrs: dict[str, Any], fill: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    array_dir = store / name
    array_dir.mkdir(parents=True, exist_ok=True)
    zarray = {
        "zarr_format": 2,
        "shape": list(data.shape),
        "chunks": list(chunks),
        "dtype": zarr_dtype(data.dtype),
        "compressor": {"id": "zlib", "level": 6},
        "fill_value": fill,
        "order": "C",
        "filters": None,
    }
    zattrs = {**attrs, "_ARRAY_DIMENSIONS": list(dimensions)}
    (array_dir / ".zarray").write_text(json.dumps(zarray, sort_keys=True), encoding="utf-8")
    (array_dir / ".zattrs").write_text(json.dumps(zattrs, sort_keys=True), encoding="utf-8")
    counts = [int(math.ceil(s / c)) for s, c in zip(data.shape, chunks)]
    native_fill = np.nan if fill == "NaN" else fill
    for index in itertools.product(*(range(n) for n in counts)):
        slices = tuple(
            slice(i * chunk, min((i + 1) * chunk, size))
            for i, chunk, size in zip(index, chunks, data.shape)
        )
        source = np.asarray(data[slices])
        block = np.full(tuple(chunks), native_fill, dtype=data.dtype)
        block[tuple(slice(0, n) for n in source.shape)] = source
        (array_dir / ".".join(map(str, index))).write_bytes(
            zlib.compress(block.tobytes(order="C"), level=6)
        )
    return zarray, zattrs


def write_monthly_zarr() -> None:
    log("Writing GLOBAL_MONTHLY_CUBE.zarr with value/support/source_count/QC arrays")
    store = DERIVED / "GLOBAL_MONTHLY_CUBE.zarr"
    store.mkdir(parents=True, exist_ok=True)
    (store / ".zgroup").write_text('{"zarr_format": 2}', encoding="utf-8")
    root_attrs = {
        "title": "TASK 0008B global monthly cube 2001-2020",
        "crs": "EPSG:4326",
        "resolution_degrees": 0.5,
        "holdout_excluded": "2021-2024",
        "gap_fill": False,
        "created_utc": utc_now(),
    }
    (store / ".zattrs").write_text(json.dumps(root_attrs, sort_keys=True), encoding="utf-8")
    metadata: dict[str, Any] = {".zgroup": {"zarr_format": 2}, ".zattrs": root_attrs}
    lat = (84.75 - np.arange(HEIGHT) * 0.5).astype(np.float64)
    lon = (-179.75 + np.arange(WIDTH) * 0.5).astype(np.float64)
    time = np.arange(240, dtype=np.int32)
    specs: list[tuple[str, np.ndarray, tuple[str, ...], tuple[int, ...], dict[str, Any], Any]] = [
        ("latitude", lat, ("latitude",), (290,), {"units": "degrees_north"}, "NaN"),
        ("longitude", lon, ("longitude",), (720,), {"units": "degrees_east"}, "NaN"),
        ("time", time, ("time",), (240,), {"units": "months since 2001-01-01", "calendar": "proleptic_gregorian"}, -1),
    ]
    dynamic = {
        "kndvi": ("monthly_kndvi", "1", "Data01 actual-date weighted monthly kNDVI"),
        "kndvi_support": ("monthly_kndvi_support", "fraction", "Data01 source support"),
        "kndvi_valid_area_fraction": ("monthly_kndvi_valid_area", "fraction", "Data01 usable valid area"),
        "kndvi_effective_weight_days": ("monthly_kndvi_effective_weight", "days*fraction", "Data01 effective temporal-area weight"),
        "kndvi_source_count": ("monthly_kndvi_source_count", "count", "contributing composites"),
        "vpd_kPa": ("monthly_vpd", "kPa", "Data14 monthly mean VPD"),
        "vpd_support": ("monthly_vpd_support", "fraction", "Data14 temporal valid fraction"),
        "vpd_source_count": ("monthly_vpd_source_count", "native_cells", "finite contributing native cells"),
        "soil_moisture_0_100_m3m3": ("monthly_soil_moisture", "m3 m-3", "Data15 0-100 cm root-zone mean"),
        "soil_moisture_support": ("monthly_soil_moisture_support", "fraction", "Data15 temporal valid fraction"),
        "soil_moisture_source_count": ("monthly_soil_moisture_source_count", "native_cells", "finite contributing native cells"),
    }
    for name, (cache, units, description) in dynamic.items():
        data = existing_mmap(cache)
        fill = "NaN" if np.issubdtype(data.dtype, np.floating) else -1
        specs.append((name, data, ("time", "latitude", "longitude"), (12, 29, 60), {"units": units, "description": description}, fill))
    k = existing_mmap("monthly_kndvi")
    kva = existing_mmap("monthly_kndvi_valid_area")
    kew = existing_mmap("monthly_kndvi_effective_weight")
    kc = existing_mmap("monthly_kndvi_source_count")
    v = existing_mmap("monthly_vpd")
    vs = existing_mmap("monthly_vpd_support")
    s = existing_mmap("monthly_soil_moisture")
    ss = existing_mmap("monthly_soil_moisture_support")
    qc_specs = {
        "kndvi_qc": (np.isfinite(k) & (kva >= 0.5) & (kew > 0) & (kc >= 1)).astype(np.uint8),
        "vpd_qc": (np.isfinite(v) & (vs > 0)).astype(np.uint8),
        "soil_moisture_qc": (np.isfinite(s) & (ss > 0)).astype(np.uint8),
    }
    for name, data in qc_specs.items():
        specs.append((name, data, ("time", "latitude", "longitude"), (12, 29, 60), {"units": "flag", "valid": 1}, 0))
    for name, data, dims, chunks, attrs, fill in specs:
        zarray, zattrs = write_zarr_array(store, name, data, dims, chunks, attrs, fill)
        metadata[f"{name}/.zarray"] = zarray
        metadata[f"{name}/.zattrs"] = zattrs
        log(f"Zarr array complete: {name}")
    (store / ".zmetadata").write_text(
        json.dumps({"zarr_consolidated_format": 1, "metadata": metadata}, sort_keys=True),
        encoding="utf-8",
    )


def write_monthly_qc(forest: dict[str, np.ndarray]) -> None:
    mask = forest["30"]
    arrays = {
        "kndvi": existing_mmap("monthly_kndvi"),
        "kndvi_support": existing_mmap("monthly_kndvi_support"),
        "kndvi_valid_area": existing_mmap("monthly_kndvi_valid_area"),
        "vpd": existing_mmap("monthly_vpd"),
        "vpd_support": existing_mmap("monthly_vpd_support"),
        "soil_moisture": existing_mmap("monthly_soil_moisture"),
        "soil_moisture_support": existing_mmap("monthly_soil_moisture_support"),
    }
    rows = []
    for index, month in enumerate(MONTHS):
        row: dict[str, Any] = {
            "month": month,
            "forest_cells": int(mask.sum()),
            "gap_fill_performed": False,
        }
        for name, data in arrays.items():
            values = data[index][mask]
            finite = np.isfinite(values)
            row[f"{name}_coverage"] = float(finite.mean())
            row[f"{name}_mean"] = float(np.nanmean(values)) if finite.any() else ""
        rows.append(row)
    fields = list(rows[0])
    write_csv(RUN / "GLOBAL_CUBE_MONTHLY_QC.csv", rows, fields)


def load_forest_cache() -> dict[str, np.ndarray]:
    return {
        "mean": np.load(WORK / "forest_cover_mean.npy"),
        "valid_years": np.load(WORK / "forest_cover_valid_years.npy"),
        "30": np.load(WORK / "forest_mask_30.npy"),
        "40": np.load(WORK / "forest_mask_40.npy"),
        "50": np.load(WORK / "forest_mask_50.npy"),
    }


def rebuild_early_manifest(manifest: list[dict[str, Any]]) -> None:
    d03 = data_dir("Data03")
    for year in YEARS:
        for path in sorted((d03 / str(year)).glob("MOD44B_native1km_g010_tile_*.tif")):
            manifest.append(input_record("Data03", path, str(year), "bands 1-2", "forest domain"))
    d01 = data_dir("Data01") / "0.5"
    for year in YEARS:
        path = next(d01.glob(f"*_g050_global_{year}_v07.tif"))
        manifest.append(input_record("Data01", path, str(year), "all dated kNDVI/support QA bands", "monthly state"))
    d04 = data_dir("Data04")
    for year in YEARS:
        path = next(d04.glob(f"*_g005_global_{year}_v01.tif"))
        manifest.append(input_record("Data04", path, str(year), "confidence and IGBP fractions c00-c16", "forest type/biome"))


def main() -> None:
    parser = argparse.ArgumentParser()
    stages = ["forest", "kndvi", "landcover", "hydroclimate", "productivity", "static", "outputs"]
    parser.add_argument("--start", choices=stages, default="forest")
    args = parser.parse_args()
    start_index = stages.index(args.start)
    RUN.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    resume = start_index > 0
    if not resume:
        (RUN / "COMMAND_LOG.txt").write_text("", encoding="utf-8")
    logger = HoldoutLog(resume=resume)
    if not resume:
        logger.self_test()
    manifest: list[dict[str, Any]] = []
    if start_index <= stages.index("forest"):
        forest = build_forest_domain(logger, manifest)
    else:
        forest = load_forest_cache()
        rebuild_early_manifest(manifest)
    if start_index <= stages.index("kndvi"):
        build_kndvi(logger, manifest)
    if start_index <= stages.index("landcover"):
        build_landcover(logger, manifest)
    if start_index <= stages.index("hydroclimate"):
        build_hydroclimate(logger, manifest)
    if start_index <= stages.index("productivity"):
        build_productivity(logger, manifest)
    if start_index <= stages.index("static"):
        build_static(logger, manifest)
    if start_index <= stages.index("outputs"):
        write_partitioned_cubes(forest)
        write_monthly_qc(forest)
        write_monthly_zarr()
    manifest_fields = [
        "dataset",
        "input_path",
        "period_selected",
        "bands_selected",
        "scientific_role",
        "size_bytes",
        "mtime_utc",
        "checksum_policy",
        "read_only",
    ]
    deduplicated = {
        (
            row["dataset"],
            row["input_path"],
            row["period_selected"],
            row["bands_selected"],
        ): row
        for row in manifest
    }
    manifest = [deduplicated[key] for key in sorted(deduplicated)]
    write_csv(RUN / "INPUT_MANIFEST.csv", manifest, manifest_fields)
    state = {
        "status": "COMPLETE",
        "completed_utc": utc_now(),
        "forest30_cells": int(forest["30"].sum()),
        "forest40_cells": int(forest["40"].sum()),
        "forest50_cells": int(forest["50"].sum()),
        "manifest_rows": len(manifest),
        "holdout_scientific_bytes_read": 0,
        "monthly_cube": str(DERIVED / "GLOBAL_MONTHLY_CUBE.zarr"),
    }
    (RUN / "GLOBAL_BUILD_STATE.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log("Global inputs build complete")


if __name__ == "__main__":
    main()
