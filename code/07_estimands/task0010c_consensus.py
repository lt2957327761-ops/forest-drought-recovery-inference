from __future__ import annotations

import math
import shutil
import zlib
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.transform import from_origin
from sklearn.metrics import roc_auc_score

import task0010c_core as C


STATUS_CODE = {"LIMITED": 1, "CONDITIONAL": 2, "SUPPORTED": 3}


def block_id(latitude: float, longitude: float) -> str:
    return f"B5_{math.floor((latitude + 60) / 5):02d}_{math.floor((longitude + 180) / 5):02d}"


def enrichment(rows: list[dict]) -> float:
    total_w = sum(row.get("weight", 1.0) for row in rows)
    flagged_w = sum(row.get("weight", 1.0) for row in rows if int(row["flag"]) == 1)
    if total_w <= 0 or flagged_w <= 0:
        return math.nan
    baseline = sum(row["outcome"] * row.get("weight", 1.0) for row in rows) / total_w
    flagged = sum(row["outcome"] * row.get("weight", 1.0) for row in rows if int(row["flag"]) == 1) / flagged_w
    return flagged / baseline if baseline > 0 else math.nan


def block_bootstrap(rows: list[dict], seed: int, reps: int = 500) -> tuple[float, float, float, int, int]:
    usable = [row for row in rows if math.isfinite(float(row["outcome"])) and math.isfinite(float(row.get("weight", 1.0)))]
    if not usable:
        return math.nan, math.nan, math.nan, 0, 0
    blocks = sorted({row["spatial_block_id"] for row in usable})
    stats = []
    for block in blocks:
        group = [row for row in usable if row["spatial_block_id"] == block]
        stats.append((sum(row["outcome"] * row.get("weight", 1.0) for row in group), sum(row.get("weight", 1.0) for row in group), sum(row["outcome"] * row.get("weight", 1.0) for row in group if int(row["flag"]) == 1), sum(row.get("weight", 1.0) for row in group if int(row["flag"]) == 1)))
    stats_array = np.asarray(stats, float)
    point = enrichment(usable)
    generator = np.random.default_rng(seed)
    values = []
    for _ in range(reps):
        summed = stats_array[generator.integers(0, len(blocks), len(blocks))].sum(axis=0)
        if summed[1] > 0 and summed[3] > 0 and summed[0] > 0:
            values.append(float((summed[2] / summed[3]) / (summed[0] / summed[1])))
    return point, float(np.quantile(values, .025)) if values else math.nan, float(np.quantile(values, .975)) if values else math.nan, len(usable), len(blocks)


def holdout_rows(events: list[dict], pixels: dict[int, dict], scale: str, flag_kind: str) -> list[dict]:
    output = []
    for event in events:
        if event["analysis_period"] != "TEMPORAL_HOLDOUT_2021_2023" or not int(event["temporal_evaluation_eligible"]):
            continue
        outcome = C.finite(event.get("incomplete_recovery_before_next_drought"))
        if not math.isfinite(outcome) or int(event["pixel_id"]) not in pixels:
            continue
        pixel = pixels[int(event["pixel_id"])]
        flag = int(pixel[f"A_{scale}"] or pixel[f"B_{scale}"]) if flag_kind == "single_scale_risk" else int(pixel["risk_consensus_ge2"])
        output.append({"event_id": event["event_id"], "pixel_id": event["pixel_id"], "scale": scale, "outcome": outcome, "flag": flag, "weight": 1.0, "spatial_block_id": event["spatial_block_id"], "prediction": C.finite(event.get("predicted_incomplete_before_next_drought")), "forest_type_group": C.FOREST_LABELS.get(int(event["forest_type"]), "Other forest"), "climate_zone_group": str(event["climate_zone_label"]), "large_region_group": str(event["large_region"])})
    return output


