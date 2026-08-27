from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import struct
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import os
from typing import Any, Iterable, Sequence

import numpy as np
from scipy import stats


PROJECT_ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW_ROOT = PROJECT_ROOT / "000 GEE Data"
RUN_ROOT = (
    PROJECT_ROOT
    / "010_Research_Workbench"
    / "02_Runs"
    / "RUN_0004_Three_Region_Benchmark_Dynamics"
)
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "010_Research_Workbench"
    / "04_Standardized_Data"
    / "Benchmark_Dynamics_v01"
)
CUBE_ROOT = (
    PROJECT_ROOT
    / "010_Research_Workbench"
    / "04_Standardized_Data"
    / "Monthly_Core_Cube_v01"
)
TASK2_RUN = (
    PROJECT_ROOT
    / "010_Research_Workbench"
    / "02_Runs"
    / "RUN_0002_Three_Region_Monthly_Core_Cube"
)

REGIONS = {
    "amazon": (-75.0, -15.0, -50.0, 5.0),
    "temperate_europe": (-5.0, 40.0, 25.0, 55.0),
    "boreal_canada": (-130.0, 50.0, -90.0, 70.0),
}
MONTHS_2001_2020 = [
    f"{year:04d}-{month:02d}"
    for year in range(2001, 2021)
    for month in range(1, 13)
]
TRAIN_END = 192
SCIENCE_END = 240
HOLDOUT_START = 240
TOTAL_MONTHS = 288


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_safe_output(path: Path) -> None:
    resolved = path.resolve()
    forbidden = [RAW_ROOT.resolve(), CUBE_ROOT.resolve(), TASK2_RUN.resolve()]
    if any(resolved == root or root in resolved.parents for root in forbidden):
        raise RuntimeError(f"Refusing to write inside read-only input: {resolved}")
    allowed = [RUN_ROOT.resolve(), OUTPUT_ROOT.resolve()]
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise RuntimeError(f"Output outside TASK0004 roots: {resolved}")


