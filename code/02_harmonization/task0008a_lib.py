from __future__ import annotations

import csv
import importlib.util
import itertools
import json
import math
import re
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Sequence

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy import stats


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW = ROOT / "000 GEE Data"
WORKBENCH = ROOT / "010_Research_Workbench"
RUN = WORKBENCH / "02_Runs" / "RUN_0008A_FAST_PAPER_Input_Freeze_and_Pilot"
DERIVED = WORKBENCH / "04_Standardized_Data" / "FastPaper_Greening_Resilience_Pilot_v01"
CUBE = WORKBENCH / "04_Standardized_Data" / "Monthly_Core_Cube_v01"
TASK4 = WORKBENCH / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics"
REGIONS = {
    "amazon": (-75.0, -15.0, -50.0, 5.0),
    "temperate_europe": (-5.0, 40.0, 25.0, 55.0),
    "boreal_canada": (-130.0, 50.0, -90.0, 70.0),
}
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
HOLDOUT_START_MONTH = 240
HOLDOUT_START_YEAR_INDEX = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir(label: str) -> Path:
    prefix = DATA_PREFIX[label]
    return next(path for path in RAW.iterdir() if path.is_dir() and path.name.startswith(prefix))


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class HoldoutLogger:
    fields = [
        "event_id", "timestamp_utc", "stage", "region", "variable",
        "access_type", "requested_start_index", "requested_end_exclusive",
        "requested_period", "holdout_overlap_requested",
        "scientific_array_read", "scientific_bytes_read",
        "holdout_scientific_bytes_read", "decision", "purpose", "notes",
    ]

    def __init__(self) -> None:
        self.path = RUN / "HOLDOUT_ACCESS_LOG.csv"
        write_csv(self.path, [], self.fields)
        self.counter = 0

    def log(self, **kwargs: Any) -> None:
        self.counter += 1
        row = {
            "event_id": self.counter,
            "timestamp_utc": utc_now(),
            "stage": "TASK0008A",
            "region": "",
            "variable": "",
            "access_type": "",
            "requested_start_index": "",
            "requested_end_exclusive": "",
            "requested_period": "",
            "holdout_overlap_requested": False,
            "scientific_array_read": False,
            "scientific_bytes_read": 0,
            "holdout_scientific_bytes_read": 0,
            "decision": "",
            "purpose": "",
            "notes": "",
            **kwargs,
        }
        with self.path.open("a", encoding="utf-8-sig", newline="") as handle:
            csv.DictWriter(handle, fieldnames=self.fields).writerow(row)


def _decode_fill(dtype: np.dtype, fill: Any) -> Any:
    if fill == "NaN":
        return np.nan
    if np.issubdtype(dtype, np.unsignedinteger) and isinstance(fill, int) and fill < 0:
        return fill % (1 << (dtype.itemsize * 8))
    return fill


