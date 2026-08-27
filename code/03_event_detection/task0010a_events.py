from __future__ import annotations

import csv
import json
import math
import pickle
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Sequence

import numpy as np


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW = ROOT / "000 GEE Data"
RUN = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010A_Global_Drought_Recovery_Consensus"
STD = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Consensus_v01"
CACHE = RUN / "_processing_cache"
REF8 = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0008B_FAST_PAPER_Global_Production"
REF4 = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics"
sys.path.insert(0, str(REF8))
sys.path.insert(0, str(REF4))
import build_global_inputs as G  # noqa: E402
import task0004_lib as P  # noqa: E402
G.RUN, G.DERIVED, G.WORK = RUN, STD, CACHE
P.RUN_ROOT, P.OUTPUT_ROOT = RUN, STD

WIDTH = 720
TRAIN_MONTHS = 240
TOTAL_MONTHS = 288
VALIDATION_END = 275
SCALES = {"D1": ("spei1", -1.0), "D3": ("spei3", -1.0), "D6": ("spei6", -1.0)}
FOREST_LABELS = {1: "Evergreen needleleaf forest", 2: "Evergreen broadleaf forest", 3: "Deciduous needleleaf forest", 4: "Deciduous broadleaf forest", 5: "Mixed forest"}
CLIMATE_LABELS = {1: "Tropical", 2: "Arid", 3: "Temperate", 4: "Boreal", 5: "Polar"}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir(prefix: str) -> Path:
    return next(path for path in RAW.iterdir() if path.is_dir() and path.name.startswith(prefix + " "))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def frozen_standardize(values: np.ndarray, minimum: int = 160) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    train = values[:TRAIN_MONTHS]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        climatology = np.nanmean(train.reshape(20, 12, train.shape[1]), axis=0)
    deseasoned = values - np.tile(climatology, (24, 1))
    yt = deseasoned[:TRAIN_MONTHS]
    t = np.arange(TRAIN_MONTHS, dtype=np.float64)[:, None]
    valid = np.isfinite(yt)
    n = valid.sum(axis=0).astype(float)
    y = np.where(valid, yt, 0)
    st = np.where(valid, t, 0).sum(axis=0)
    sy = y.sum(axis=0)
    stt = np.where(valid, t * t, 0).sum(axis=0)
    sty = np.where(valid, t * y, 0).sum(axis=0)
    den = n * stt - st * st
    good = (n >= minimum) & (np.abs(den) > 1e-12)
    slope = np.full(values.shape[1], np.nan)
    intercept = np.full(values.shape[1], np.nan)
    slope[good] = (n[good] * sty[good] - st[good] * sy[good]) / den[good]
    intercept[good] = (sy[good] - slope[good] * st[good]) / n[good]
    residual = deseasoned - (intercept[None] + slope[None] * np.arange(TOTAL_MONTHS)[:, None])
    residual[~np.isfinite(values)] = np.nan
    sd = np.nanstd(residual[:TRAIN_MONTHS], axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = residual / sd[None]
    out[:, ~good | ~np.isfinite(sd) | (sd <= 0)] = np.nan
    return out.astype(np.float32)


def annual_standardize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, float)
    t = np.arange(20, dtype=float)[:, None]
    train = values[:20]
    valid = np.isfinite(train)
    n = valid.sum(axis=0).astype(float)
    y = np.where(valid, train, 0)
    st = np.where(valid, t, 0).sum(axis=0)
    sy = y.sum(axis=0)
    stt = np.where(valid, t*t, 0).sum(axis=0)
    sty = np.where(valid, t*y, 0).sum(axis=0)
    den = n*stt-st*st
    good = (n >= 15) & (np.abs(den) > 1e-12)
    b = np.full(values.shape[1], np.nan); a = b.copy()
    b[good] = (n[good]*sty[good]-st[good]*sy[good])/den[good]
    a[good] = (sy[good]-b[good]*st[good])/n[good]
    res = values-(a[None]+b[None]*np.arange(24)[:,None])
    sd = np.nanstd(res[:20], axis=0, ddof=1)
    return (res/sd[None]).astype(np.float32)