def ensure_dir(path: Path) -> None:
    assert_safe_output(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    assert_safe_output(path)
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8", newline="\n")


def append_log(message: str) -> None:
    path = RUN_ROOT / "COMMAND_LOG.txt"
    assert_safe_output(path)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"[{utc_now()}] {message}\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> None:
    assert_safe_output(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class HoldoutViolation(RuntimeError):
    pass


class HoldoutLogger:
    fields = [
        "event_id",
        "timestamp_utc",
        "stage",
        "region",
        "variable",
        "access_type",
        "requested_start_index",
        "requested_end_exclusive",
        "requested_period",
        "holdout_overlap_requested",
        "scientific_array_read",
        "holdout_scientific_bytes_read",
        "decision",
        "purpose",
        "max_time_chunk_read",
        "notes",
    ]

    def __init__(self, stage: str, reset: bool = False) -> None:
        self.stage = stage
        self.path = RUN_ROOT / "HOLDOUT_ACCESS_LOG.csv"
        ensure_dir(self.path.parent)
        if reset or not self.path.exists():
            write_csv(self.path, [], self.fields)

    def log(self, **kwargs: Any) -> None:
        existing = 0
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = max(sum(1 for _ in handle) - 1, 0)
        row = {
            "event_id": existing + 1,
            "timestamp_utc": utc_now(),
            "stage": self.stage,
            "region": "",
            "variable": "",
            "access_type": "",
            "requested_start_index": "",
            "requested_end_exclusive": "",
            "requested_period": "",
            "holdout_overlap_requested": False,
            "scientific_array_read": False,
            "holdout_scientific_bytes_read": 0,
            "decision": "",
            "purpose": "",
            "max_time_chunk_read": "",
            "notes": "",
            **kwargs,
        }
        with self.path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields, extrasaction="ignore")
            writer.writerow(row)


def _decode_fill(dtype: np.dtype, fill: Any) -> Any:
    if fill == "NaN":
        return np.nan
    if np.issubdtype(dtype, np.unsignedinteger) and isinstance(fill, int) and fill < 0:
        return fill % (1 << (dtype.itemsize * 8))
    return fill


class ProtectedZarrReader:
    def __init__(self, region: str, logger: HoldoutLogger) -> None:
        self.region = region
        self.store = CUBE_ROOT / f"{region}_monthly_core_cube_v01.zarr"
        if not self.store.is_dir():
            raise RuntimeError(f"Missing TASK0002 cube: {self.store}")
        self.logger = logger
        self.metadata = json.loads(
            (self.store / ".zmetadata").read_text(encoding="utf-8")
        )["metadata"]
        self.logger.log(
            region=region,
            variable="ALL",
            access_type="consolidated_metadata",
            decision="ALLOWED_METADATA_ONLY",
            purpose="verify shapes, chunks, dimensions and 288 timestamp metadata",
            notes=".zmetadata contains no decoded scientific array values",
        )

    def _array_meta(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            return (
                self.metadata[f"{name}/.zarray"],
                self.metadata[f"{name}/.zattrs"],
            )
        except KeyError as exc:
            raise RuntimeError(f"Missing Zarr variable {name} in {self.store}") from exc

    def _read_full_array_unlogged(self, name: str) -> np.ndarray:
        zarray, _ = self._array_meta(name)
        shape = tuple(int(value) for value in zarray["shape"])
        chunks = tuple(int(value) for value in zarray["chunks"])
        dtype = np.dtype(zarray["dtype"])
        fill = _decode_fill(dtype, zarray["fill_value"])
        output = np.full(shape, fill, dtype=dtype)
        counts = [int(math.ceil(size / chunk)) for size, chunk in zip(shape, chunks)]
        for index in itertools.product(*(range(count) for count in counts)):
            chunk_path = self.store / name / ".".join(str(value) for value in index)
            if not chunk_path.exists():
                continue
            decoded = np.frombuffer(zlib.decompress(chunk_path.read_bytes()), dtype=dtype)
            block = decoded.reshape(chunks, order="C")
            target_slices = tuple(
                slice(i * chunk, min((i + 1) * chunk, size))
                for i, chunk, size in zip(index, chunks, shape)
            )
            edge = tuple(slice(0, sl.stop - sl.start) for sl in target_slices)
            output[target_slices] = block[edge]
        return output

    def verify_time_axis(self) -> None:
        zarray, _ = self._array_meta("time")
        if tuple(zarray["shape"]) != (TOTAL_MONTHS,):
            raise RuntimeError(f"Unexpected time shape in {self.region}: {zarray['shape']}")
        time_values = self._read_full_array_unlogged("time")
        expected = np.array(
            [
                (
                    date(year, month, 1) - date(1970, 1, 1)
                ).days
                for year in range(2001, 2025)
                for month in range(1, 13)
            ],
            dtype=np.int32,
        )
        if not np.array_equal(time_values, expected):
            raise RuntimeError(f"Time coordinate mismatch in {self.region}")
        self.logger.log(
            region=self.region,
            variable="time",
            access_type="coordinate_integrity_check",
            requested_start_index=0,
            requested_end_exclusive=288,
            requested_period="2001-01..2024-12",
            holdout_overlap_requested=True,
            scientific_array_read=False,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_NON_SCIENTIFIC_COORDINATE",
            purpose="verify exactly 48 locked holdout timestamps exist",
            max_time_chunk_read="coordinate_only",
            notes="time coordinate was not passed to preprocessing/model/plot functions",
        )

    def deny_holdout_probe(self, variable: str) -> None:
        try:
            self.read_scientific(variable, HOLDOUT_START, TOTAL_MONTHS, "unit-test denial")
        except HoldoutViolation:
            return
        raise RuntimeError("Holdout denial probe unexpectedly succeeded")

    def read_static(self, name: str, purpose: str) -> np.ndarray:
        zarray, attrs = self._array_meta(name)
        dimensions = attrs.get("_ARRAY_DIMENSIONS", [])
        if "time" in dimensions:
            raise RuntimeError(f"{name} is temporal; use read_scientific")
        result = self._read_full_array_unlogged(name)
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="static_array",
            scientific_array_read=True,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_STATIC_NO_TIME_DIMENSION",
            purpose=purpose,
            notes=f"dimensions={dimensions};shape={zarray['shape']}",
        )
        return result

    def read_scientific(
        self, name: str, start: int = 0, stop: int = SCIENCE_END, purpose: str = ""
    ) -> np.ndarray:
        overlap = stop > HOLDOUT_START
        if start < 0 or stop <= start or stop > TOTAL_MONTHS:
            raise ValueError(f"Invalid time slice {start}:{stop}")
        if overlap:
            self.logger.log(
                region=self.region,
                variable=name,
                access_type="scientific_array",
                requested_start_index=start,
                requested_end_exclusive=stop,
                requested_period=f"index {start}:{stop}",
                holdout_overlap_requested=True,
                scientific_array_read=False,
                holdout_scientific_bytes_read=0,
                decision="DENIED_BEFORE_IO",
                purpose=purpose,
                notes="ProtectedZarrReader blocks time index >=240",
            )
            raise HoldoutViolation(f"Scientific holdout read denied: {name}[{start}:{stop}]")
        zarray, attrs = self._array_meta(name)
        dimensions = attrs.get("_ARRAY_DIMENSIONS", [])
        if not dimensions or dimensions[0] != "time":
            raise RuntimeError(f"{name} does not have leading time dimension: {dimensions}")
        shape = tuple(int(value) for value in zarray["shape"])
        chunks = tuple(int(value) for value in zarray["chunks"])
        if shape[0] != TOTAL_MONTHS:
            raise RuntimeError(f"{name} time length is not 288: {shape}")
        dtype = np.dtype(zarray["dtype"])
        fill = _decode_fill(dtype, zarray["fill_value"])
        output_shape = (stop - start, *shape[1:])
        output = np.full(output_shape, fill, dtype=dtype)
        first_chunk = start // chunks[0]
        last_chunk = (stop - 1) // chunks[0]
        if last_chunk >= HOLDOUT_START // chunks[0]:
            raise HoldoutViolation("Internal time-chunk firewall triggered")
        spatial_counts = [
            int(math.ceil(size / chunk)) for size, chunk in zip(shape[1:], chunks[1:])
        ]
        for time_chunk in range(first_chunk, last_chunk + 1):
            for spatial_index in itertools.product(
                *(range(count) for count in spatial_counts)
            ):
                index = (time_chunk, *spatial_index)
                chunk_path = self.store / name / ".".join(
                    str(value) for value in index
                )
                if not chunk_path.exists():
                    continue
                decoded = np.frombuffer(
                    zlib.decompress(chunk_path.read_bytes()), dtype=dtype
                ).reshape(chunks, order="C")
                source_start = max(start, time_chunk * chunks[0])
                source_stop = min(stop, (time_chunk + 1) * chunks[0])
                target_time = slice(source_start - start, source_stop - start)
                source_time = slice(
                    source_start - time_chunk * chunks[0],
                    source_stop - time_chunk * chunks[0],
                )
                target_spatial = []
                source_spatial = []
                for dim_index, (sp_index, chunk, size) in enumerate(
                    zip(spatial_index, chunks[1:], shape[1:])
                ):
                    left = sp_index * chunk
                    right = min(left + chunk, size)
                    target_spatial.append(slice(left, right))
                    source_spatial.append(slice(0, right - left))
                output[(target_time, *target_spatial)] = decoded[
                    (source_time, *source_spatial)
                ]
        self.logger.log(
            region=self.region,
            variable=name,
            access_type="scientific_array",
            requested_start_index=start,
            requested_end_exclusive=stop,
            requested_period=f"{MONTHS_2001_2020[start]}..{MONTHS_2001_2020[stop-1]}",
            holdout_overlap_requested=False,
            scientific_array_read=True,
            holdout_scientific_bytes_read=0,
            decision="ALLOWED_PRE_HOLDOUT_ONLY",
            purpose=purpose,
            max_time_chunk_read=last_chunk,
            notes=f"decoded time chunks {first_chunk}..{last_chunk}; holdout starts at chunk 20",
        )
        return output


def grid_coordinates(region: str) -> tuple[np.ndarray, np.ndarray]:
    lon_min, lat_min, lon_max, lat_max = REGIONS[region]
    lon = np.arange(lon_min + 0.25, lon_max, 0.5, dtype=np.float64)
    lat = np.arange(lat_max - 0.25, lat_min, -0.5, dtype=np.float64)
    return lat, lon


def ac1(series: np.ndarray, min_pairs: int = 3) -> tuple[float, int]:
    values = np.asarray(series, dtype=np.float64)
    valid = np.isfinite(values[:-1]) & np.isfinite(values[1:])
    n = int(valid.sum())
    if n < min_pairs:
        return math.nan, n
    left = values[:-1][valid]
    right = values[1:][valid]
    if np.std(left) <= 0 or np.std(right) <= 0:
        return math.nan, n
    return float(np.corrcoef(left, right)[0, 1]), n


def fisher_interval(r: float, n: int) -> tuple[float, float, float]:
    if not math.isfinite(r) or n <= 3 or abs(r) >= 1:
        return math.nan, math.nan, math.nan
    se = 1.0 / math.sqrt(n - 3)
    z = np.arctanh(r)
    return se, float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))