def consensus_validation(events_by_scale: dict[str, list[dict]], pixels: list[dict]) -> None:
    lookup = {int(row["pixel_id"]): row for row in pixels}
    by_scale, all_event_consensus = [], []
    scale_consensus_er = []
    for si, scale in enumerate(C.SCALES):
        for kind in ("single_scale_risk", "consensus_ge2_risk"):
            rows = holdout_rows(events_by_scale[scale], lookup, scale, kind)
            er, low, high, n, blocks = block_bootstrap(rows, C.RNG + si * 10 + (kind == "consensus_ge2_risk"))
            y = np.asarray([row["outcome"] for row in rows]); p = np.asarray([row["prediction"] for row in rows]); ok = np.isfinite(y) & np.isfinite(p)
            auc = float(roc_auc_score(y[ok], p[ok])) if ok.sum() >= 20 and len(np.unique(y[ok])) > 1 else math.nan
            flagged = [row["outcome"] for row in rows if row["flag"] == 1]
            by_scale.append({"spei_timescale": scale, "screen": kind, "n_events": n, "n_spatial_blocks": blocks, "flagged_events": len(flagged), "baseline_incomplete_rate": float(np.mean(y)) if len(y) else math.nan, "flagged_incomplete_rate": float(np.mean(flagged)) if flagged else math.nan, "enrichment_ratio": er, "er_ci_low": low, "er_ci_high": high, "prospective_hazard_auc": auc, "bootstrap_repetitions": 500, "bootstrap_unit": "5-degree spatial block", "scale_pooling": "none"})
            if kind == "consensus_ge2_risk":
                scale_consensus_er.append(er); all_event_consensus.extend(rows)
    C.write_csv(C.RUN / "CONSENSUS_VALIDATION_BY_SCALE.csv", by_scale)
    event_er, event_low, event_high, n_event, n_blocks = block_bootstrap(all_event_consensus, C.RNG + 101)
    event_rows = [
        {"estimand": "POOLED_EVENT_WEIGHTED", "value": event_er, "ci_low": event_low, "ci_high": event_high, "n_units": n_event, "n_spatial_blocks": n_blocks, "interpretation": "each event is one unit; scale event counts are not equalized"},
        {"estimand": "EQUAL_SCALE_MEAN_ER", "value": float(np.nanmean(scale_consensus_er)), "ci_low": math.nan, "ci_high": math.nan, "n_units": 3, "n_spatial_blocks": math.nan, "interpretation": "arithmetic mean of separately validated D1/D3/D6 ERs"},
        {"estimand": "EQUAL_SCALE_MEDIAN_ER", "value": float(np.nanmedian(scale_consensus_er)), "ci_low": math.nan, "ci_high": math.nan, "n_units": 3, "n_spatial_blocks": math.nan, "interpretation": "median of separately validated D1/D3/D6 ERs"},
        {"estimand": "EQUAL_SCALE_RANGE_MIN", "value": float(np.nanmin(scale_consensus_er)), "ci_low": math.nan, "ci_high": math.nan, "n_units": 3, "n_spatial_blocks": math.nan, "interpretation": "minimum separately validated scale ER"},
        {"estimand": "EQUAL_SCALE_RANGE_MAX", "value": float(np.nanmax(scale_consensus_er)), "ci_low": math.nan, "ci_high": math.nan, "n_units": 3, "n_spatial_blocks": math.nan, "interpretation": "maximum separately validated scale ER"},
    ]
    C.write_csv(C.RUN / "CONSENSUS_EVENT_WEIGHTED_VALIDATION.csv", event_rows)
    pixel_outcomes = defaultdict(dict)
    for scale in C.SCALES:
        grouped = defaultdict(list)
        for row in holdout_rows(events_by_scale[scale], lookup, scale, "consensus_ge2_risk"):
            grouped[int(row["pixel_id"])].append(row["outcome"])
        for pid, values in grouped.items(): pixel_outcomes[pid][scale] = float(np.mean(values))
    pixel_rows = []
    for pid, values in pixel_outcomes.items():
        pixel = lookup[pid]
        pixel_rows.append({"pixel_id": pid, "outcome": float(np.mean(list(values.values()))), "flag": int(pixel["risk_consensus_ge2"]), "weight": 1.0, "area_weight": pixel["cell_area_km2"], "spatial_block_id": block_id(pixel["latitude"], pixel["longitude"]), "n_scales": len(values)})
    pixel_er, pixel_low, pixel_high, n_pixel, pixel_blocks = block_bootstrap(pixel_rows, C.RNG + 102)
    C.write_csv(C.RUN / "CONSENSUS_PIXEL_WEIGHTED_VALIDATION.csv", [{"estimand": "PIXEL_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL", "enrichment_ratio": pixel_er, "er_ci_low": pixel_low, "er_ci_high": pixel_high, "n_pixels": n_pixel, "n_spatial_blocks": pixel_blocks, "bootstrap_repetitions": 500, "bootstrap_unit": "5-degree spatial block"}])
    area_rows = [{**row, "weight": row["area_weight"]} for row in pixel_rows]
    area_er, area_low, area_high, n_area, area_blocks = block_bootstrap(area_rows, C.RNG + 103)
    C.write_csv(C.RUN / "CONSENSUS_AREA_WEIGHTED_VALIDATION.csv", [{"estimand": "FOREST_CELL_AREA_WEIGHTED_EQUAL_SCALE_WITHIN_PIXEL", "enrichment_ratio": area_er, "er_ci_low": area_low, "er_ci_high": area_high, "n_pixels": n_area, "n_spatial_blocks": area_blocks, "bootstrap_repetitions": 500, "bootstrap_unit": "5-degree spatial block", "weight_units": "km2"}])