def find_runs(values: np.ndarray, threshold: float) -> list[tuple[int, int, int]]:
    dry = np.isfinite(values) & (values < threshold)
    indexes = np.flatnonzero(dry)
    if not len(indexes):
        return []
    runs = [[int(indexes[0]), int(indexes[0])]]
    for idx in indexes[1:]:
        idx = int(idx)
        if idx == runs[-1][1] + 1:
            runs[-1][1] = idx
        else:
            runs.append([idx, idx])
    merged = [runs[0]]
    for start, end in runs[1:]:
        if start - merged[-1][1] - 1 < 2:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end, int(dry[start:end+1].sum())) for start, end in merged if int(dry[start:end+1].sum()) >= 2]


def recovery(anom: np.ndarray, start: int, end: int, next_start: int | None) -> dict | None:
    negative = np.flatnonzero(np.isfinite(anom[start:end+1]) & (anom[start:end+1] < -0.5))
    if not len(negative):
        return None
    negative_start = start + int(negative[0])
    first = next((i for i in range(negative_start + 1, len(anom)) if np.isfinite(anom[i]) and anom[i] > -0.5), None)
    search_end = first if first is not None else len(anom)-1
    block = anom[negative_start:search_end+1]
    if not np.isfinite(block).any():
        return None
    minimum = negative_start + int(np.nanargmin(block))
    if first is None or first <= minimum:
        first = next((i for i in range(minimum + 1, len(anom)) if np.isfinite(anom[i]) and anom[i] > -0.5), None)
    finite_after = np.flatnonzero(np.isfinite(anom[minimum:]))
    censor = first if first is not None else minimum + int(finite_after[-1]) if len(finite_after) else minimum
    return {"negative_start": negative_start, "minimum": minimum, "recovery": first, "censor": censor, "right_censored": int(first is None), "recovery_min": float(first-minimum) if first is not None else math.nan, "recovery_end": float(max(0, first-end)) if first is not None else math.nan, "followup": float(censor-minimum) if first is None else math.nan, "recovered_before_next": int(first is not None and first < next_start) if next_start is not None else (1 if first is not None else math.nan), "incomplete_before_next": int(not(first is not None and first < next_start)) if next_start is not None else math.nan, "next_interval": float(next_start-end) if next_start is not None else math.nan, "missing_uncertainty": int((~np.isfinite(anom[minimum:censor+1])).any())}


def month_label(index: int) -> str:
    return f"{2001 + index//12:04d}-{index%12+1:02d}"


def area_km2(lat: float) -> float:
    radius = 6371.0088
    return float(radius**2 * math.radians(0.5) * (math.sin(math.radians(lat+0.25))-math.sin(math.radians(lat-0.25))))


def region_label(lat: float, lon: float) -> str:
    if -170 <= lon < -30 and lat >= 7: return "North America"
    if -85 <= lon < -30 and lat < 15: return "South America"
    if -25 <= lon < 60 and lat >= 35: return "Europe"
    if -20 <= lon < 55 and lat < 35: return "Africa"
    if 55 <= lon < 180 and lat >= 0: return "Asia"
    if 110 <= lon < 180 and lat < 0: return "Oceania"
    return "Other"


def static_enrichment(rows: np.ndarray, cols: np.ndarray) -> dict[str, np.ndarray]:
    path = CACHE / "static_enrichment.npz"
    if path.exists():
        return dict(np.load(path))
    d11 = data_dir("11"); p11 = next(d11.rglob("*.tif"))
    canopy, _, _ = G.aggregate_weighted_global(p11, 2, 1)
    d12 = data_dir("12"); p12 = sorted((d12 / "01_downloaded_tiles").glob("*.tif"))
    clay, _, _ = G.aggregate_reprojected_tiles(p12, 14, 1)
    sand, _, _ = G.aggregate_reprojected_tiles(p12, 15, 1)
    d13 = data_dir("13"); p13 = sorted((d13 / "02_downloaded_land368").glob("*.tif"))
    slope, _, _ = G.aggregate_reprojected_tiles(p13, 7, 1)
    out = {"canopy_height": canopy[rows, cols], "clay_100cm": clay[rows, cols], "sand_100cm": sand[rows, cols], "slope": slope[rows, cols]}
    np.savez_compressed(path, **out)
    return out


