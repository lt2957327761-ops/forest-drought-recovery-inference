from __future__ import annotations

import copy
import math
import shutil
import warnings
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from scipy.stats import spearmanr

import task0010c_core as C


def frozen_standardize(values: np.ndarray, minimum: int = 160) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    train = values[: C.TRAIN_END]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        climatology = np.nanmean(train.reshape(20, 12, train.shape[1]), axis=0)
    deseasoned = values - np.tile(climatology, (24, 1))
    yt = deseasoned[: C.TRAIN_END]
    t = np.arange(C.TRAIN_END, dtype=np.float64)[:, None]
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
    residual = deseasoned - (intercept[None] + slope[None] * np.arange(C.TOTAL_MONTHS)[:, None])
    residual[~np.isfinite(values)] = np.nan
    sd = np.nanstd(residual[: C.TRAIN_END], axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = residual / sd[None]
    out[:, ~good | ~np.isfinite(sd) | (sd <= 0)] = np.nan
    return out.astype(np.float32)


def corrected_climate_arrays() -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for name in ("soil_moisture", "vpd", "temperature", "precipitation"):
        path = C.WORK / f"standardized_{name}.npy"
        if not path.exists():
            raw = np.load(C.CACHE / f"global_{name}.npy", mmap_mode="r")
            standardized = frozen_standardize(raw)
            C.assert_output(path)
            np.save(path, standardized)
            del standardized
        arrays[name] = np.load(path, mmap_mode="r")
    return arrays


def mean_or_nan(values: np.ndarray) -> float:
    return float(np.nanmean(values)) if np.isfinite(values).any() else math.nan


def correct_event(event: dict, anomaly: np.ndarray, pixel_index: int, climate: dict[str, np.ndarray], fire: np.ndarray, fire_support: np.ndarray, gpp: np.ndarray, npp: np.ndarray) -> dict:
    out = copy.deepcopy(event)
    start = C.month_index(event["event_start"])
    end = C.month_index(event["event_end"])
    interval = C.finite(event.get("next_drought_interval_months"))
    next_start = end + int(round(interval)) if math.isfinite(interval) else None
    old = C.current_recovery(anomaly[:, pixel_index], start, end, next_start)
    r1 = C.corrected_recovery(anomaly[:, pixel_index], start, end, next_start, "R1")
    r2 = C.corrected_recovery(anomaly[:, pixel_index], start, end, next_start, "R2")
    if old is None or r1 is None or r2 is None:
        raise RuntimeError(f"Recovery reconstruction failed for {event['event_id']}")
    for key in (
        "recovery_start", "recovery_end", "observed_recovery_time_months", "recovery_time_from_minimum_months",
        "recovery_time_from_drought_end_months", "censored_followup_months", "right_censored", "last_observed_month",
        "recovered_before_next_drought", "incomplete_recovery_before_next_drought", "analysis_period",
    ):
        out[f"old_{key}"] = event.get(key, "")
    C.update_event_with_definition(out, old, "old_reconstructed")
    C.update_event_with_definition(out, r1, "r1")
    C.update_event_with_definition(out, r2, "r2")
    out["recovery_definition_main"] = "R2"
    out["recovery_start"] = C.month_label(r2["minimum"])
    out["recovery_end"] = C.month_label(r2["recovery"]) if r2["recovery"] is not None else ""
    out["observed_recovery_time_months"] = r2["recovery_from_minimum"]
    out["recovery_time_from_minimum_months"] = r2["recovery_from_minimum"]
    out["recovery_time_from_drought_end_months"] = r2["recovery_from_drought_end"]
    out["censored_followup_months"] = r2["censored_followup"]
    out["right_censored"] = r2["right_censored"]
    out["last_observed_month"] = C.month_label(r2["censor"])
    out["recovered_before_next_drought"] = r2["recovered_before_next"]
    out["incomplete_recovery_before_next_drought"] = r2["incomplete_before_next"]
    out["early_recovery_before_drought_end"] = r2["early_before_drought_end"]
    stop = r2["recovery"] if r2["recovery"] is not None else r2["censor"]
    period = C.analysis_period(start, stop)
    out["analysis_period"] = period
    out["train_or_holdout"] = period
    out["temporal_evaluation_eligible"] = int(C.TRAIN_END <= start <= C.VALIDATION_END and end <= C.VALIDATION_END)
    out["temporal_evaluation_right_censored"] = int(out["temporal_evaluation_eligible"] and (r2["recovery"] is None or r2["recovery"] > C.VALIDATION_END))
    out["temporal_evaluation_recovery_time_from_drought_end_months"] = (
        float(r2["recovery"] - end) if out["temporal_evaluation_eligible"] and not out["temporal_evaluation_right_censored"] else math.nan
    )
    recovery_stop = r2["recovery"] if r2["recovery"] is not None else r2["censor"]
    sl = slice(r2["minimum"], recovery_stop + 1)
    aliases = {
        "soil_moisture": ("recovery_period_soil_moisture", "recovery_period_soil_moisture_mean_anomaly"),
        "vpd": ("recovery_period_vpd", "recovery_period_VPD_mean_anomaly"),
        "temperature": ("recovery_period_temperature", "recovery_period_temperature_mean_anomaly"),
        "precipitation": ("recovery_period_precipitation", "recovery_period_precipitation_mean_anomaly"),
    }
    for name, fields in aliases.items():
        value = mean_or_nan(climate[name][sl, pixel_index])
        for field in fields:
            out[field] = value
    combined = fire[start : recovery_stop + 1, pixel_index]
    recovery_fire = fire[r2["minimum"] : recovery_stop + 1, pixel_index]
    support = fire_support[start : recovery_stop + 1, pixel_index]
    out["burned_fraction_during_recovery"] = float(np.nansum(recovery_fire)) if np.isfinite(recovery_fire).any() else math.nan
    out["max_monthly_burned_fraction"] = float(np.nanmax(combined)) if np.isfinite(combined).any() else math.nan
    out["cumulative_burned_fraction"] = float(np.nansum(combined)) if np.isfinite(combined).any() else math.nan
    out["fire_overlap_months"] = int(np.sum(np.isfinite(combined) & (combined > 0))) if np.isfinite(combined).any() else math.nan
    out["any_fire_overlap"] = int(np.any(np.isfinite(combined) & (combined > 0))) if np.isfinite(combined).any() else math.nan
    out["fire_valid_support"] = mean_or_nan(support)
    year_index = 2001 + start // 12 - 2001
    for metric, annual in (("gpp_legacy", gpp), ("npp_legacy", npp)):
        value = math.nan
        if 3 <= year_index and year_index + 2 < annual.shape[0]:
            before = np.asarray(annual[year_index - 3 : year_index, pixel_index], float)
            after = np.asarray(annual[year_index : year_index + 3, pixel_index], float)
            if np.isfinite(before).all() and np.isfinite(after).all():
                value = float(after.mean() - before.mean())
        out[metric] = value
    out["gpp_npp_legacy_definition"] = "raw annual post3 mean minus pre3 mean; kg C m-2 yr-1"
    for field in ("predicted_recovery_time", "predicted_recovery_time_months", "predicted_hazard", "predicted_recovery_probability", "predicted_incomplete_before_next_drought"):
        out[field] = math.nan
    return out


def build_pixel_table(events_by_scale: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    pixels = C.base_pixel_rows()
    groups = {scale: defaultdict(list) for scale in C.SCALES}
    for scale, events in events_by_scale.items():
        for event in events:
            if event["analysis_period"] == "TRAIN_2001_2020":
                groups[scale][int(event["pixel_id"])].append(event)
    biomass_q = float(np.nanquantile([row["biomass"] for row in pixels], 0.75))
    hm_q = float(np.nanquantile([row["human_modification"] for row in pixels], 0.75))
    threshold_rows = []
    for scale in C.SCALES:
        for row in pixels:
            events = groups[scale].get(row["pixel_id"], [])
            burden = [C.finite(e["recovery_time_from_minimum_months"]) if int(e["right_censored"]) == 0 else C.finite(e["censored_followup_months"]) for e in events]
            burden = [x for x in burden if math.isfinite(x)]
            complete = [C.finite(e["recovery_time_from_minimum_months"]) for e in events if int(e["right_censored"]) == 0 and math.isfinite(C.finite(e["recovery_time_from_minimum_months"]))]
            incomplete = [C.finite(e["incomplete_recovery_before_next_drought"]) for e in events if math.isfinite(C.finite(e["incomplete_recovery_before_next_drought"]))]
            row[f"event_count_{scale}"] = len(events)
            row[f"median_recovery_burden_months_{scale}"] = float(np.median(burden)) if burden else math.nan
            row[f"median_complete_recovery_months_{scale}"] = float(np.median(complete)) if complete else math.nan
            row[f"right_censor_rate_{scale}"] = float(np.mean([e["right_censored"] for e in events])) if events else math.nan
            row[f"incomplete_fraction_{scale}"] = float(np.mean(incomplete)) if incomplete else math.nan
            row[f"recurrence_per_decade_{scale}"] = len(events) / 2.0
        finite_burden = [row[f"median_recovery_burden_months_{scale}"] for row in pixels if math.isfinite(row[f"median_recovery_burden_months_{scale}"])]
        global_slow = float(np.quantile(finite_burden, 0.75))
        recurrence_q = float(np.quantile([row[f"recurrence_per_decade_{scale}"] for row in pixels], 0.75))
        by_type = {}
        for code in C.FOREST_TYPES:
            values = [row[f"median_recovery_burden_months_{scale}"] for row in pixels if row["forest_type"] == code and math.isfinite(row[f"median_recovery_burden_months_{scale}"])]
            if len(values) >= 20:
                by_type[code] = float(np.quantile(values, 0.75))
        threshold_rows.append({"scale": scale, "slow_global_p75_months": global_slow, "recurrence_global_p75_events_decade": recurrence_q, "biomass_global_p75": biomass_q, "human_modification_global_p75": hm_q, "forest_type_slow_thresholds": "|".join(f"{k}:{v:.6g}" for k, v in sorted(by_type.items())), "frozen_rule": "TASK0010A unchanged"})
        for row in pixels:
            slow = math.isfinite(row[f"median_recovery_burden_months_{scale}"]) and row[f"median_recovery_burden_months_{scale}"] >= by_type.get(row["forest_type"], global_slow)
            incomplete = math.isfinite(row[f"incomplete_fraction_{scale}"]) and row[f"incomplete_fraction_{scale}"] > 0
            high_biomass = math.isfinite(row["biomass"]) and row["biomass"] >= biomass_q
            intact = math.isfinite(row["intact_forest"]) and row["intact_forest"] >= 0.5
            high_hm = math.isfinite(row["human_modification"]) and row["human_modification"] >= hm_q
            recurrent = row[f"recurrence_per_decade_{scale}"] >= recurrence_q
            row[f"slow_recovery_{scale}"] = int(slow)
            row[f"incomplete_recovery_{scale}"] = int(incomplete)
            row[f"high_recurrence_{scale}"] = int(recurrent)
            row[f"A_{scale}"] = int(slow and incomplete and high_biomass and intact)
            row[f"B_{scale}"] = int(slow and incomplete and (high_hm or not intact))
            row[f"C_{scale}"] = int((not slow) and recurrent and row[f"event_count_{scale}"] > 0)
    for row in pixels:
        for label in "ABC":
            row[f"priority_agreement_count_{label}"] = sum(row[f"{label}_{scale}"] for scale in C.SCALES)
            row[f"priority_consensus_class_{label}"] = C.CONS_LABEL[row[f"priority_agreement_count_{label}"]]
        row["risk_priority_agreement_count"] = max(row["priority_agreement_count_A"], row["priority_agreement_count_B"])
        row["monitoring_priority_agreement_count"] = row["priority_agreement_count_C"]
        row["risk_consensus_class"] = C.CONS_LABEL[row["risk_priority_agreement_count"]]
        row["monitoring_consensus_class"] = C.CONS_LABEL[row["monitoring_priority_agreement_count"]]
        row["risk_priority_type"] = "Priority A" if row["priority_agreement_count_A"] >= row["priority_agreement_count_B"] and row["priority_agreement_count_A"] > 0 else "Priority B" if row["priority_agreement_count_B"] > 0 else "None"
        row["risk_consensus_ge2"] = int(row["risk_priority_agreement_count"] >= 2)
        row["risk_robust_3of3"] = int(row["risk_priority_agreement_count"] == 3)
        row["monitoring_consensus_ge2"] = int(row["monitoring_priority_agreement_count"] >= 2)
        row["median_recovery_burden_crossscale"] = float(np.nanmedian([row[f"median_recovery_burden_months_{s}"] for s in C.SCALES]))
        row["median_complete_recovery_crossscale"] = float(np.nanmedian([row[f"median_complete_recovery_months_{s}"] for s in C.SCALES]))
        row["right_censor_crossscale_train"] = float(np.nanmean([row[f"right_censor_rate_{s}"] for s in C.SCALES]))
        row["risk_screening_only"] = 1
        row["priority_rule"] = "TASK0010A thresholds unchanged; A/B risk separated from C monitoring"
    return pixels, threshold_rows


def summaries(events_by_scale: dict[str, list[dict]], pixels: list[dict]) -> None:
    comparison, distribution, early = [], [], []
    for scale, events in events_by_scale.items():
        for definition, prefix in (("OLD", "old_reconstructed"), ("R1", "r1"), ("R2", "r2")):
            times = np.asarray([C.finite(e[f"{prefix}_recovery_time_from_minimum_months"]) for e in events], float)
            complete = times[np.isfinite(times)]
            censored = np.asarray([int(e[f"{prefix}_right_censored"]) for e in events])
            incomplete = np.asarray([C.finite(e[f"{prefix}_incomplete_recovery_before_next_drought"]) for e in events], float)
            earlies = np.asarray([int(e[f"{prefix}_early_recovery_before_drought_end"]) for e in events])
            comparison.append({"scale": scale, "definition": definition, "event_count": len(events), "complete_recovery_count": len(complete), "right_censored_count": int(censored.sum()), "right_censor_rate": float(censored.mean()), "early_recovery_count": int(earlies.sum()), "early_recovery_rate": float(earlies.mean()), "incomplete_before_next_count": int(np.nansum(incomplete)), "incomplete_before_next_rate": float(np.nanmean(incomplete)), "median_recovery_months": float(np.median(complete)) if len(complete) else math.nan, "mean_recovery_months": float(np.mean(complete)) if len(complete) else math.nan})
            for quantile in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.98, 0.99, 1):
                distribution.append({"scale": scale, "definition": definition, "quantile": quantile, "recovery_time_months": float(np.quantile(complete, quantile)) if len(complete) else math.nan, "n_complete": len(complete)})
            early.append({"scale": scale, "definition": definition, "event_count": len(events), "early_count": int(earlies.sum()), "early_fraction": float(earlies.mean()), "rule": "recovery month <= drought end month"})
    old_pixels = {int(row["pixel_id"]): row for row in C.read_csv(C.SRC / "GLOBAL_PIXEL_MULTISCALE_PRIORITY.csv")}
    for scale in C.SCALES:
        oldv, newv = [], []
        field_old = f"median_complete_recovery_months_{scale}"
        field_new = f"median_complete_recovery_months_{scale}"
        for row in pixels:
            ov = C.finite(old_pixels.get(row["pixel_id"], {}).get(field_old))
            nv = C.finite(row[field_new])
            if math.isfinite(ov) and math.isfinite(nv):
                oldv.append(ov); newv.append(nv)
        rho = float(spearmanr(oldv, newv).statistic) if len(oldv) > 2 else math.nan
        comparison.append({"scale": scale, "definition": "OLD_VS_R2_PIXEL_MAP", "event_count": len(oldv), "map_spearman": rho, "note": "pixel median complete-recovery maps"})
    C.write_csv(C.RUN / "OLD_VS_R1_VS_R2_RECOVERY_COMPARISON.csv", comparison)
    C.write_csv(C.RUN / "RECOVERY_TIME_DISTRIBUTION.csv", distribution)
    C.write_csv(C.RUN / "EARLY_RECOVERY_BEFORE_DROUGHT_END.csv", early)


def examples(events_by_scale: dict[str, list[dict]], anomaly: np.ndarray, spei: dict[str, np.ndarray], pixel_lookup: dict[int, int]) -> None:
    candidates = []
    for scale, events in events_by_scale.items():
        changed = [e for e in events if e["old_reconstructed_recovery_month"] != e["r2_recovery_month"] or int(e["old_reconstructed_early_recovery_before_drought_end"]) == 1]
        chosen = changed[:34 if scale == "D1" else 33]
        candidates.extend(chosen)
    if len(candidates) < 100:
        used = {e["event_id"] for e in candidates}
        for scale in C.SCALES:
            for event in events_by_scale[scale]:
                if event["event_id"] not in used:
                    candidates.append(event); used.add(event["event_id"])
                    if len(candidates) >= 100: break
            if len(candidates) >= 100: break
    candidates = candidates[:100]
    detail = []
    for number, event in enumerate(candidates, 1):
        idx = pixel_lookup[int(event["pixel_id"])]
        start, end = C.month_index(event["event_start"]), C.month_index(event["event_end"])
        markers = {
            "event_start": start, "event_end": end,
            "old_minimum": C.month_index(event["old_reconstructed_minimum_month"]),
            "old_recovery": C.month_index(event["old_reconstructed_recovery_month"]) if event["old_reconstructed_recovery_month"] else None,
            "r1_minimum": C.month_index(event["r1_minimum_month"]),
            "r1_recovery": C.month_index(event["r1_recovery_month"]) if event["r1_recovery_month"] else None,
            "r2_minimum": C.month_index(event["r2_minimum_month"]),
            "r2_recovery": C.month_index(event["r2_recovery_month"]) if event["r2_recovery_month"] else None,
        }
        finite_markers = [value for value in markers.values() if value is not None]
        lo, hi = max(0, min(finite_markers) - 3), min(C.TOTAL_MONTHS - 1, max(finite_markers) + 3)
        for month in range(lo, hi + 1):
            detail.append({"example_number": number, "event_id": event["event_id"], "spei_timescale": event["spei_timescale"], "pixel_id": event["pixel_id"], "latitude": event["lat"], "longitude": event["lon"], "month": C.month_label(month), "month_index": month, "relative_to_drought_end_months": month - end, "SPEI": C.finite(spei[event["spei_timescale"]][month + 12, idx]), "kNDVI_anomaly_sd": C.finite(anomaly[month, idx]), **{f"{name}_flag": int(value == month) if value is not None else 0 for name, value in markers.items()}})
    C.write_csv(C.RUN / "RECOVERY_ALGORITHM_EXAMPLES.csv", detail)
    pdf = C.RUN / "RECOVERY_ALGORITHM_EXAMPLES.pdf"
    C.assert_output(pdf)
    with PdfPages(pdf) as pages:
        for offset in range(0, len(candidates), 4):
            fig, axes = plt.subplots(4, 1, figsize=(11, 8.5), constrained_layout=True)
            for ax, event in zip(axes, candidates[offset : offset + 4]):
                idx = pixel_lookup[int(event["pixel_id"])]
                rows = [r for r in detail if r["event_id"] == event["event_id"]]
                x = np.asarray([r["month_index"] for r in rows])
                y = np.asarray([r["kNDVI_anomaly_sd"] for r in rows])
                s = np.asarray([r["SPEI"] for r in rows])
                ax.plot(x, y, color="#146C94", lw=1.5, marker="o", ms=2.5, label="kNDVI anomaly")
                ax.plot(x, s, color="#777777", lw=1.0, alpha=.7, label="SPEI")
                ax.axhline(-.5, color="#B22222", ls="--", lw=.8)
                colors = {"event_start": "#333333", "event_end": "#333333", "old_recovery": "#E69F00", "r1_recovery": "#009E73", "r2_recovery": "#CC79A7", "r2_minimum": "#0072B2"}
                for name, color in colors.items():
                    value = next((r["month_index"] for r in rows if r.get(f"{name}_flag") == 1), None)
                    if value is not None: ax.axvline(value, color=color, lw=1, ls=":" if "recovery" in name else "-")
                ax.set_title(f"{event['event_id']} | {event['lat']:.2f}, {event['lon']:.2f} | OLD={event['old_reconstructed_recovery_month'] or 'censored'} R1={event['r1_recovery_month'] or 'censored'} R2={event['r2_recovery_month'] or 'censored'}", fontsize=8)
                ax.set_xticks(x[::max(1, len(x)//8)], [C.month_label(int(v)) for v in x[::max(1, len(x)//8)]], rotation=25, fontsize=6)
                ax.tick_params(axis="y", labelsize=7)
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=7)
            fig.suptitle("Recovery algorithm audit examples: monthly SPEI and kNDVI", fontsize=12)
            pages.savefig(fig)
            plt.close(fig)


def main() -> None:
    C.ensure_dir(C.WORK); C.ensure_dir(C.OUT)
    climate = corrected_climate_arrays()
    anomaly = np.load(C.CACHE / "global_kndvi_anomaly.npy", mmap_mode="r")
    fire = np.load(C.CACHE / "global_burned_fraction.npy", mmap_mode="r")
    fire_support = np.load(C.CACHE / "global_fire_support.npy", mmap_mode="r")
    gpp = np.load(C.CACHE / "global_annual_gpp.npy", mmap_mode="r")
    npp = np.load(C.CACHE / "global_annual_npp.npy", mmap_mode="r")
    rows = np.load(C.CACHE / "forest_rows.npy"); cols = np.load(C.CACHE / "forest_cols.npy")
    pixel_lookup = {int(row) * C.WIDTH + int(col): index for index, (row, col) in enumerate(zip(rows, cols))}
    events_by_scale = {}
    for scale in C.SCALES:
        source = C.load_pickle(C.CACHE / f"events_{scale}.pkl")
        corrected = [correct_event(event, anomaly, pixel_lookup[int(event["pixel_id"])], climate, fire, fire_support, gpp, npp) for event in source]
        events_by_scale[scale] = corrected
        C.save_pickle(C.WORK / f"events_corrected_{scale}.pkl", corrected)
        C.write_parquet(C.RUN / f"CORRECTED_EVENT_LEVEL_R2_{scale}.parquet", corrected, {"task": "0010C", "recovery_definition": "R2", "source": "TASK0010A event detection; corrected recovery only"})
        C.write_parquet(C.OUT / f"CORRECTED_EVENT_LEVEL_R2_{scale}.parquet", corrected, {"task": "0010C", "recovery_definition": "R2", "source": "TASK0010A event detection; corrected recovery only"})
        C.log(f"corrected {scale}: {len(corrected)} events")
    pixels, thresholds = build_pixel_table(events_by_scale)
    C.save_pickle(C.WORK / "corrected_pixels.pkl", pixels)
    C.write_csv(C.RUN / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.csv", pixels)
    C.write_parquet(C.RUN / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.parquet", pixels, {"task": "0010C", "priority": "A/B risk separated from C monitoring"})
    C.write_parquet(C.OUT / "CORRECTED_PIXEL_MULTISCALE_PRIORITY.parquet", pixels, {"task": "0010C", "priority": "A/B risk separated from C monitoring"})
    C.write_csv(C.RUN / "FROZEN_PRIORITY_THRESHOLDS.csv", thresholds)
    summaries(events_by_scale, pixels)
    spei = {scale: np.load(C.CACHE / f"global_spei{scale[-1]}.npy", mmap_mode="r") for scale in C.SCALES}
    examples(events_by_scale, anomaly, spei, pixel_lookup)
    early_rows = C.read_csv(C.RUN / "EARLY_RECOVERY_BEFORE_DROUGHT_END.csv")
    old_early = sum(int(float(row["early_count"])) for row in early_rows if row["definition"] == "OLD")
    r2_early = sum(int(float(row["early_count"])) for row in early_rows if row["definition"] == "R2")
    C.write_text(C.RUN / "RECOVERY_ALGORITHM_AUDIT.md", f"""# Recovery algorithm audit

## Reconstructed old algorithm

The frozen TASK0010A implementation located the first kNDVI anomaly below -0.5 during the drought, then searched immediately for the first later value above -0.5. It selected the minimum only up to that first crossing. This allowed recovery inside an ongoing meteorological drought, could ignore a later deeper vegetation loss within the same drought, and accepted a one-month crossing without persistence.

## Corrected definitions

- **R1 sensitivity:** find the minimum over the complete meteorological drought interval; search for the first finite kNDVI anomaly above -0.5 after that minimum.
- **R2 main:** find the same full-drought minimum; do not start the recovery search before the month after drought end; use the first finite kNDVI anomaly above -0.5.
- Events without a crossing remain right-censored and have missing recovery time. No fixed recovery duration is assigned.

R2 was declared the main definition before inspecting performance. R1 is a sensitivity analysis only. Neither threshold nor model hyperparameters were tuned.

## Audit result

Across D1/D3/D6, the reconstructed old rule produced {old_early:,} recovery declarations on or before drought end; R2 produced {r2_early:,}. The 100-event monthly audit CSV and its 25-page PDF expose drought boundaries, full-drought minima and OLD/R1/R2 crossings. The event detector itself was frozen, so recovery correction changes timing/censor outcomes rather than meteorological drought detection.
""")
    priority_a = sum(int(row["priority_agreement_count_A"]) >= 2 for row in pixels)
    C.write_text(C.RUN / "PRIORITY_A_SMALL_SAMPLE_AUDIT.md", f"# Priority A small-sample audit\n\nThe frozen TASK0010A thresholds and hierarchy were applied unchanged to corrected R2 outcomes. The corrected global grid contains **{priority_a}** pixels meeting Priority A at >=2 of 3 SPEI scales. This remains a strict candidate core and is not described as a spatially supported global intervention class. Thresholds were not relaxed.\n")
    C.write_json(C.RUN / "CHECKPOINT_02_CORRECTED_EVENTS.json", {"status": "PASS", "events": {s: len(v) for s, v in events_by_scale.items()}, "pixels": len(pixels), "completed_utc": C.utc()})
    C.log("event correction, comparisons, examples and pixel priorities complete")
    print({"status": "PASS", "events": {s: len(v) for s, v in events_by_scale.items()}, "pixels": len(pixels)})


if __name__ == "__main__":
    main()