class ProtectedCubeReader:
    def __init__(self, region: str, logger: HoldoutLogger) -> None:
        self.region = region
        self.logger = logger
        self.store = CUBE / f"{region}_monthly_core_cube_v01.zarr"
        self.metadata = json.loads((self.store / ".zmetadata").read_text(encoding="utf-8"))["metadata"]
        self.logger.log(
            region=region,
            variable="ALL",
            access_type="consolidated_metadata",
            decision="ALLOWED_METADATA_ONLY",
            purpose="verify cube schema without scientific holdout access",
        )

    def _meta(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.metadata[f"{name}/.zarray"], self.metadata[f"{name}/.zattrs"]

    def _read(self, name: str, leading_stop: int | None = None) -> np.ndarray:
        zarray, _ = self._meta(name)
        shape = tuple(int(x) for x in zarray["shape"])
        chunks = tuple(int(x) for x in zarray["chunks"])
        dtype = np.dtype(zarray["dtype"])
        out_shape = shape if leading_stop is None else (leading_stop, *shape[1:])
        result = np.full(out_shape, _decode_fill(dtype, zarray["fill_value"]), dtype=dtype)
        counts = [int(math.ceil(s / c)) for s, c in zip(shape, chunks)]
        if leading_stop is not None:
            counts[0] = int(math.ceil(leading_stop / chunks[0]))
        for index in itertools.product(*(range(x) for x in counts)):
            chunk_path = self.store / name / ".".join(map(str, index))
            if not chunk_path.exists():
                continue
            block = np.frombuffer(zlib.decompress(chunk_path.read_bytes()), dtype=dtype).reshape(chunks)
            target = []
            edge = []
            for axis, (i, chunk, size) in enumerate(zip(index, chunks, out_shape)):
                start = i * chunk
                stop = min((i + 1) * chunk, size)
                if start >= size:
                    break
                target.append(slice(start, stop))
                edge.append(slice(0, stop - start))
            else:
                result[tuple(target)] = block[tuple(edge)]
        return result

    def read_coordinate(self, name: str) -> np.ndarray:
        result = self._read(name)
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="coordinate",
            decision="ALLOWED_NON_SCIENTIFIC_COORDINATE",
            purpose="grid alignment check",
            scientific_bytes_read=0,
        )
        return result

    def read_monthly(self, name: str, stop: int, purpose: str) -> np.ndarray:
        if stop > HOLDOUT_START_MONTH:
            self.logger.log(
                region=self.region,
                variable=name,
                access_type="monthly_scientific",
                requested_start_index=0,
                requested_end_exclusive=stop,
                requested_period=f"2001-01 through index {stop - 1}",
                holdout_overlap_requested=True,
                scientific_array_read=False,
                decision="DENIED_BEFORE_IO",
                purpose=purpose,
                notes="firewall blocks monthly index >=240",
            )
            raise RuntimeError("Holdout firewall")
        result = self._read(name, stop)
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="monthly_scientific",
            requested_start_index=0,
            requested_end_exclusive=stop,
            requested_period="2001-01..2020-12",
            holdout_overlap_requested=False,
            scientific_array_read=True,
            scientific_bytes_read=result.nbytes,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_PRIMARY_PERIOD",
            purpose=purpose,
            notes="only chunks with leading time index <240 were opened",
        )
        return result

    def read_annual(self, name: str, stop: int, purpose: str) -> np.ndarray:
        if stop > HOLDOUT_START_YEAR_INDEX:
            self.logger.log(
                region=self.region,
                variable=name,
                access_type="annual_scientific",
                requested_start_index=0,
                requested_end_exclusive=stop,
                requested_period=f"2001 through year index {stop - 1}",
                holdout_overlap_requested=True,
                scientific_array_read=False,
                decision="DENIED_BEFORE_IO",
                purpose=purpose,
                notes="firewall blocks annual index >=20",
            )
            raise RuntimeError("Holdout firewall")
        result = self._read(name, stop)
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="annual_scientific",
            requested_start_index=0,
            requested_end_exclusive=stop,
            requested_period="2001..2020",
            holdout_overlap_requested=False,
            scientific_array_read=True,
            scientific_bytes_read=result.nbytes,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_PRIMARY_PERIOD",
            purpose=purpose,
            notes="only annual chunks with year index <20 were opened",
        )
        return result

    def read_static(self, name: str, purpose: str) -> np.ndarray:
        result = self._read(name)
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="static_scientific",
            requested_period="static",
            scientific_array_read=True,
            scientific_bytes_read=result.nbytes,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_STATIC",
            purpose=purpose,
        )
        return result

    def firewall_self_test(self) -> None:
        try:
            self.read_monthly("kndvi", 241, "firewall self-test; no IO expected")
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Monthly firewall self-test failed")


def target_geometry(bounds: tuple[float, float, float, float]) -> tuple[int, int, Any, np.ndarray, np.ndarray]:
    west, south, east, north = bounds
    width = int(round((east - west) / 0.5))
    height = int(round((north - south) / 0.5))
    transform = from_origin(west, north, 0.5, 0.5)
    lon = west + 0.25 + np.arange(width) * 0.5
    lat = north - 0.25 - np.arange(height) * 0.5
    return height, width, transform, lat, lon


_TILE_RE = re.compile(
    r"_(E|W)(\d{3})_(E|W)(\d{3})_(N|S)(\d{2})_(N|S)(\d{2})_"
)


def _coord(hemi: str, number: str) -> float:
    value = float(number)
    return -value if hemi in ("W", "S") else value


def nominal_tile_bounds(path: Path) -> tuple[float, float, float, float]:
    match = _TILE_RE.search(path.name)
    if not match:
        raise RuntimeError(f"Cannot parse nominal tile bounds: {path.name}")
    x1 = _coord(match.group(1), match.group(2))
    x2 = _coord(match.group(3), match.group(4))
    y1 = _coord(match.group(5), match.group(6))
    y2 = _coord(match.group(7), match.group(8))
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def select_tiles(paths: Sequence[Path], bounds: tuple[float, float, float, float]) -> list[Path]:
    selected = []
    for path in paths:
        try:
            tile = nominal_tile_bounds(path)
        except RuntimeError:
            continue
        if intersects(tile, bounds):
            selected.append(path)
    return sorted(selected)


