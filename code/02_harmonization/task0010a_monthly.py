from __future__ import annotations

import calendar
import csv
import itertools
import json
import math
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW = ROOT / "000 GEE Data"
RUN = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010A_Global_Drought_Recovery_Consensus"
STD = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Consensus_v01"
CACHE = RUN / "_processing_cache"
REF = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0008B_FAST_PAPER_Global_Production"
sys.path.insert(0, str(REF))
import build_global_inputs as G  # noqa: E402

G.RUN = RUN
G.DERIVED = STD
G.WORK = CACHE
YEARS = list(range(2001, 2025))
MONTHS = [f"{year:04d}-{month:02d}" for year in YEARS for month in range(1, 13)]
HEIGHT, WIDTH = 290, 720


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir(prefix: str) -> Path:
    return next(path for path in RAW.iterdir() if path.is_dir() and path.name.startswith(prefix + " "))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def overlaps(start: date, end: date) -> list[tuple[int, int]]:
    out = []
    cursor = date(start.year, start.month, 1)
    while cursor < end:
        nxt = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)
        days = (min(end, nxt) - max(start, cursor)).days
        if days > 0 and 2001 <= cursor.year <= 2024:
            out.append(((cursor.year - 2001) * 12 + cursor.month - 1, days))
        cursor = nxt
    return out


def build_kndvi(rows: np.ndarray, cols: np.ndarray) -> dict[str, np.ndarray]:
    d01 = data_dir("1")
    files = {year: next(d01.rglob(f"*_g050_global_{year}_v07.tif")) for year in YEARS}
    records = {}
    all_dates = []
    for year, path in files.items():
        with rasterio.open(path) as src:
            grouped = {key: {} for key in ("kNDVI", "supportFrac", "validFracSupport", "goodFracSupport")}
            for index, description in enumerate(src.descriptions, start=1):
                match = re.fullmatch(r"(kNDVI|supportFrac|validFracSupport|goodFracSupport)_(\d{8})", description or "")
                if not match:
                    raise RuntimeError(f"Unexpected Data01 description {description}")
                day = datetime.strptime(match.group(2), "%Y%m%d").date()
                grouped[match.group(1)][day] = index
        dates = sorted(grouped["kNDVI"])
        if any(set(grouped[key]) != set(dates) for key in grouped):
            raise RuntimeError(f"Data01 band date mismatch {year}")
        records[year] = (dates, grouped)
        all_dates.extend(dates)
    all_dates.sort()
    end_lookup = {day: all_dates[i + 1] if i + 1 < len(all_dates) else date(2025, 1, 1) for i, day in enumerate(all_dates)}
    n = len(rows)
    num = np.zeros((288, n), dtype=np.float64)
    eff = np.zeros((288, n), dtype=np.float64)
    support_num = np.zeros((288, n), dtype=np.float64)
    valid_num = np.zeros((288, n), dtype=np.float64)
    support_days = np.zeros((288, n), dtype=np.float32)
    valid_days = np.zeros((288, n), dtype=np.float32)
    count = np.zeros((288, n), dtype=np.int16)
    mapping = []
    for year in YEARS:
        dates, grouped = records[year]
        with rasterio.open(files[year]) as src:
            for day in dates:
                values = {}
                for key in grouped:
                    band = src.read(grouped[key][day], masked=True).filled(np.nan).astype(np.float32)
                    values[key] = band[rows, cols].astype(np.float64)
                support = values["supportFrac"]
                validfrac = values["validFracSupport"]
                support_ok = np.isfinite(support)
                valid_ok = support_ok & ((support == 0) | np.isfinite(validfrac))
                usable = np.where(support == 0, 0.0, support * validfrac)
                usable[~valid_ok] = np.nan
                kval = values["kNDVI"]
                k_ok = np.isfinite(kval) & np.isfinite(usable) & (usable > 0)
                for target, days in overlaps(day, end_lookup[day]):
                    support_num[target] += np.where(support_ok, days * support, 0)
                    support_days[target] += support_ok * days
                    valid_num[target] += np.where(valid_ok, days * usable, 0)
                    valid_days[target] += valid_ok * days
                    weight = days * usable
                    num[target] += np.where(k_ok, weight * kval, 0)
                    eff[target] += np.where(k_ok, weight, 0)
                    count[target] += k_ok
                    mapping.append({"dataset": "Data01", "source_date": day.isoformat(), "source_end_exclusive": end_lookup[day].isoformat(), "target_month": MONTHS[target], "overlap_days": days, "mapping": "actual_date_half_open_interval_overlap_days"})
        print(f"Data01 {year} complete", flush=True)
    out = np.divide(num, eff, out=np.full_like(num, np.nan), where=eff > 0).astype(np.float32)
    support_out = np.full((288, n), np.nan, np.float32)
    valid_out = np.full((288, n), np.nan, np.float32)
    for t, month in enumerate(MONTHS):
        y, m = map(int, month.split("-"))
        days = calendar.monthrange(y, m)[1]
        ok = np.isclose(support_days[t], days)
        support_out[t, ok] = (support_num[t, ok] / days).astype(np.float32)
        ok = np.isclose(valid_days[t], days)
        valid_out[t, ok] = (valid_num[t, ok] / days).astype(np.float32)
    write_csv(RUN / "DATE_WEIGHT_MAPPING.csv", mapping, ["dataset", "source_date", "source_end_exclusive", "target_month", "overlap_days", "mapping"])
    return {"kndvi": out, "kndvi_support": support_out, "kndvi_valid_area": valid_out, "kndvi_effective_weight": eff.astype(np.float32), "kndvi_source_count": count}