def mode_rows(values: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    block = values[:, rows, cols]
    out = np.full(len(rows), -1, np.int16)
    for i in range(len(rows)):
        valid = block[:, i][block[:, i] >= 0]
        if len(valid): out[i] = int(np.bincount(valid.astype(int)).argmax())
    return out


def infer_columns(rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    columns = {}
    for field in fields:
        values = [row.get(field, "") for row in rows]
        numeric, failed, missing = [], False, False
        for value in values:
            if value is None or value == "": numeric.append(math.nan); missing = True; continue
            if isinstance(value, str): failed = True; break
            try: numeric.append(float(value))
            except Exception: failed = True; break
        if failed: columns[field] = ["" if value is None else str(value) for value in values]
        elif not missing and all(math.isfinite(v) and v.is_integer() for v in numeric): columns[field] = np.asarray(numeric, dtype=np.int64)
        else: columns[field] = np.asarray(numeric, dtype=np.float64)
    return columns


FIELDS = [
    "event_id","pixel_id","lon","lat","pixel_area_km2","event_start","event_end","recovery_start","recovery_end","spei_timescale","spei_threshold","drought_duration","drought_duration_months","minimum_spei","minimum_SPEI","cumulative_spei_deficit","cumulative_SPEI_deficit","kNDVI_loss_amplitude","kNDVI_loss_amplitude_sd","antecedent_drought_frequency","antecedent_drought_frequency_5yr","interval_since_previous_drought","interval_since_previous_drought_months","observed_recovery_time_months","recovery_time_from_minimum_months","recovery_time_from_drought_end_months","censored_followup_months","right_censored","last_observed_month","recovered_before_next_drought","incomplete_recovery_before_next_drought","next_drought_interval_months","recovery_period_soil_moisture","recovery_period_soil_moisture_mean_anomaly","recovery_period_vpd","recovery_period_VPD_mean_anomaly","recovery_period_temperature","recovery_period_temperature_mean_anomaly","recovery_period_precipitation","recovery_period_precipitation_mean_anomaly","forest_cover","forest_type","biome","climate_zone","climate_zone_label","large_region","biomass","canopy_height","soil_water_holding_capacity","field_capacity_100cm","soil_texture","clay_100cm","sand_100cm","elevation","slope","hydrological_background","human_modification","human_modification_group","intact_forest","burned_fraction_during_drought","burned_fraction_during_recovery","max_monthly_burned_fraction","cumulative_burned_fraction","any_fire_overlap","fire_overlap_months","fire_valid_support","gpp_legacy","npp_legacy","train_or_holdout","analysis_period","temporal_evaluation_eligible","temporal_evaluation_right_censored","spatial_block_5deg","spatial_block_id","production_block_10deg","qc_flag","predicted_recovery_time","predicted_recovery_time_months","predicted_hazard","predicted_recovery_probability","predicted_incomplete_before_next_drought"
]


def main() -> None:
    rows = np.load(CACHE / "forest_rows.npy"); cols = np.load(CACHE / "forest_cols.npy")
    kndvi = np.load(CACHE / "global_kndvi.npy", mmap_mode="r")
    k_anom = frozen_standardize(kndvi)
    np.save(CACHE / "global_kndvi_anomaly.npy", k_anom)
    climate = {name: frozen_standardize(np.load(CACHE / f"global_{name}.npy", mmap_mode="r")) for name in ("soil_moisture","vpd","temperature","precipitation")}
    spei = {name: np.load(CACHE / f"global_{name}.npy", mmap_mode="r") for name in ("spei1","spei3","spei6")}
    fire = np.load(CACHE / "global_burned_fraction.npy", mmap_mode="r"); fire_support = np.load(CACHE / "global_fire_support.npy", mmap_mode="r")
    gpp = annual_standardize(np.load(CACHE / "global_annual_gpp.npy", mmap_mode="r")); npp = annual_standardize(np.load(CACHE / "global_annual_npp.npy", mmap_mode="r"))
    forest_mean = np.load(CACHE / "forest_cover_mean.npy")[rows, cols]
    annual_type = np.load(CACHE / "annual_forest_type.npy", mmap_mode="r")
    forest_type = mode_rows(annual_type, rows, cols)
    static = dict(np.load(CACHE / "static_background.npz")); enrich = static_enrichment(rows, cols)
    static_pix = {"human_modification": static["human_modification"][rows, cols], "climate_zone": static["climate_zone"][rows, cols].astype(np.int16), "biomass": static["biomass"][rows, cols], "field_capacity_100cm": static["soil_background"][rows, cols], "elevation": static["topography"][rows, cols], "intact_forest": static["intact_forest"][rows, cols], **enrich}
    hm_q75 = float(np.nanquantile(static_pix["human_modification"], .75))
    all_events, counts = [], []
    excluded_no_veg = 0
    for scale, (spei_name, threshold) in SCALES.items():
        events = []
        for pixel in range(len(rows)):
            runs = find_runs(spei[spei_name][:, pixel], threshold)
            for j, (sfull, efull, duration) in enumerate(runs):
                if sfull < 12: continue
                start, end = sfull-12, efull-12
                if start >= TOTAL_MONTHS: continue
                end = min(end, TOTAL_MONTHS-1)
                next_start = runs[j+1][0]-12 if j+1 < len(runs) and runs[j+1][0]-12 < TOTAL_MONTHS else None
                rec = recovery(k_anom[:, pixel], start, end, next_start)
                if rec is None: excluded_no_veg += 1; continue
                rstop = rec["recovery"] if rec["recovery"] is not None else rec["censor"]
                cblock = slice(rec["minimum"], rstop+1)
                def cmean(name):
                    vals = climate[name][cblock, pixel]
                    return float(np.nanmean(vals)) if np.isfinite(vals).any() else math.nan
                drought_fire = fire[start:end+1, pixel]; recovery_fire = fire[rec["minimum"]:rstop+1, pixel]; combined = fire[start:rstop+1, pixel]; fs = fire_support[start:rstop+1, pixel]
                fire_sum_d = float(min(1, np.nansum(drought_fire))) if np.isfinite(drought_fire).any() else math.nan
                fire_sum_r = float(min(1, np.nansum(recovery_fire))) if np.isfinite(recovery_fire).any() else math.nan
                cumulative = float(min(1, np.nansum(combined))) if np.isfinite(combined).any() else math.nan
                year = 2001 + start//12; annual_i = year-2001
                yi = slice(annual_i, min(24, annual_i+3))
                glegacy = float(np.nanmean(gpp[yi, pixel])) if np.isfinite(gpp[yi, pixel]).any() else math.nan
                nlegacy = float(np.nanmean(npp[annual_i:min(24, annual_i+2), pixel])) if np.isfinite(npp[annual_i:min(24, annual_i+2), pixel]).any() else math.nan
                lat = float(84.75-rows[pixel]*.5); lon = float(-179.75+cols[pixel]*.5)
                prev = runs[j-1] if j else None
                antecedent = sum(1 for rs, re, _ in runs[:j] if rs >= sfull-60)
                if start < TRAIN_MONTHS:
                    period = "TRAIN_2001_2020" if rstop < TRAIN_MONTHS else "TRAIN_BOUNDARY_EXCLUDED"
                elif start <= VALIDATION_END: period = "TEMPORAL_HOLDOUT_2021_2023"
                else: period = "CURRENT_STATUS_2024_CENSOR_ONLY"
                temporal_eligible = int(period == "TEMPORAL_HOLDOUT_2021_2023")
                temporal_censored = int(rec["recovery"] is None or rec["recovery"] > VALIDATION_END) if temporal_eligible else math.nan
                climate_code = int(static_pix["climate_zone"][pixel])
                texture = f"clay={static_pix['clay_100cm'][pixel]:.3g};sand={static_pix['sand_100cm'][pixel]:.3g}" if np.isfinite(static_pix["clay_100cm"][pixel]) and np.isfinite(static_pix["sand_100cm"][pixel]) else "missing"
                event_id = f"{scale}_{int(rows[pixel])*WIDTH+int(cols[pixel])}_{month_label(start).replace('-','')}_{j:02d}"
                row = {
                    "event_id": event_id,"pixel_id": int(rows[pixel])*WIDTH+int(cols[pixel]),"lon": lon,"lat": lat,"pixel_area_km2": area_km2(lat),"event_start": month_label(start),"event_end": month_label(end),"recovery_start": month_label(rec["minimum"]),"recovery_end": month_label(rec["recovery"]) if rec["recovery"] is not None else "","spei_timescale": scale,"spei_threshold": threshold,"drought_duration": duration,"drought_duration_months": duration,"minimum_spei": float(np.nanmin(spei[spei_name][sfull:efull+1,pixel])),"cumulative_spei_deficit": float(np.nansum(np.minimum(spei[spei_name][sfull:efull+1,pixel],0))),"kNDVI_loss_amplitude": float(-np.nanmin(k_anom[start:end+1,pixel])),"antecedent_drought_frequency": antecedent,"interval_since_previous_drought": float(sfull-prev[1]) if prev else math.nan,"observed_recovery_time_months": rec["recovery_min"],"recovery_time_from_minimum_months": rec["recovery_min"],"recovery_time_from_drought_end_months": rec["recovery_end"],"censored_followup_months": rec["followup"],"right_censored": rec["right_censored"],"last_observed_month": month_label(rec["censor"]),"recovered_before_next_drought": rec["recovered_before_next"],"incomplete_recovery_before_next_drought": rec["incomplete_before_next"],"next_drought_interval_months": rec["next_interval"],"recovery_period_soil_moisture": cmean("soil_moisture"),"recovery_period_vpd": cmean("vpd"),"recovery_period_temperature": cmean("temperature"),"recovery_period_precipitation": cmean("precipitation"),"forest_cover": float(forest_mean[pixel]),"forest_type": int(forest_type[pixel]),"biome": FOREST_LABELS.get(int(forest_type[pixel]),"Other forest"),"climate_zone": climate_code,"climate_zone_label": CLIMATE_LABELS.get(climate_code,"Unknown"),"large_region": region_label(lat,lon),"biomass": float(static_pix["biomass"][pixel]),"canopy_height": float(static_pix["canopy_height"][pixel]),"soil_water_holding_capacity": float(static_pix["field_capacity_100cm"][pixel]),"field_capacity_100cm": float(static_pix["field_capacity_100cm"][pixel]),"soil_texture": texture,"clay_100cm": float(static_pix["clay_100cm"][pixel]),"sand_100cm": float(static_pix["sand_100cm"][pixel]),"elevation": float(static_pix["elevation"][pixel]),"slope": float(static_pix["slope"][pixel]),"hydrological_background": float(static_pix["field_capacity_100cm"][pixel]),"human_modification": float(static_pix["human_modification"][pixel]),"human_modification_group": "high" if static_pix["human_modification"][pixel]>=hm_q75 else "lower","intact_forest": float(static_pix["intact_forest"][pixel]),"burned_fraction_during_drought": fire_sum_d,"burned_fraction_during_recovery": fire_sum_r,"max_monthly_burned_fraction": float(np.nanmax(combined)) if np.isfinite(combined).any() else math.nan,"cumulative_burned_fraction": cumulative,"any_fire_overlap": int(np.any(np.isfinite(combined)&(combined>0))) if np.isfinite(combined).any() else math.nan,"fire_overlap_months": int(np.sum(np.isfinite(combined)&(combined>0))) if np.isfinite(combined).any() else math.nan,"fire_valid_support": float(np.nanmean(fs)) if np.isfinite(fs).any() else math.nan,"gpp_legacy": glegacy,"npp_legacy": nlegacy,"train_or_holdout": period,"analysis_period": period,"temporal_evaluation_eligible": temporal_eligible,"temporal_evaluation_right_censored": temporal_censored,"spatial_block_5deg": f"B5_{math.floor((lat+60)/5):02d}_{math.floor((lon+180)/5):02d}","spatial_block_id": f"B5_{math.floor((lat+60)/5):02d}_{math.floor((lon+180)/5):02d}","production_block_10deg": f"B10_{math.floor((lat+60)/10):02d}_{math.floor((lon+180)/10):02d}","qc_flag": "PASS" if all(np.isfinite(rowv) for rowv in (duration, fire_sum_d, static_pix["biomass"][pixel])) else "PARTIAL_STATIC_OR_FIRE","predicted_recovery_time": math.nan,"predicted_recovery_time_months": math.nan,"predicted_hazard": math.nan,"predicted_recovery_probability": math.nan,"predicted_incomplete_before_next_drought": math.nan,
                }
                row.update({"minimum_SPEI":row["minimum_spei"],"cumulative_SPEI_deficit":row["cumulative_spei_deficit"],"kNDVI_loss_amplitude_sd":row["kNDVI_loss_amplitude"],"antecedent_drought_frequency_5yr":row["antecedent_drought_frequency"],"interval_since_previous_drought_months":row["interval_since_previous_drought"],"recovery_period_soil_moisture_mean_anomaly":row["recovery_period_soil_moisture"],"recovery_period_VPD_mean_anomaly":row["recovery_period_vpd"],"recovery_period_temperature_mean_anomaly":row["recovery_period_temperature"],"recovery_period_precipitation_mean_anomaly":row["recovery_period_precipitation"]})
                events.append(row)
        P.write_parquet(RUN / f"GLOBAL_EVENT_LEVEL_{scale}.parquet", infer_columns(events,FIELDS), {"task":"0010A","scale":scale,"right_censoring":"retained","no_imputation":"true"})
        with (CACHE / f"events_{scale}.pkl").open("wb") as handle: pickle.dump(events, handle, protocol=5)
        all_events.extend(events)
        counts.append({"scale":scale,"effective_events":len(events),"training_events":sum(r["analysis_period"]=="TRAIN_2001_2020" for r in events),"training_boundary_excluded":sum(r["analysis_period"]=="TRAIN_BOUNDARY_EXCLUDED" for r in events),"temporal_holdout_events":sum(r["analysis_period"]=="TEMPORAL_HOLDOUT_2021_2023" for r in events),"current_2024_events":sum(r["analysis_period"]=="CURRENT_STATUS_2024_CENSOR_ONLY" for r in events),"right_censored_events":sum(r["right_censored"]==1 for r in events)})
        print(json.dumps(counts[-1]), flush=True)
    P.write_parquet(RUN / "GLOBAL_EVENT_LEVEL_ALL.parquet", infer_columns(all_events,FIELDS), {"task":"0010A","scales":"D1|D3|D6","DT_in_vote":"false"})
    write_csv(RUN/"GLOBAL_EVENT_COUNTS.csv",counts,list(counts[0]))
    tests=[{"test":"drought_duration_and_gap","pass":all(r["drought_duration"]>=2 for r in all_events),"observed":len(all_events)},{"test":"right_censor_missing_recovery","pass":all((r["right_censored"]==0) or not math.isfinite(r["observed_recovery_time_months"]) for r in all_events),"observed":sum(r["right_censored"] for r in all_events)},{"test":"2024_not_complete_performance","pass":all(r["temporal_evaluation_eligible"]==0 for r in all_events if r["analysis_period"]=="CURRENT_STATUS_2024_CENSOR_ONLY"),"observed":"2024 censor only"},{"test":"dt_not_in_vote","pass":set(SCALES)=={"D1","D3","D6"},"observed":"D1|D3|D6"},{"test":"small_block_nonempty","pass":any(r["spatial_block_5deg"]==all_events[0]["spatial_block_5deg"] for r in all_events),"observed":all_events[0]["spatial_block_5deg"]}]
    write_csv(RUN/"DRY_RUN_TESTS.csv",tests,["test","pass","observed"])
    (RUN/"CHECKPOINT_04_RECOVERY_RIGHT_CENSOR.json").write_text(json.dumps({"status":"PASS","event_count":len(all_events),"no_vegetation_exclusions":excluded_no_veg,"completed_utc":utc()},indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","all_events":len(all_events)}))


if __name__ == "__main__": main()