def equal_scale_group_bootstrap(scale_rows: dict[str, list[dict]], seed: int, reps: int = 500) -> tuple[float, float, float]:
    scale_points = [enrichment(scale_rows[scale]) for scale in C.SCALES]
    point = float(np.nanmedian(scale_points)) if any(math.isfinite(x) for x in scale_points) else math.nan
    blocks = sorted({row["spatial_block_id"] for rows in scale_rows.values() for row in rows})
    if not blocks: return point, math.nan, math.nan
    block_pos = {block: i for i, block in enumerate(blocks)}
    stats = np.zeros((3, len(blocks), 4), float)
    for si, scale in enumerate(C.SCALES):
        for row in scale_rows[scale]:
            bi = block_pos[row["spatial_block_id"]]; weight = row.get("weight", 1.0)
            stats[si, bi, 0] += row["outcome"] * weight; stats[si, bi, 1] += weight
            if row["flag"]:
                stats[si, bi, 2] += row["outcome"] * weight; stats[si, bi, 3] += weight
    generator = np.random.default_rng(seed); values = []
    for _ in range(reps):
        selected = generator.integers(0, len(blocks), len(blocks)); estimates = []
        for si in range(3):
            summed = stats[si, selected].sum(axis=0)
            if summed[1] > 0 and summed[3] > 0 and summed[0] > 0:
                estimates.append((summed[2] / summed[3]) / (summed[0] / summed[1]))
        if estimates: values.append(float(np.median(estimates)))
    return point, float(np.quantile(values, .025)) if values else math.nan, float(np.quantile(values, .975)) if values else math.nan