def build_climate_spei(rows: np.ndarray, cols: np.ndarray) -> dict[str, np.ndarray]:
    n = len(rows)
    out = {name: np.full((288, n), np.nan, np.float32) for name in ("temperature", "precipitation")}
    d02 = data_dir("2") / "0.5"
    for year in YEARS:
        path = next(d02.glob(f"*_{year}_v03.tif"))
        with rasterio.open(path) as src:
            index = {d: i for i, d in enumerate(src.descriptions, 1)}
            for month in range(1, 13):
                t = (year - 2001) * 12 + month - 1
                for name, desc in (("temperature", f"tempC_{year}{month:02d}"), ("precipitation", f"precip_mm_raw_{year}{month:02d}")):
                    if desc not in index:
                        raise RuntimeError(f"Missing {desc}")
                    full = src.read(index[desc], masked=True).filled(np.nan).astype(np.float32)
                    out[name][t] = full[rows, cols]
        print(f"Data02 {year} complete", flush=True)
    d22 = data_dir("22")
    spei = {name: np.full((300, n), np.nan, np.float32) for name in ("spei1", "spei3", "spei6")}
    for year in range(2000, 2025):
        path = next(d22.glob(f"*_{year}_YEAR_FULL_v04_FIXED.tif"))
        with rasterio.open(path) as src:
            if src.count != 36:
                raise RuntimeError(f"Data22 {year} band count {src.count}")
            for month in range(1, 13):
                t = (year - 2000) * 12 + month - 1
                for scale, name in enumerate(("spei1", "spei3", "spei6"), start=1):
                    full = src.read((month - 1) * 3 + scale, masked=True).filled(np.nan).astype(np.float32)
                    spei[name][t] = full[rows + 10, cols]
        print(f"Data22 {year} complete", flush=True)
    return {**out, **spei}


def build_hydro(rows: np.ndarray, cols: np.ndarray, forest: np.ndarray) -> dict[str, np.ndarray]:
    n = len(rows)
    out = {name: np.full((288, n), np.nan, np.float32) for name in ("vpd", "vpd_support", "soil_moisture", "soil_support")}
    tiles = []
    for r0 in range(0, HEIGHT, 20):
        for c0 in range(0, WIDTH, 20):
            r1, c1 = min(HEIGHT, r0 + 20), min(WIDTH, c0 + 20)
            if np.any(forest[r0:r1, c0:c1]):
                tiles.append((r0, r1, c0, c1))
    paths = {}
    for year in YEARS:
        p14 = G.part_files("Data14", year, "60band_v04")
        p15 = G.part_files("Data15", year, "96band_v02")
        if len(p14) != 8 or len(p15) != 8:
            raise RuntimeError(f"Hydro parts missing {year}: {len(p14)}/{len(p15)}")
        with rasterio.open(p14[0]) as src:
            if "vpd_mean_m01_kPa" not in src.descriptions:
                raise RuntimeError("VPD unit not proven by band descriptions")
        with rasterio.open(p15[0]) as src:
            if not all(f"swvl{i}_mean_m01_m3m3" in src.descriptions for i in (1, 2, 3)):
                raise RuntimeError("Soil layer definition not proven")
        paths[year] = ([str(p) for p in p14], [str(p) for p in p15])
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        futures = {pool.submit(G.process_hydro_year, year, paths[year][0], paths[year][1], tiles): year for year in YEARS}
        for future in as_completed(futures):
            year, data = future.result()
            s = (year - 2001) * 12
            out["vpd"][s:s+12] = data["vpd"][:, rows, cols]
            out["vpd_support"][s:s+12] = data["vpd_support"][:, rows, cols]
            out["soil_moisture"][s:s+12] = data["soil"][:, rows, cols]
            out["soil_support"][s:s+12] = data["soil_support"][:, rows, cols]
            print(f"Data14/15 {year} complete", flush=True)
    return out