def ols_fit(
    X: np.ndarray, y: np.ndarray, hac_lags: int = 3
) -> dict[str, Any]:
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xv = X[valid]
    yv = y[valid]
    n, k = Xv.shape if Xv.ndim == 2 else (0, 0)
    if n <= k + 2:
        return {"valid": False, "n": n}
    beta, _, rank, _ = np.linalg.lstsq(Xv, yv, rcond=None)
    if rank < k:
        return {"valid": False, "n": n}
    fitted = Xv @ beta
    residual = yv - fitted
    xtx_inv = np.linalg.pinv(Xv.T @ Xv)
    meat = np.zeros((k, k), dtype=np.float64)
    for t in range(n):
        score = Xv[t] * residual[t]
        meat += np.outer(score, score)
    for lag in range(1, min(hac_lags, n - 1) + 1):
        weight = 1.0 - lag / (hac_lags + 1.0)
        cross = np.zeros((k, k), dtype=np.float64)
        for t in range(lag, n):
            cross += np.outer(
                Xv[t] * residual[t], Xv[t - lag] * residual[t - lag]
            )
        meat += weight * (cross + cross.T)
    covariance = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    tvalues = np.divide(
        beta, se, out=np.full_like(beta, np.nan), where=se > 0
    )
    pvalues = 2.0 * stats.t.sf(np.abs(tvalues), df=max(n - k, 1))
    return {
        "valid": True,
        "n": n,
        "beta": beta,
        "se": se,
        "pvalue": pvalues,
        "fitted": fitted,
        "residual": residual,
        "valid_rows": valid,
        "condition_number": float(np.linalg.cond(Xv)),
        "xtx_inv": xtx_inv,
    }