def evidence(events_by_scale: dict[str, list[dict]], pixels: list[dict]) -> list[dict]:
    lookup = {int(row["pixel_id"]): row for row in pixels}
    dimensions = {"forest_type": "forest_type_group", "climate_zone": "climate_zone_group", "large_region": "large_region_group"}
    holdout_cache = {scale: holdout_rows(events_by_scale[scale], lookup, scale, "consensus_ge2_risk") for scale in C.SCALES}
    result = []
    for dimension, group_field in dimensions.items():
        groups = sorted({row[group_field] for rows in holdout_cache.values() for row in rows})
        for group in groups:
            scale_rows, aucs, scale_ns = {}, [], []
            for scale in C.SCALES:
                rows = [row for row in holdout_cache[scale] if row[group_field] == group]
                scale_rows[scale] = rows; scale_ns.append(len(rows))
                y = np.asarray([row["outcome"] for row in rows]); p = np.asarray([row["prediction"] for row in rows]); ok = np.isfinite(y) & np.isfinite(p)
                aucs.append(float(roc_auc_score(y[ok], p[ok])) if ok.sum() >= 20 and len(np.unique(y[ok])) > 1 else math.nan)
            point, low, high = equal_scale_group_bootstrap(scale_rows, C.RNG + zlib.crc32((dimension + group).encode()))
            auc = float(np.nanmedian(aucs)) if any(math.isfinite(x) for x in aucs) else math.nan
            n = sum(scale_ns)
            supported = n >= 300 and math.isfinite(low) and low > 1 and math.isfinite(auc) and auc >= .60
            conditional = n >= 100 and ((math.isfinite(point) and point > 1) or (math.isfinite(auc) and auc >= .60))
            status = "SUPPORTED" if supported else "CONDITIONAL" if conditional else "LIMITED"
            result.append({"group_dimension": dimension, "group": group, "sample_events_total": n, "D1_events": scale_ns[0], "D3_events": scale_ns[1], "D6_events": scale_ns[2], "equal_scale_median_enrichment_ratio": point, "er_5deg_bootstrap_ci_low": low, "er_5deg_bootstrap_ci_high": high, "equal_scale_median_prospective_hazard_auc": auc, "application_evidence_status": status, "status_rule": "SUPPORTED:n>=300&ER_CI_low>1&AUC>=0.60; CONDITIONAL:n>=100&(ER>1|AUC>=0.60); else LIMITED", "independent_dimension": 1})
    result.append({"group_dimension": "pilot_constraint", "group": "Amazon box lon[-75,-50],lat[-15,5]", "sample_events_total": "pilot", "application_evidence_status": "LIMITED", "status_rule": "predeclared TASK0009D negative/weak pilot constraint", "independent_dimension": 1})
    status_lookup = {(row["group_dimension"], row["group"]): row["application_evidence_status"] for row in result}
    audit = []
    for pixel in pixels:
        individual = {
            "forest_type": status_lookup.get(("forest_type", pixel["forest_type_label"]), "LIMITED"),
            "climate_zone": status_lookup.get(("climate_zone", pixel["climate_zone_label"]), "LIMITED"),
            "large_region": status_lookup.get(("large_region", pixel["large_region"]), "LIMITED"),
        }
        amazon = -75 <= pixel["longitude"] <= -50 and -15 <= pixel["latitude"] <= 5
        codes = [STATUS_CODE[value] for value in individual.values()] + ([STATUS_CODE["LIMITED"]] if amazon else [])
        final_code = min(codes)
        final_status = next(label for label, code in STATUS_CODE.items() if code == final_code)
        pixel["evidence_forest_type"] = individual["forest_type"]
        pixel["evidence_climate_zone"] = individual["climate_zone"]
        pixel["evidence_large_region"] = individual["large_region"]
        pixel["amazon_pilot_constraint"] = int(amazon)
        pixel["corrected_application_evidence_status"] = final_status
        audit.append({"pixel_id": pixel["pixel_id"], "latitude": pixel["latitude"], "longitude": pixel["longitude"], "forest_type_status": individual["forest_type"], "climate_zone_status": individual["climate_zone"], "large_region_status": individual["large_region"], "amazon_pilot_constraint": int(amazon), "final_status": final_status, "assignment_rule": "most conservative independent dimension; Amazon box forced LIMITED"})
    C.write_csv(C.RUN / "CORRECTED_APPLICATION_EVIDENCE_STATUS.csv", result)
    C.write_csv(C.RUN / "EVIDENCE_STATUS_ASSIGNMENT_AUDIT.csv", audit)
    return result