def parse_tile(path: Path) -> tuple[int, int]:
    with rasterio.open(path) as src:
        r0 = int(round((85.0 - src.bounds.top) / 0.05))
        c0 = int(round((src.bounds.left + 180.0) / 0.05))
    return r0, c0


def fire_year(args: tuple[int, str, str]) -> tuple[int, np.ndarray, np.ndarray]:
    year, root_text, mask_text = args
    forest = np.load(mask_text)
    target = np.full((12, HEIGHT, WIDTH), np.nan, np.float32)
    support = np.zeros((12, HEIGHT, WIDTH), np.float32)
    paths = sorted(Path(root_text, "01_years", str(year), "02_downloaded_tif").glob("*.tif"))
    if len(paths) != 57:
        raise RuntimeError(f"Data06 {year}: expected 57 tiles")
    for path in paths:
        with rasterio.open(path) as src:
            tr0 = int(round((85.0 - src.bounds.top) / 0.5))
            tc0 = int(round((src.bounds.left + 180.0) / 0.5))
            th, tw = src.height // 10, src.width // 10
            r0, r1, c0, c1 = max(0, tr0), min(HEIGHT, tr0 + th), max(0, tc0), min(WIDTH, tc0 + tw)
            if r1 <= r0 or c1 <= c0 or not np.any(forest[r0:r1, c0:c1]):
                continue
            desc = {d: i for i, d in enumerate(src.descriptions, 1)}
            raw = src.read([desc[f"burned_land_frac_m{m:02d}_{year}"] for m in range(1, 13)] + [desc[f"valid_land_area_frac_m{m:02d}_{year}"] for m in range(1, 13)], masked=True).filled(np.nan).astype(np.float32)
            lat = src.bounds.top - 0.025 - np.arange(src.height) * 0.05
            w = np.cos(np.deg2rad(lat)).reshape(th, 10, 1, 1)
            for m in range(12):
                burn = raw[m].reshape(th, 10, tw, 10)
                valid = raw[12 + m].reshape(th, 10, tw, 10)
                ok = np.isfinite(burn) & np.isfinite(valid) & (valid > 0)
                den = np.sum(np.where(ok, valid * w, 0), axis=(1, 3))
                num = np.sum(np.where(ok, burn * valid * w, 0), axis=(1, 3))
                val = np.divide(num, den, out=np.full((th, tw), np.nan), where=den > 0)
                full = np.sum(w[:, :, 0, 0], axis=1)[:, None] * 10
                sup = np.divide(den, full, out=np.zeros((th, tw)), where=full > 0)
                sr0, sr1, sc0, sc1 = r0-tr0, r1-tr0, c0-tc0, c1-tc0
                target[m, r0:r1, c0:c1] = val[sr0:sr1, sc0:sc1]
                support[m, r0:r1, c0:c1] = sup[sr0:sr1, sc0:sc1]
    return year, target, support


def build_fire(rows: np.ndarray, cols: np.ndarray) -> dict[str, np.ndarray]:
    n = len(rows)
    out = np.full((288, n), np.nan, np.float32)
    sup = np.zeros((288, n), np.float32)
    root = data_dir("6")
    mask_path = CACHE / "forest_mask_30.npy"
    with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        futures = {pool.submit(fire_year, (year, str(root), str(mask_path))): year for year in YEARS}
        for future in as_completed(futures):
            year, values, support = future.result()
            s = (year - 2001) * 12
            out[s:s+12] = values[:, rows, cols]
            sup[s:s+12] = support[:, rows, cols]
            print(f"Data06 {year} complete", flush=True)
    if np.nanmin(out) < -1e-6 or np.nanmax(out) > 1 + 1e-6:
        raise RuntimeError("Fire aggregation outside [0,1]")
    return {"burned_fraction": out, "fire_support": sup}


def build_productivity(rows: np.ndarray, cols: np.ndarray) -> dict[str, np.ndarray]:
    d07 = data_dir("7")
    gpp = np.full((24, len(rows)), np.nan, np.float32)
    npp = np.full_like(gpp, np.nan)
    support = np.full_like(gpp, np.nan)
    for year in YEARS:
        path = next(d07.rglob(f"*_{year}_v04.tif"))
        gv, gs, _ = G.aggregate_weighted_global(path, 2, 1)
        nv, ns, _ = G.aggregate_weighted_global(path, 3, 1)
        i = year - 2001
        gpp[i], npp[i], support[i] = gv[rows, cols], nv[rows, cols], np.minimum(gs, ns)[rows, cols]
        print(f"Data07 {year} complete", flush=True)
    return {"annual_gpp": gpp, "annual_npp": npp, "annual_productivity_support": support}