def max_vif(X_without_intercept: np.ndarray) -> tuple[float, list[float]]:
    X = np.asarray(X_without_intercept, dtype=np.float64)
    valid = np.all(np.isfinite(X), axis=1)
    X = X[valid]
    if X.shape[0] <= X.shape[1] + 2:
        return math.nan, [math.nan] * X.shape[1]
    values: list[float] = []
    for index in range(X.shape[1]):
        y = X[:, index]
        others = np.delete(X, index, axis=1)
        design = np.column_stack([np.ones(len(y)), others])
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        residual = y - design @ beta
        total = np.sum((y - np.mean(y)) ** 2)
        r2 = 1.0 - np.sum(residual**2) / total if total > 0 else 1.0
        values.append(float(1.0 / max(1.0 - r2, 1e-12)))
    return max(values), values


def residual_diagnostics(
    residual: np.ndarray, fitted: np.ndarray, X: np.ndarray, ljung_lag: int = 12
) -> dict[str, float]:
    residual = np.asarray(residual, dtype=np.float64)
    n = len(residual)
    residual_ac, _ = ac1(residual)
    q = 0.0
    used = 0
    for lag in range(1, min(ljung_lag, n - 2) + 1):
        r, pairs = ac1_at_lag(residual, lag)
        if math.isfinite(r):
            q += r * r / max(n - lag, 1)
            used += 1
    q *= n * (n + 2)
    q_p = float(stats.chi2.sf(q, df=max(used, 1))) if used else math.nan
    bp_design = np.column_stack([np.ones(n), fitted])
    bp_beta = np.linalg.lstsq(bp_design, residual**2, rcond=None)[0]
    bp_fit = bp_design @ bp_beta
    total = np.sum((residual**2 - np.mean(residual**2)) ** 2)
    r2 = 1.0 - np.sum((residual**2 - bp_fit) ** 2) / total if total > 0 else 0.0
    bp_lm = n * max(r2, 0.0)
    return {
        "residual_ac1": residual_ac,
        "ljung_box_q12": float(q),
        "ljung_box_p": q_p,
        "breusch_pagan_lm": float(bp_lm),
        "breusch_pagan_p": float(stats.chi2.sf(bp_lm, df=1)),
    }


def ac1_at_lag(series: np.ndarray, lag: int) -> tuple[float, int]:
    values = np.asarray(series, dtype=np.float64)
    valid = np.isfinite(values[:-lag]) & np.isfinite(values[lag:])
    n = int(valid.sum())
    if n < 3:
        return math.nan, n
    x = values[:-lag][valid]
    y = values[lag:][valid]
    if np.std(x) <= 0 or np.std(y) <= 0:
        return math.nan, n
    return float(np.corrcoef(x, y)[0, 1]), n


def ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xv = X[valid]
    yv = y[valid]
    penalty = np.eye(Xv.shape[1]) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(Xv.T @ Xv + penalty, Xv.T @ yv)


def recovery_class(a: float) -> tuple[str, float]:
    if not math.isfinite(a):
        return "invalid", math.nan
    if 0 < a < 1:
        return "monotonic", float(-1.0 / math.log(a))
    if -1 < a <= 0:
        return "oscillatory", math.nan
    if a >= 1:
        return "non_decaying", math.nan
    return "invalid", math.nan


def validation_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    valid = np.isfinite(observed) & np.isfinite(predicted)
    y = observed[valid]
    p = predicted[valid]
    if len(y) < 3:
        return {
            "n": len(y),
            "mae": math.nan,
            "rmse": math.nan,
            "r2": math.nan,
            "pearson_r": math.nan,
            "mean_bias": math.nan,
            "calibration_slope": math.nan,
        }
    error = p - y
    total = np.sum((y - np.mean(y)) ** 2)
    r2 = 1.0 - np.sum(error**2) / total if total > 0 else math.nan
    pearson = (
        float(np.corrcoef(y, p)[0, 1])
        if np.std(y) > 0 and np.std(p) > 0
        else math.nan
    )
    calibration = (
        float(np.cov(p, y, ddof=0)[0, 1] / np.var(p))
        if np.var(p) > 0
        else math.nan
    )
    return {
        "n": len(y),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "r2": float(r2),
        "pearson_r": pearson,
        "mean_bias": float(np.mean(error)),
        "calibration_slope": calibration,
    }