def censor_fields(events_by_scale: dict[str, list[dict]], pixels: list[dict]) -> list[dict]:
    summaries = []
    grouped = {scale: defaultdict(list) for scale in C.SCALES}
    for scale in C.SCALES:
        for event in events_by_scale[scale]:
            grouped[scale][int(event["pixel_id"])].append(event)
    for pixel in pixels:
        pid = int(pixel["pixel_id"])
        for period in ("TRAIN", "HOLDOUT", "CURRENT_2024", "ALL"):
            scale_values = []
            for scale in C.SCALES:
                events = grouped[scale].get(pid, [])
                if period == "TRAIN":
                    values = [int(e["right_censored"]) for e in events if e["analysis_period"] == "TRAIN_2001_2020"]
                elif period == "HOLDOUT":
                    values = [int(e["temporal_evaluation_right_censored"]) for e in events if e["analysis_period"] == "TEMPORAL_HOLDOUT_2021_2023" and int(e["temporal_evaluation_eligible"])]
                elif period == "CURRENT_2024":
                    values = [int(e["right_censored"]) for e in events if e["analysis_period"] == "CURRENT_STATUS_2024_CENSOR_ONLY"]
                else:
                    values = [int(e["right_censored"]) for e in events]
                if values: scale_values.append(float(np.mean(values)))
            value = float(np.mean(scale_values)) if scale_values else math.nan
            pixel[f"right_censor_rate_{period.lower()}"] = value
        summaries.append({"pixel_id": pid, "train_right_censor_rate": pixel["right_censor_rate_train"], "holdout_2021_2023_temporal_right_censor_rate": pixel["right_censor_rate_holdout"], "current_2024_right_censor_status": pixel["right_censor_rate_current_2024"], "all_period_right_censor_rate": pixel["right_censor_rate_all"]})
    period_summary = []
    for period, field in (("TRAIN_2001_2020", "right_censor_rate_train"), ("TEMPORAL_HOLDOUT_2021_2023", "right_censor_rate_holdout"), ("CURRENT_2024", "right_censor_rate_current_2024"), ("ALL_2001_2024", "right_censor_rate_all")):
        values = [pixel[field] for pixel in pixels if math.isfinite(pixel[field])]
        period_summary.append({"period": period, "pixels_with_events": len(values), "mean_pixel_right_censor_rate": float(np.mean(values)) if values else math.nan, "median_pixel_right_censor_rate": float(np.median(values)) if values else math.nan, "definition": "equal mean across available D1/D3/D6 pixel-scale rates"})
    C.write_csv(C.RUN / "RIGHT_CENSOR_PIXEL_AUDIT.csv", summaries)
    C.write_csv(C.RUN / "RIGHT_CENSOR_PERIOD_SUMMARY.csv", period_summary)
    return period_summary


def write_tif(name: str, pixels: list[dict], value, dtype: str, nodata, description: str, units: str, definition: str) -> None:
    array = np.full((290, 720), nodata, dtype=np.dtype(dtype))
    for pixel in pixels:
        v = value(pixel)
        if v is not None and math.isfinite(float(v)): array[int(pixel["grid_row"]), int(pixel["grid_col"])] = v
    C.ensure_dir(C.MAPS); C.ensure_dir(C.OUT_MAPS)
    path = C.MAPS / name; C.assert_output(path)
    profile = {"driver": "GTiff", "height": 290, "width": 720, "count": 1, "dtype": dtype, "crs": "EPSG:4326", "transform": from_origin(-180, 85, .5, .5), "nodata": nodata, "compress": "deflate", "tiled": True, "blockxsize": 256, "blockysize": 256}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1); dst.set_band_description(1, description); dst.update_tags(1, units=units, definition=definition); dst.update_tags(TASK="0010C", recovery_definition="R2", source_inputs_read_only="true")
    shutil.copyfile(path, C.OUT_MAPS / name)