def save_arrays(groups: list[dict[str, np.ndarray]], rows: np.ndarray, cols: np.ndarray) -> None:
    np.save(CACHE / "forest_rows.npy", rows)
    np.save(CACHE / "forest_cols.npy", cols)
    for group in groups:
        for name, values in group.items():
            np.save(CACHE / f"global_{name}.npy", values)


def write_zarr(groups: list[dict[str, np.ndarray]], rows: np.ndarray, cols: np.ndarray) -> None:
    store = STD / "GLOBAL_MONTHLY_AND_ANNUAL_STATE.zarr"
    store.mkdir(parents=True, exist_ok=True)
    (store / ".zgroup").write_text('{"zarr_format": 2}', encoding="utf-8")
    root_attrs = {"title": "TASK0010A global forest pixel state", "grid": "EPSG:4326 0.5-degree", "main_period": "2001-2020", "temporal_validation": "2021-2023", "recent_censor_only": "2024", "no_imputation": True}
    (store / ".zattrs").write_text(json.dumps(root_attrs), encoding="utf-8")
    metadata = {".zgroup": {"zarr_format": 2}, ".zattrs": root_attrs}
    arrays = {"pixel_id": (rows.astype(np.int64) * WIDTH + cols, ("pixel",), (4096,), "1", -1), "lat": ((84.75 - rows * 0.5).astype(np.float32), ("pixel",), (4096,), "degree_north", np.nan), "lon": ((-179.75 + cols * 0.5).astype(np.float32), ("pixel",), (4096,), "degree_east", np.nan)}
    for group in groups:
        for name, values in group.items():
            dims = ("time", "pixel") if values.shape[0] in (288, 300) else ("year", "pixel")
            chunks = (12, min(4096, values.shape[1])) if len(values.shape) == 2 else values.shape
            units = {"kndvi": "1", "temperature": "degree_C", "precipitation": "mm_month-1", "vpd": "kPa", "soil_moisture": "m3_m-3", "burned_fraction": "fraction", "spei1": "1", "spei3": "1", "spei6": "1", "annual_gpp": "kgC_m-2_year-1", "annual_npp": "kgC_m-2_year-1"}.get(name, "1")
            arrays[name] = (values, dims, chunks, units, np.nan if values.dtype.kind == "f" else -1)
    for name, (values, dims, chunks, units, fill) in arrays.items():
        za, zt = G.write_zarr_array(store, name, np.asarray(values), dims, chunks, {"units": units, "no_gap_fill": True}, fill)
        metadata[f"{name}/.zarray"] = za
        metadata[f"{name}/.zattrs"] = zt
    (store / ".zmetadata").write_text(json.dumps({"zarr_consolidated_format": 1, "metadata": metadata}, sort_keys=True), encoding="utf-8")


def main() -> None:
    forest = np.load(CACHE / "forest_mask_30.npy")
    rows, cols = np.where(forest)
    state = build_kndvi(rows, cols)
    climate = build_climate_spei(rows, cols)
    hydro = build_hydro(rows, cols, forest)
    fire = build_fire(rows, cols)
    productivity = build_productivity(rows, cols)
    groups = [state, climate, hydro, fire, productivity]
    save_arrays(groups, rows, cols)
    write_zarr(groups, rows, cols)
    qc = []
    for group in groups:
        for name, values in group.items():
            qc.append({"variable": name, "shape": "x".join(map(str, values.shape)), "finite_count": int(np.isfinite(values).sum()), "total_count": int(values.size), "finite_fraction": float(np.isfinite(values).mean()), "minimum": float(np.nanmin(values)) if np.isfinite(values).any() else "", "maximum": float(np.nanmax(values)) if np.isfinite(values).any() else "", "interpolated_or_filled": False})
    write_csv(RUN / "GLOBAL_MONTHLY_COVERAGE_QC.csv", qc, ["variable", "shape", "finite_count", "total_count", "finite_fraction", "minimum", "maximum", "interpolated_or_filled"])
    (RUN / "CHECKPOINT_02_MONTHLY_ALIGNMENT.json").write_text(json.dumps({"status": "PASS", "forest_pixels": len(rows), "months_2001_2024": 288, "spei_months_with_buffer": 300, "date_weighting": "actual dates and cross-month overlap days", "no_imputation": True, "completed_utc": utc()}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "pixels": len(rows)}))


if __name__ == "__main__":
    main()