def moving_block_bootstrap_slope(
    y: np.ndarray, repetitions: int, seed: int, block_length: int | None = None
) -> tuple[float, float]:
    values = np.asarray(y, dtype=np.float64)
    if not np.all(np.isfinite(values)) or len(values) < 5:
        return math.nan, math.nan
    n = len(values)
    block = block_length or max(2, int(round(math.sqrt(n))))
    rng = np.random.default_rng(seed)
    x = np.arange(n, dtype=np.float64)
    x_centered = x - x.mean()
    denominator = np.sum(x_centered**2)
    slopes = np.empty(repetitions, dtype=np.float64)
    starts = np.arange(0, n - block + 1)
    blocks_needed = int(math.ceil(n / block))
    for rep in range(repetitions):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate(
            [values[start : start + block] for start in chosen]
        )[:n]
        slopes[rep] = np.sum(x_centered * sample) / denominator
    return float(np.quantile(slopes, 0.025)), float(np.quantile(slopes, 0.975))


def trend_statistics(
    values: np.ndarray, seed: int, repetitions: int = 1000
) -> dict[str, float]:
    y = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(y)
    if valid.sum() < 5:
        return {
            "n": int(valid.sum()),
            "ols_slope": math.nan,
            "hac_se": math.nan,
            "theil_sen_slope": math.nan,
            "bootstrap_low": math.nan,
            "bootstrap_high": math.nan,
        }
    x = np.arange(len(y), dtype=np.float64)[valid]
    yv = y[valid]
    fit = ols_fit(np.column_stack([np.ones(len(x)), x]), yv, hac_lags=3)
    theil = stats.theilslopes(yv, x).slope
    low, high = moving_block_bootstrap_slope(yv, repetitions, seed)
    return {
        "n": len(yv),
        "ols_slope": float(fit["beta"][1]),
        "hac_se": float(fit["se"][1]),
        "theil_sen_slope": float(theil),
        "bootstrap_low": low,
        "bootstrap_high": high,
    }


def block_ids(
    lat: np.ndarray, lon: np.ndarray, bounds: tuple[float, float, float, float], size: float
) -> np.ndarray:
    lon_min, lat_min, _, _ = bounds
    row = np.floor((lat - lat_min) / size).astype(np.int64)
    col = np.floor((lon - lon_min) / size).astype(np.int64)
    return row * 10000 + col


def spatial_block_bootstrap(
    values: np.ndarray,
    blocks: np.ndarray,
    repetitions: int,
    seed: int,
) -> tuple[float, float, float, int]:
    valid = np.isfinite(values)
    y = values[valid]
    b = blocks[valid]
    if len(y) < 2:
        return math.nan, math.nan, math.nan, 0
    unique = np.unique(b)
    sums = np.array([np.sum(y[b == block]) for block in unique], dtype=np.float64)
    counts = np.array([np.sum(b == block) for block in unique], dtype=np.float64)
    rng = np.random.default_rng(seed)
    chosen = rng.integers(0, len(unique), size=(repetitions, len(unique)))
    estimates = np.sum(sums[chosen], axis=1) / np.sum(counts[chosen], axis=1)
    return (
        float(np.mean(y)),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
        len(unique),
    )


# Minimal Parquet v1 writer supporting required numeric and UTF-8 columns.
CT_STOP = 0
CT_I32 = 5
CT_I64 = 6
CT_BINARY = 8
CT_LIST = 9
CT_STRUCT = 12


def _uvarint(value: int) -> bytes:
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            output.append(byte | 0x80)
        else:
            output.append(byte)
            return bytes(output)


def _zigzag(value: int, bits: int = 64) -> int:
    return (value << 1) ^ (value >> (bits - 1))


class CompactStruct:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.last_field_id = 0

    def _header(self, field_id: int, compact_type: int) -> None:
        delta = field_id - self.last_field_id
        if 0 < delta <= 15:
            self.buffer.append((delta << 4) | compact_type)
        else:
            self.buffer.append(compact_type)
            self.buffer.extend(_uvarint(_zigzag(field_id, 16)))
        self.last_field_id = field_id

    def i32(self, field_id: int, value: int) -> None:
        self._header(field_id, CT_I32)
        self.buffer.extend(_uvarint(_zigzag(int(value), 32)))

    def i64(self, field_id: int, value: int) -> None:
        self._header(field_id, CT_I64)
        self.buffer.extend(_uvarint(_zigzag(int(value), 64)))

    def binary(self, field_id: int, value: str | bytes) -> None:
        payload = value.encode("utf-8") if isinstance(value, str) else value
        self._header(field_id, CT_BINARY)
        self.buffer.extend(_uvarint(len(payload)))
        self.buffer.extend(payload)

    def struct(self, field_id: int, payload: bytes) -> None:
        self._header(field_id, CT_STRUCT)
        self.buffer.extend(payload)

    def list(self, field_id: int, element_type: int, payloads: Sequence[bytes]) -> None:
        self._header(field_id, CT_LIST)
        size = len(payloads)
        if size < 15:
            self.buffer.append((size << 4) | element_type)
        else:
            self.buffer.append(0xF0 | element_type)
            self.buffer.extend(_uvarint(size))
        for payload in payloads:
            self.buffer.extend(payload)

    def finish(self) -> bytes:
        self.buffer.append(CT_STOP)
        return bytes(self.buffer)