def maps(pixels: list[dict]) -> None:
    write_tif("GLOBAL_RISK_PRIORITY_AGREEMENT.tif", pixels, lambda p: p["risk_priority_agreement_count"], "int16", -1, "A/B risk priority agreement", "count", "max A or B agreement across unweighted D1/D3/D6; C excluded")
    write_tif("GLOBAL_MONITORING_PRIORITY_AGREEMENT.tif", pixels, lambda p: p["monitoring_priority_agreement_count"], "int16", -1, "C monitoring priority agreement", "count", "C-only agreement across unweighted D1/D3/D6; A/B excluded")
    write_tif("GLOBAL_RISK_CONSENSUS_CLASS.tif", pixels, lambda p: p["risk_priority_agreement_count"], "int16", -1, "A/B risk consensus class", "code 0-3", "0 none, 1 scale-specific, 2 consensus, 3 robust core")
    write_tif("GLOBAL_MONITORING_CONSENSUS_CLASS.tif", pixels, lambda p: p["monitoring_priority_agreement_count"], "int16", -1, "C monitoring consensus class", "code 0-3", "0 none, 1 scale-specific, 2 consensus, 3 robust core")
    write_tif("CORRECTED_APPLICATION_EVIDENCE_STATUS.tif", pixels, lambda p: STATUS_CODE[p["corrected_application_evidence_status"]], "int16", -1, "corrected application evidence status", "code", "1 LIMITED, 2 CONDITIONAL, 3 SUPPORTED; worst independent dimension; Amazon forced LIMITED")
    write_tif("GLOBAL_CURRENT_2024_CENSOR_STATUS.tif", pixels, lambda p: p["right_censor_rate_current_2024"], "float32", -9999, "current 2024 right censor status", "fraction", "equal-scale mean fraction of 2024-start events unresolved through 2024-12; NoData where no 2024 event")
    write_tif("GLOBAL_ALL_PERIOD_RIGHT_CENSOR_RATE.tif", pixels, lambda p: p["right_censor_rate_all"], "float32", -9999, "all-period right censor rate", "fraction", "equal-scale mean event right-censor rate for 2001-2024 events")
    for scale in C.SCALES:
        write_tif(f"GLOBAL_R2_MEDIAN_RECOVERY_TIME_{scale}.tif", pixels, lambda p, s=scale: p[f"median_complete_recovery_months_{s}"], "float32", -9999, f"R2 median complete recovery time {scale}", "months", "training complete events; from full-drought kNDVI minimum")
    cap = float(np.nanquantile([p["median_complete_recovery_crossscale"] for p in pixels if math.isfinite(p["median_complete_recovery_crossscale"])], .98))
    write_tif("GLOBAL_R2_LONG_RECOVERY_HOTSPOT.tif", pixels, lambda p: int(math.isfinite(p["median_complete_recovery_crossscale"]) and p["median_complete_recovery_crossscale"] > 12), "int16", -1, "long recovery hotspot", "binary", "1 where equal-scale median complete R2 recovery exceeds 12 months")
    C.write_csv(C.RUN / "RECOVERY_MAP_DISPLAY_PARAMETERS.csv", [{"map": "GLOBAL_R2_MEDIAN_RECOVERY_TIME", "display_color_cap_months": cap, "cap_quantile": 0.98, "values_above_cap_preserved_in_data": 1}])


def functional(events_by_scale: dict[str, list[dict]], pixels: list[dict]) -> None:
    lookup = {int(row["pixel_id"]): row for row in pixels}
    events = [event for event in events_by_scale["D3"] if event["analysis_period"] == "TRAIN_2001_2020" and 2004 <= int(event["event_start"][:4]) <= 2018]
    comparisons = [
        ("consensus_risk_ge2_vs_no_risk_consensus", lambda e: lookup[int(e["pixel_id"])]["risk_consensus_ge2"] == 1, lambda e: lookup[int(e["pixel_id"])]["risk_priority_agreement_count"] == 0),
        ("incomplete_vs_recovered_before_next", lambda e: C.finite(e["incomplete_recovery_before_next_drought"]) == 1, lambda e: C.finite(e["incomplete_recovery_before_next_drought"]) == 0),
        ("fire_overlap_vs_none", lambda e: C.finite(e["any_fire_overlap"]) == 1, lambda e: C.finite(e["any_fire_overlap"]) == 0),
        ("intact_vs_nonintact", lambda e: C.finite(e["intact_forest"]) >= .5, lambda e: C.finite(e["intact_forest"]) < .5),
    ]
    output = []
    for mi, metric in enumerate(("gpp_legacy", "npp_legacy")):
        for ci, (label, group_a, group_b) in enumerate(comparisons):
            usable = [e for e in events if int(e["pixel_id"]) in lookup and math.isfinite(C.finite(e[metric])) and (group_a(e) or group_b(e))]
            av = [C.finite(e[metric]) for e in usable if group_a(e)]; bv = [C.finite(e[metric]) for e in usable if group_b(e)]
            blocks = sorted({e["spatial_block_id"] for e in usable}); by_block = {block: [e for e in usable if e["spatial_block_id"] == block] for block in blocks}
            generator = np.random.default_rng(C.RNG + mi * 20 + ci); boot = []
            for _ in range(500):
                draw = [e for block in generator.choice(blocks, len(blocks), replace=True) for e in by_block[str(block)]] if blocks else []
                aa = [C.finite(e[metric]) for e in draw if group_a(e)]; bb = [C.finite(e[metric]) for e in draw if group_b(e)]
                if aa and bb: boot.append(float(np.mean(aa) - np.mean(bb)))
            output.append({"metric": metric, "units": "kg C m-2 yr-1", "comparison": label, "n_a": len(av), "n_b": len(bv), "mean_a": float(np.mean(av)) if av else math.nan, "mean_b": float(np.mean(bv)) if bv else math.nan, "difference_a_minus_b": float(np.mean(av) - np.mean(bv)) if av and bv else math.nan, "ci_low": float(np.quantile(boot, .025)) if boot else math.nan, "ci_high": float(np.quantile(boot, .975)) if boot else math.nan, "bootstrap_repetitions": 500, "bootstrap_unit": "5-degree spatial block", "input_definition": "raw annual post3 mean minus pre3 mean", "eligible_event_years": "2004-2018", "interpretation": "functional association; not causal"})
    C.write_csv(C.RUN / "CORRECTED_GPP_NPP_LEGACY_VALIDATION.csv", output)