def aggregate_support_weighted_tiles(
    paths: Sequence[Path],
    bounds: tuple[float, float, float, float],
    value_band: int,
    support_band: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width, transform, lat, lon = target_geometry(bounds)
    value_out = np.full((height, width), np.nan, dtype=np.float32)
    support_out = np.full((height, width), np.nan, dtype=np.float32)
    count_out = np.zeros((height, width), dtype=np.int32)
    yy, xx = np.meshgrid(lat, lon, indexing="ij")
    for path in select_tiles(paths, bounds):
        tile_bounds = nominal_tile_bounds(path)
        with rasterio.open(path) as src:
            value = src.read(value_band, masked=True).filled(np.nan).astype(np.float32)
            support = src.read(support_band, masked=True).filled(np.nan).astype(np.float32)
            valid = np.isfinite(value) & np.isfinite(support) & (support > 0)
            numerator = np.where(valid, value * support, np.nan).astype(np.float32)
            denominator = np.where(valid, support, np.nan).astype(np.float32)
            binary = valid.astype(np.float32)
            dst_num = np.full((height, width), np.nan, dtype=np.float32)
            dst_den = np.full((height, width), np.nan, dtype=np.float32)
            dst_count = np.zeros((height, width), dtype=np.float32)
            common = dict(
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                dst_nodata=np.nan,
                resampling=Resampling.average,
            )
            reproject(numerator, dst_num, src_nodata=np.nan, **common)
            reproject(denominator, dst_den, src_nodata=np.nan, **common)
            reproject(binary, dst_count, src_nodata=0, **common)
        nominal = (
            (xx >= tile_bounds[0]) & (xx < tile_bounds[2])
            & (yy >= tile_bounds[1]) & (yy < tile_bounds[3])
        )
        ok = nominal & np.isfinite(dst_num) & np.isfinite(dst_den) & (dst_den > 0)
        value_out[ok] = dst_num[ok] / dst_den[ok]
        support_out[ok] = dst_den[ok]
        # source_count is the count of contributing canonical rasters, not an
        # invented estimate of native pixels within a 0.5-degree cell.
        count_out[ok] = 1
    return value_out, support_out, count_out


def _aligned_window(src: rasterio.io.DatasetReader, bounds: tuple[float, float, float, float]) -> Any:
    window = rasterio.windows.from_bounds(*bounds, transform=src.transform)
    return window.round_offsets().round_lengths()


def aggregate_global_weighted(
    path: Path,
    bounds: tuple[float, float, float, float],
    value_band: int,
    support_band: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width, _, _, _ = target_geometry(bounds)
    with rasterio.open(path) as src:
        window = _aligned_window(src, bounds)
        value = src.read(value_band, window=window, masked=True).filled(np.nan).astype(float)
        support = src.read(support_band, window=window, masked=True).filled(np.nan).astype(float)
    fy = value.shape[0] // height
    fx = value.shape[1] // width
    if fy != 10 or fx != 10 or value.shape != (height * fy, width * fx):
        raise RuntimeError(f"Expected exact 0.05 to 0.5 alignment: {path.name} {value.shape}")
    value4 = value.reshape(height, fy, width, fx)
    support4 = support.reshape(height, fy, width, fx)
    valid = np.isfinite(value4) & np.isfinite(support4) & (support4 > 0)
    denominator = np.sum(np.where(valid, support4, 0.0), axis=(1, 3))
    numerator = np.sum(np.where(valid, value4 * support4, 0.0), axis=(1, 3))
    out = np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)
    support_out = denominator / (fy * fx)
    count = np.sum(valid, axis=(1, 3)).astype(np.int32)
    return out.astype(np.float32), support_out.astype(np.float32), count


def aggregate_global_mean(
    path: Path,
    bounds: tuple[float, float, float, float],
    value_band: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width, _, _, _ = target_geometry(bounds)
    with rasterio.open(path) as src:
        window = _aligned_window(src, bounds)
        value = src.read(value_band, window=window, masked=True).filled(np.nan).astype(float)
    fy = value.shape[0] // height
    fx = value.shape[1] // width
    if fy != 10 or fx != 10:
        raise RuntimeError(f"Expected exact 0.05 to 0.5 alignment: {path.name}")
    value4 = value.reshape(height, fy, width, fx)
    valid = np.isfinite(value4)
    count = np.sum(valid, axis=(1, 3)).astype(np.int32)
    out = np.nanmean(value4, axis=(1, 3))
    support = count.astype(float) / (fy * fx)
    out[count == 0] = np.nan
    return out.astype(np.float32), support.astype(np.float32), count


def aggregate_global_mode(
    path: Path,
    bounds: tuple[float, float, float, float],
    value_band: int,
    support_band: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width, _, _, _ = target_geometry(bounds)
    with rasterio.open(path) as src:
        window = _aligned_window(src, bounds)
        value = src.read(value_band, window=window, masked=True).filled(np.nan).astype(float)
        support = src.read(support_band, window=window, masked=True).filled(np.nan).astype(float)
    fy, fx = value.shape[0] // height, value.shape[1] // width
    value4 = value.reshape(height, fy, width, fx)
    support4 = support.reshape(height, fy, width, fx)
    out = np.full((height, width), -1, dtype=np.int16)
    support_out = np.zeros((height, width), dtype=np.float32)
    count = np.zeros((height, width), dtype=np.int32)
    for r in range(height):
        for c in range(width):
            values = value4[r, :, c, :].ravel()
            weights = support4[r, :, c, :].ravel()
            valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
            if not np.any(valid):
                continue
            codes = values[valid].astype(int)
            unique = np.unique(codes)
            totals = np.array([weights[valid][codes == code].sum() for code in unique])
            out[r, c] = int(unique[np.argmax(totals)])
            support_out[r, c] = float(weights[valid].sum() / (fy * fx))
            count[r, c] = int(valid.sum())
    return out, support_out, count


def ols_trend(values: np.ndarray, x: np.ndarray, minimum: int) -> tuple[float, float, float, int]:
    valid = np.isfinite(values) & np.isfinite(x)
    n = int(valid.sum())
    if n < minimum:
        return np.nan, np.nan, np.nan, n
    result = stats.linregress(x[valid], values[valid])
    return float(result.slope), float(result.pvalue), float(result.stderr), n


def theil_sen(values: np.ndarray, x: np.ndarray, minimum: int) -> tuple[float, int]:
    valid = np.isfinite(values) & np.isfinite(x)
    n = int(valid.sum())
    if n < minimum:
        return np.nan, n
    return float(stats.theilslopes(values[valid], x[valid]).slope), n


def mann_kendall(values: np.ndarray, x: np.ndarray, minimum: int) -> tuple[float, float, int]:
    valid = np.isfinite(values) & np.isfinite(x)
    n = int(valid.sum())
    if n < minimum:
        return np.nan, np.nan, n
    result = stats.kendalltau(x[valid], values[valid], nan_policy="omit")
    return float(result.statistic), float(result.pvalue), n


def lag_correlation(values: np.ndarray, lag: int, minimum_pairs: int = 60) -> tuple[float, int]:
    a = values[:-lag]
    b = values[lag:]
    valid = np.isfinite(a) & np.isfinite(b)
    n = int(valid.sum())
    if n < minimum_pairs:
        return np.nan, n
    return float(np.corrcoef(a[valid], b[valid])[0, 1]), n


def mode_int(values: np.ndarray, invalid: int = -1) -> int:
    valid = values[np.isfinite(values) & (values >= 0)].astype(int)
    if valid.size == 0:
        return invalid
    counts = np.bincount(valid)
    return int(np.flatnonzero(counts == counts.max())[0])


def read_task4_table(name: str, fields: Sequence[str], kinds: dict[str, str], expected_rows: int) -> dict[str, np.ndarray]:
    module_path = (
        WORKBENCH / "02_Runs" / "RUN_0007_TAC_Fidelity_StateSpace_Pilot" / "task0007_lib.py"
    )
    spec = importlib.util.spec_from_file_location("task0007_read_only_parquet", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load prior primitive Parquet reader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_primitive_parquet(TASK4 / name, fields, kinds, expected_rows)


def write_parquet_columns(path: Path, columns: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
    module_path = TASK4 / "task0004_lib.py"
    spec = importlib.util.spec_from_file_location("task0004_write_only_parquet", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load prior primitive Parquet writer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RUN_ROOT = RUN
    module.OUTPUT_ROOT = DERIVED
    module.write_parquet(path, columns, metadata=metadata)
    result = module.validate_parquet(path)
    if not result["pass"]:
        raise RuntimeError(f"Parquet envelope validation failed: {path}")
    return result