PHYSICAL_TYPES = {
    "int32": 1,
    "int64": 2,
    "float32": 4,
    "float64": 5,
    "string": 6,
}


def _schema_element(name: str, physical: str | None, children: int | None) -> bytes:
    writer = CompactStruct()
    if physical is not None:
        writer.i32(1, PHYSICAL_TYPES[physical])
        writer.i32(3, 0)
    writer.binary(4, name)
    if children is not None:
        writer.i32(5, children)
    if physical == "string":
        writer.i32(6, 0)  # ConvertedType UTF8
    return writer.finish()


def _data_page_header(num_values: int, body_size: int) -> bytes:
    data_header = CompactStruct()
    data_header.i32(1, num_values)
    data_header.i32(2, 0)
    data_header.i32(3, 3)
    data_header.i32(4, 3)
    page_header = CompactStruct()
    page_header.i32(1, 0)
    page_header.i32(2, body_size)
    page_header.i32(3, body_size)
    page_header.struct(5, data_header.finish())
    return page_header.finish()


def _column_metadata(
    name: str, physical: str, n: int, total_size: int, offset: int
) -> bytes:
    writer = CompactStruct()
    writer.i32(1, PHYSICAL_TYPES[physical])
    writer.list(2, CT_I32, [_uvarint(_zigzag(0, 32)), _uvarint(_zigzag(3, 32))])
    encoded = name.encode("utf-8")
    writer.list(3, CT_BINARY, [_uvarint(len(encoded)) + encoded])
    writer.i32(4, 0)
    writer.i64(5, n)
    writer.i64(6, total_size)
    writer.i64(7, total_size)
    writer.i64(9, offset)
    return writer.finish()


def _column_chunk(
    name: str, physical: str, n: int, total_size: int, offset: int
) -> bytes:
    writer = CompactStruct()
    writer.i64(2, offset)
    writer.struct(3, _column_metadata(name, physical, n, total_size, offset))
    return writer.finish()


def _row_group(chunks: Sequence[bytes], total_size: int, n: int) -> bytes:
    writer = CompactStruct()
    writer.list(1, CT_STRUCT, list(chunks))
    writer.i64(2, total_size)
    writer.i64(3, n)
    writer.i64(5, total_size)
    return writer.finish()


def _key_value(key: str, value: str) -> bytes:
    writer = CompactStruct()
    writer.binary(1, key)
    writer.binary(2, value)
    return writer.finish()


def _normalize_column(values: Sequence[Any] | np.ndarray) -> tuple[str, Any, bytes]:
    array = np.asarray(values)
    if array.dtype.kind in ("U", "S", "O"):
        strings = ["" if value is None else str(value) for value in values]
        body = b"".join(
            struct.pack("<I", len(value.encode("utf-8"))) + value.encode("utf-8")
            for value in strings
        )
        return "string", strings, body
    if array.dtype.kind == "b":
        array = array.astype(np.int32)
    if array.dtype == np.int16 or array.dtype == np.uint8:
        array = array.astype(np.int32)
    mapping = {
        np.dtype("int32"): "int32",
        np.dtype("int64"): "int64",
        np.dtype("float32"): "float32",
        np.dtype("float64"): "float64",
    }
    if array.dtype not in mapping:
        array = array.astype(np.float64)
    physical = mapping[array.dtype]
    normalized = np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<")))
    return physical, normalized, normalized.tobytes(order="C")


def write_parquet(
    path: Path,
    columns: dict[str, Sequence[Any] | np.ndarray],
    metadata: dict[str, str] | None = None,
) -> None:
    assert_safe_output(path)
    ensure_dir(path.parent)
    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1:
        raise ValueError("Parquet column lengths differ")
    n = next(iter(lengths))
    normalized = {
        name: _normalize_column(values) for name, values in columns.items()
    }
    payload = bytearray(b"PAR1")
    chunks = []
    total_size = 0
    for name, (physical, _, body) in normalized.items():
        offset = len(payload)
        page = _data_page_header(n, len(body)) + body
        payload.extend(page)
        chunks.append(_column_chunk(name, physical, n, len(page), offset))
        total_size += len(page)
    schema = [_schema_element("schema", None, len(columns))]
    schema.extend(
        _schema_element(name, physical, None)
        for name, (physical, _, _) in normalized.items()
    )
    footer = CompactStruct()
    footer.i32(1, 1)
    footer.list(2, CT_STRUCT, schema)
    footer.i64(3, n)
    footer.list(4, CT_STRUCT, [_row_group(chunks, total_size, n)])
    meta = dict(metadata or {})
    meta["writer"] = "TASK0004_primitive_parquet_v1_plain_required"
    footer.list(
        5,
        CT_STRUCT,
        [_key_value(key, value) for key, value in sorted(meta.items())],
    )
    footer.binary(6, "TASK0004 Python Parquet writer")
    footer_bytes = footer.finish()
    payload.extend(footer_bytes)
    payload.extend(struct.pack("<I", len(footer_bytes)))
    payload.extend(b"PAR1")
    path.write_bytes(payload)