def main() -> None:
    pixels = C.load_pickle(C.WORK / "corrected_pixels.pkl")
    events_by_scale = {scale: C.load_pickle(C.WORK / f"events_modeled_{scale}.pkl") for scale in C.SCALES}
    consensus_validation(events_by_scale, pixels)
    evidence_rows = evidence(events_by_scale, pixels)
    censor_summary = censor_fields(events_by_scale, pixels)
    maps(pixels); functional(events_by_scale, pixels)
    C.save_pickle(C.WORK / "corrected_pixels_final.pkl", pixels)
    C.write_csv(C.RUN / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.csv", pixels)
    C.write_parquet(C.RUN / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.parquet", pixels, {"task": "0010C", "recovery": "R2", "evidence": "independent dimensions, conservative assignment"})
    C.write_parquet(C.OUT / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.parquet", pixels, {"task": "0010C", "recovery": "R2", "evidence": "independent dimensions, conservative assignment"})
    for scale, events in events_by_scale.items():
        C.write_parquet(C.RUN / f"CORRECTED_EVENT_LEVEL_R2_{scale}.parquet", events, {"task": "0010C", "recovery_definition": "R2", "models": "frozen prospective RF and discrete hazard"})
        C.write_parquet(C.OUT / f"CORRECTED_EVENT_LEVEL_R2_{scale}.parquet", events, {"task": "0010C", "recovery_definition": "R2", "models": "frozen prospective RF and discrete hazard"})
    C.write_text(C.RUN / "RIGHT_CENSOR_MAP_AUDIT.md", "# Right-censor map audit\n\nFour censor populations are kept separate: fixed 2001-2020 training, locked 2021-2023 temporal evaluation (censored at 2023-12), current 2024 events (status through 2024-12), and all detected 2001-2024 events (status through 2024-12). The current map is NoData for pixels without a 2024-start event; zero means observed recovery, not missingness. Rates are computed within scale first and then equally averaged across available D1/D3/D6 scales. No training-only zero surface is presented as a global censor map.\n")
    C.write_text(C.RUN / "DOMINANT_DRIVER_MAP_AUDIT.md", "# Dominant driver map audit\n\n**Option B selected: no corrected dominant-driver map is produced.** TASK0010A's global surface assigned one globally ranked variable to every forest pixel and therefore contained no local attribution. TASK0010C does not claim local drivers and does not reproduce, rename or replace that constant map. Variable associations remain model-level diagnostics only.\n")
    C.write_text(C.RUN / "PRIORITY_MAP_SEPARATION_AUDIT.md", "# Risk and monitoring map separation\n\nPriority A and B are risk-screening classes and are combined only for the risk agreement and consensus products. Priority C is a monitoring class and appears only in the monitoring agreement and consensus products. No figure panel or raster merges C with A/B risk. These are screening candidates, not intervention effects.\n")
    C.write_json(C.RUN / "CHECKPOINT_04_CONSENSUS_MAPS.json", {"status": "PASS", "evidence_groups": len(evidence_rows), "censor_periods": len(censor_summary), "maps": 11, "completed_utc": C.utc()})
    C.log("consensus validation, evidence, censor, maps and functional legacy complete")
    print({"status": "PASS", "pixels": len(pixels), "evidence_groups": len(evidence_rows)})


if __name__ == "__main__":
    main()