def rows_to_columns(rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> dict[str, list[Any]]:
    return {
        field: [row.get(field, "") for row in rows]
        for field in fields
    }


def validate_parquet(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    passed = payload[:4] == b"PAR1" and payload[-4:] == b"PAR1"
    metadata_length = struct.unpack("<I", payload[-8:-4])[0] if passed else 0
    passed = passed and 0 < metadata_length < len(payload) - 8
    return {
        "path": str(path),
        "bytes": len(payload),
        "footer_metadata_bytes": metadata_length,
        "pass": passed,
    }


def _weighted_linear_trend(
    values: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    time = np.arange(values.shape[0], dtype=np.float64)[:, None]
    valid = np.isfinite(values)
    w = np.where(valid, weights, 0.0)
    y = np.where(valid, values, 0.0)
    sw = np.sum(w, axis=0)
    st = np.sum(w * time, axis=0)
    sy = np.sum(w * y, axis=0)
    stt = np.sum(w * time * time, axis=0)
    sty = np.sum(w * time * y, axis=0)
    denominator = sw * stt - st * st
    slope = np.divide(
        sw * sty - st * sy,
        denominator,
        out=np.full(values.shape[1], np.nan),
        where=(sw >= 3) & (np.abs(denominator) > 1e-12),
    )
    intercept = np.divide(
        sy - slope * st,
        sw,
        out=np.full(values.shape[1], np.nan),
        where=sw > 0,
    )
    return intercept, slope


def preprocess_kndvi(
    values: np.ndarray,
    estimation_end: int,
    apply_end: int,
    method: str,
) -> dict[str, np.ndarray]:
    y = np.asarray(values, dtype=np.float64)
    if y.shape[0] < apply_end or estimation_end > apply_end:
        raise ValueError("Invalid preprocessing periods")
    estimate = y[:estimation_end]
    climatology = np.full((12, y.shape[1]), np.nan, dtype=np.float64)
    for month in range(12):
        climatology[month] = np.nanmean(estimate[month::12], axis=0)
    deseasonalized = np.full((apply_end, y.shape[1]), np.nan, dtype=np.float64)
    for index in range(apply_end):
        deseasonalized[index] = y[index] - climatology[index % 12]
    trend_values = deseasonalized[:estimation_end]
    base_weights = np.isfinite(trend_values).astype(np.float64)
    intercept, slope = _weighted_linear_trend(trend_values, base_weights)
    if method.lower() == "huber":
        time = np.arange(estimation_end, dtype=np.float64)[:, None]
        for _ in range(30):
            fitted = intercept[None, :] + slope[None, :] * time
            residual = trend_values - fitted
            scale = 1.4826 * np.nanmedian(
                np.abs(residual - np.nanmedian(residual, axis=0)), axis=0
            )
            scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
            cutoff = 1.345 * scale[None, :]
            abs_residual = np.abs(residual)
            robust = np.minimum(
                1.0,
                np.divide(
                    cutoff,
                    abs_residual,
                    out=np.ones_like(abs_residual),
                    where=abs_residual > 0,
                ),
            )
            robust[~np.isfinite(trend_values)] = 0.0
            new_intercept, new_slope = _weighted_linear_trend(
                trend_values, robust
            )
            change = np.nanmax(
                np.abs(np.nan_to_num(new_slope) - np.nan_to_num(slope))
            )
            intercept, slope = new_intercept, new_slope
            if change < 1e-10:
                break
    elif method.lower() != "ols":
        raise ValueError(f"Unknown detrending method: {method}")
    time_apply = np.arange(apply_end, dtype=np.float64)[:, None]
    anomaly = deseasonalized - (
        intercept[None, :] + slope[None, :] * time_apply
    )
    residual_variance = np.nanvar(
        anomaly[:estimation_end], axis=0, ddof=2
    )
    return {
        "anomaly": anomaly.astype(np.float32),
        "climatology": climatology.astype(np.float32),
        "intercept": intercept.astype(np.float32),
        "slope": slope.astype(np.float32),
        "residual_variance": residual_variance.astype(np.float32),
    }


def climate_training_transform(values: np.ndarray) -> dict[str, np.ndarray]:
    y = np.asarray(values, dtype=np.float64)
    if y.shape[0] < SCIENCE_END:
        raise ValueError("Climate array is shorter than 2001-2020")
    train = y[:TRAIN_END]
    climatology = np.full((12, y.shape[1]), np.nan, dtype=np.float64)
    for month in range(12):
        climatology[month] = np.nanmean(train[month::12], axis=0)
    anomaly = np.full((SCIENCE_END, y.shape[1]), np.nan, dtype=np.float64)
    for index in range(SCIENCE_END):
        anomaly[index] = y[index] - climatology[index % 12]
    train_mean = np.nanmean(anomaly[:TRAIN_END], axis=0)
    train_std = np.nanstd(anomaly[:TRAIN_END], axis=0, ddof=1)
    standardized = np.divide(
        anomaly - train_mean[None, :],
        train_std[None, :],
        out=np.full_like(anomaly, np.nan),
        where=train_std[None, :] > 0,
    )
    return {
        "standardized": standardized.astype(np.float32),
        "anomaly": anomaly.astype(np.float32),
        "climatology": climatology.astype(np.float32),
        "training_mean": train_mean.astype(np.float32),
        "training_std": train_std.astype(np.float32),
    }


def rolling_ac1(
    series: np.ndarray,
    window: int,
    step: int = 12,
    minimum_fraction: float = 0.8,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(series, dtype=np.float64)
    results = []
    labels = []
    for start in range(0, len(values) - window + 1, step):
        end = start + window
        block = values[start:end]
        value, n = ac1(block)
        required = math.ceil((window - 1) * minimum_fraction)
        results.append(value if n >= required else math.nan)
        end_index = end - 1
        labels.append(2001 + end_index // 12)
    return np.asarray(results, dtype=np.float64), np.asarray(labels, dtype=np.int16)


def model_design(
    state: np.ndarray,
    drivers: np.ndarray,
    model: str,
    training: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    state = np.asarray(state, dtype=np.float64)
    drivers = np.asarray(drivers, dtype=np.float64)
    if training:
        # All M0-M3 use the same t=1..190 training transitions so model
        # comparisons do not gain a row merely because M3 needs t-1 drivers.
        t_start, t_stop = 1, TRAIN_END - 1
    else:
        t_start, t_stop = TRAIN_END - 1, SCIENCE_END - 1
    t = np.arange(t_start, t_stop, dtype=np.int64)
    target = state[t + 1]
    columns = [np.ones(len(t)), state[t]]
    names = ["intercept", "a"]
    if model in ("M1", "M2", "M3"):
        columns.extend([drivers[t, 0], drivers[t, 1]])
        names.extend(["beta_vpd", "beta_sm"])
    if model in ("M2", "M3"):
        columns.extend([drivers[t, 2], drivers[t, 3]])
        names.extend(["beta_temperature", "beta_precipitation"])
    if model == "M3":
        columns.extend([drivers[t - 1, 0], drivers[t - 1, 1]])
        names.extend(["beta_vpd_lag1", "beta_sm_lag1"])
    return np.column_stack(columns), target, t, names


def simulate_counterfactual(
    state: np.ndarray,
    drivers_m2: np.ndarray,
    coefficients: np.ndarray,
    repetitions: int,
    seed: int,
) -> dict[str, float]:
    x = np.asarray(state, dtype=np.float64)
    drivers = np.asarray(drivers_m2, dtype=np.float64)
    if (
        len(x) != SCIENCE_END
        or drivers.ndim != 2
        or drivers.shape[0] != SCIENCE_END
        or len(coefficients) != drivers.shape[1] + 2
        or not np.all(np.isfinite(x))
        or not np.all(np.isfinite(drivers))
    ):
        return {
            "observed_fitted_tac": math.nan,
            "median_counterfactual_tac": math.nan,
            "climate_order_inflation": math.nan,
        }
    c = float(coefficients[0])
    a = float(coefficients[1])
    beta = np.asarray(coefficients[2:], dtype=np.float64)
    observed = np.empty(SCIENCE_END, dtype=np.float64)
    observed[0] = x[0]
    for t in range(SCIENCE_END - 1):
        observed[t + 1] = (
            c + a * observed[t] + float(drivers[t] @ beta)
        )
    observed_tac, _ = ac1(observed)
    rng = np.random.default_rng(seed)
    simulated = np.empty((repetitions, SCIENCE_END), dtype=np.float64)
    simulated[:, 0] = x[0]
    permutations = np.vstack(
        [rng.permutation(SCIENCE_END - 1) for _ in range(repetitions)]
    )
    ordered = drivers[: SCIENCE_END - 1][permutations]
    for t in range(SCIENCE_END - 1):
        simulated[:, t + 1] = (
            c
            + a * simulated[:, t]
            + ordered[:, t, :] @ beta
        )
    left = simulated[:, :-1]
    right = simulated[:, 1:]
    left_centered = left - left.mean(axis=1, keepdims=True)
    right_centered = right - right.mean(axis=1, keepdims=True)
    numerator = np.sum(left_centered * right_centered, axis=1)
    denominator = np.sqrt(
        np.sum(left_centered**2, axis=1) * np.sum(right_centered**2, axis=1)
    )
    counterfactual = np.divide(
        numerator,
        denominator,
        out=np.full(repetitions, np.nan),
        where=denominator > 0,
    )
    median = float(np.nanmedian(counterfactual))
    return {
        "observed_fitted_tac": observed_tac,
        "median_counterfactual_tac": median,
        "climate_order_inflation": (
            float(observed_tac - median) if math.isfinite(observed_tac) else math.nan
        ),
    }
