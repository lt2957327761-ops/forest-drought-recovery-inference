from __future__ import annotations

import argparse
import math
import pickle

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import task0010c_core as C
from task0010c_dryrun import PROSPECTIVE_FEATURES, RETROSPECTIVE_ONLY


NUMERIC_PROSPECTIVE = [x for x in PROSPECTIVE_FEATURES if x not in ("forest_type", "climate_zone")]
NUMERIC_RETROSPECTIVE = NUMERIC_PROSPECTIVE + RETROSPECTIVE_ONLY


def matrix(rows: list[dict], features: list[str]) -> tuple[np.ndarray, list[str]]:
    names = list(features) + [f"forest_type_{x}" for x in C.FOREST_TYPES] + [f"climate_zone_{x}" for x in range(1, 6)]
    X = np.full((len(rows), len(names)), np.nan, float)
    for i, row in enumerate(rows):
        for j, feature in enumerate(features):
            X[i, j] = C.finite(row.get(feature))
        offset = len(features)
        forest_type = int(C.finite(row.get("forest_type"))) if math.isfinite(C.finite(row.get("forest_type"))) else -1
        for code in C.FOREST_TYPES:
            X[i, offset] = int(forest_type == code); offset += 1
        climate = int(C.finite(row.get("climate_zone"))) if math.isfinite(C.finite(row.get("climate_zone"))) else -1
        for code in range(1, 6):
            X[i, offset] = int(climate == code); offset += 1
    return X, names


def rf(seed: int) -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=1.0, bootstrap=True, n_jobs=-1, random_state=seed)


def regression_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    ok = np.isfinite(y) & np.isfinite(p)
    if ok.sum() < 2:
        return {"r2": math.nan, "rmse": math.nan, "mae": math.nan, "spearman": math.nan}
    rho = spearmanr(y[ok], p[ok]).statistic
    return {"r2": float(r2_score(y[ok], p[ok])), "rmse": float(math.sqrt(mean_squared_error(y[ok], p[ok]))), "mae": float(mean_absolute_error(y[ok], p[ok])), "spearman": float(rho) if math.isfinite(float(rho)) else math.nan}


def hazard_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    ok = np.isfinite(p)
    y, p = y[ok].astype(int), p[ok]
    if len(y) < 20 or len(np.unique(y)) < 2:
        return {"hazard_auc": math.nan, "pr_auc": math.nan, "brier_score": math.nan}
    return {"hazard_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "brier_score": float(brier_score_loss(y, p))}


def months_between(start: str, end: str) -> int:
    return C.month_index(end) - C.month_index(start)


def hazard_data(rows: list[dict], features: list[str], temporal: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    base, _ = matrix(rows, features)
    complete_base = np.all(np.isfinite(base), axis=1)
    durations, recovered, kept = [], [], []
    for i, row in enumerate(rows):
        if not complete_base[i]:
            continue
        end = C.month_index(row["event_end"])
        if temporal:
            if not int(row.get("temporal_evaluation_eligible", 0)):
                continue
            censored = int(row["temporal_evaluation_right_censored"])
            duration = C.VALIDATION_END - end if censored else C.finite(row["recovery_time_from_drought_end_months"])
        else:
            censored = int(row["right_censored"])
            duration = C.month_index(row["last_observed_month"]) - end if censored else C.finite(row["recovery_time_from_drought_end_months"])
        if not math.isfinite(duration) or duration < 1:
            continue
        kept.append(i); durations.append(int(round(duration))); recovered.append(1 - censored)
    if not kept:
        return np.empty((0, base.shape[1] + 2)), np.empty(0, np.int8), np.empty(0, int)
    rep = np.repeat(np.arange(len(kept)), durations)
    month = np.concatenate([np.arange(1, duration + 1, dtype=float) for duration in durations])
    X = np.column_stack([base[np.asarray(kept)[rep]], month, np.log1p(month)])
    y = np.zeros(len(rep), np.int8)
    cursor = 0
    for duration, did_recover in zip(durations, recovered):
        if did_recover:
            y[cursor + duration - 1] = 1
        cursor += duration
    return X, y, np.asarray(kept)[rep]


def event_incomplete_probability(model, rows: list[dict], features: list[str]) -> np.ndarray:
    base, _ = matrix(rows, features)
    output = np.full(len(rows), np.nan)
    for i, row in enumerate(rows):
        interval = C.finite(row.get("next_drought_interval_months"))
        if not math.isfinite(interval) or interval < 1 or not np.all(np.isfinite(base[i])):
            continue
        horizon = max(1, min(240, int(round(interval))))
        month = np.arange(1, horizon + 1, dtype=float)
        X = np.column_stack([np.repeat(base[i][None], horizon, axis=0), month, np.log1p(month)])
        probability = model.predict_proba(X)[:, 1]
        output[i] = float(np.prod(1 - probability))
    return output


def complete_regression_rows(rows: list[dict], features: list[str]) -> tuple[list[dict], np.ndarray, np.ndarray]:
    complete = [row for row in rows if int(row["right_censored"]) == 0]
    X, _ = matrix(complete, features)
    y = np.asarray([C.finite(row["recovery_time_from_drought_end_months"]) for row in complete])
    keep = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    return [row for row, flag in zip(complete, keep) if flag], X[keep], y[keep]


def fit_scale(scale: str, events: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    train = [row for row in events if row["analysis_period"] == "TRAIN_2001_2020"]
    holdout = [row for row in events if row["analysis_period"] == "TEMPORAL_HOLDOUT_2021_2023" and int(row["temporal_evaluation_eligible"]) == 1]
    train_complete, X, y = complete_regression_rows(train, NUMERIC_PROSPECTIVE)
    groups = np.asarray([row["spatial_block_id"] for row in train_complete])
    spatial, temporal, biome = [], [], []
    for fold, (fit, test) in enumerate(GroupKFold(5).split(X, y, groups), 1):
        model = rf(C.RNG + fold); model.fit(X[fit], y[fit]); pred = model.predict(X[test])
        spatial.append({"spei_timescale": scale, "fold": fold, "model_type": "PROSPECTIVE_RF_COMPLETE_RECOVERY", "recovery_definition": "R2", "time_origin": "drought_end", "n_train": len(fit), "n_test": len(test), **regression_metrics(y[test], pred)})
    final_rf = rf(C.RNG); final_rf.fit(X, y)
    hold_complete, HX, hy = complete_regression_rows([row for row in holdout if int(row["temporal_evaluation_right_censored"]) == 0], NUMERIC_PROSPECTIVE)
    hp = final_rf.predict(HX) if len(HX) else np.asarray([])
    temporal.append({"spei_timescale": scale, "group_dimension": "GLOBAL", "group": "GLOBAL", "model_type": "PROSPECTIVE_RF_COMPLETE_RECOVERY", "recovery_definition": "R2", "time_origin": "drought_end", "n_train": len(y), "n_test": len(hy), **regression_metrics(hy, hp)})
    numeric_full, _ = matrix(events, NUMERIC_PROSPECTIVE)
    valid = np.all(np.isfinite(numeric_full), axis=1)
    predicted = np.full(len(events), np.nan)
    if valid.any(): predicted[valid] = final_rf.predict(numeric_full[valid])
    for row, value in zip(events, predicted):
        row["predicted_recovery_time"] = row["predicted_recovery_time_months"] = float(value) if math.isfinite(value) else math.nan
        row["prediction_context"] = "FROZEN_PROSPECTIVE_R2"
    hazard_X, hazard_y, hazard_idx = hazard_data(train, NUMERIC_PROSPECTIVE)
    hazard_groups = np.asarray([train[i]["spatial_block_id"] for i in hazard_idx])
    for fold, (fit, test) in enumerate(GroupKFold(5).split(hazard_X, hazard_y, hazard_groups), 1):
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=C.RNG + fold))
        model.fit(hazard_X[fit], hazard_y[fit]); pred = model.predict_proba(hazard_X[test])[:, 1]
        spatial.append({"spei_timescale": scale, "fold": fold, "model_type": "PROSPECTIVE_DISCRETE_TIME_HAZARD", "recovery_definition": "R2", "time_origin": "drought_end", "n_train": len(fit), "n_test": len(test), **hazard_metrics(hazard_y[test], pred)})
    final_hazard = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=C.RNG))
    final_hazard.fit(hazard_X, hazard_y)
    hold_X, hold_y, hold_idx = hazard_data(holdout, NUMERIC_PROSPECTIVE, temporal=True)
    hold_pred = final_hazard.predict_proba(hold_X)[:, 1] if len(hold_X) else np.asarray([])
    temporal.append({"spei_timescale": scale, "group_dimension": "GLOBAL", "group": "GLOBAL", "model_type": "PROSPECTIVE_DISCRETE_TIME_HAZARD", "recovery_definition": "R2", "time_origin": "drought_end", "n_train": len(hazard_y), "n_test": len(hold_y), **hazard_metrics(hold_y, hold_pred)})
    incomplete_prediction = event_incomplete_probability(final_hazard, events, NUMERIC_PROSPECTIVE)
    for row, value in zip(events, incomplete_prediction):
        row["predicted_incomplete_before_next_drought"] = float(value) if math.isfinite(value) else math.nan
    # Frozen retrospective association RF: spatial-block validation only.
    retro_complete, RX, ry = complete_regression_rows(train, NUMERIC_RETROSPECTIVE)
    retro_groups = np.asarray([row["spatial_block_id"] for row in retro_complete])
    for fold, (fit, test) in enumerate(GroupKFold(5).split(RX, ry, retro_groups), 1):
        model = rf(C.RNG + 100 + fold); model.fit(RX[fit], ry[fit]); pred = model.predict(RX[test])
        spatial.append({"spei_timescale": scale, "fold": fold, "model_type": "RETROSPECTIVE_ASSOCIATION_RF", "recovery_definition": "R2", "time_origin": "drought_end", "n_train": len(fit), "n_test": len(test), **regression_metrics(ry[test], pred), "temporal_prediction_authorized": 0})
    # Forest type is the only independent categorical vegetation grouping; no duplicate biome holdout.
    for code in C.FOREST_TYPES:
        label = C.FOREST_LABELS[code]
        fit_rows = [row for row in train if int(row["forest_type"]) != code]
        test_rows = [row for row in train if int(row["forest_type"]) == code]
        fr, FX, fy = complete_regression_rows(fit_rows, NUMERIC_PROSPECTIVE)
        tr, TX, ty = complete_regression_rows(test_rows, NUMERIC_PROSPECTIVE)
        if len(fy) >= 200 and len(ty) >= 50:
            model = rf(C.RNG + 500 + code); model.fit(FX, fy); pred = model.predict(TX)
            biome.append({"spei_timescale": scale, "held_dimension": "forest_type", "held_group": label, "model_type": "PROSPECTIVE_RF_COMPLETE_RECOVERY", "n_train": len(fy), "n_test": len(ty), **regression_metrics(ty, pred), "biome_duplicate_removed": 1})
        fHX, fHy, _ = hazard_data(fit_rows, NUMERIC_PROSPECTIVE)
        tHX, tHy, _ = hazard_data(test_rows, NUMERIC_PROSPECTIVE)
        if len(fHy) >= 500 and len(tHy) >= 20 and len(np.unique(tHy)) > 1:
            model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=C.RNG + 500 + code))
            model.fit(fHX, fHy); pred = model.predict_proba(tHX)[:, 1]
            biome.append({"spei_timescale": scale, "held_dimension": "forest_type", "held_group": label, "model_type": "PROSPECTIVE_DISCRETE_TIME_HAZARD", "n_train": len(fHy), "n_test": len(tHy), **hazard_metrics(tHy, pred), "biome_duplicate_removed": 1})
    C.assert_output(C.RUN / f"CORRECTED_MODEL_{scale}_RF.pkl")
    with (C.RUN / f"CORRECTED_MODEL_{scale}_RF.pkl").open("wb") as handle:
        pickle.dump({"model": final_rf, "numeric_features": NUMERIC_PROSPECTIVE, "categorical_features": ["forest_type", "climate_zone"], "definition": "R2", "time_origin": "drought_end"}, handle, protocol=5)
    with (C.RUN / f"CORRECTED_MODEL_{scale}_HAZARD.pkl").open("wb") as handle:
        pickle.dump({"model": final_hazard, "numeric_features": NUMERIC_PROSPECTIVE, "categorical_features": ["forest_type", "climate_zone"], "time_features": ["month_since_drought_end", "log1p_month_since_drought_end"], "definition": "R2"}, handle, protocol=5)
    freeze = {"spei_timescale": scale, "main_recovery": "R2", "sensitivity_recovery": "R1", "rf_parameters": "n_estimators=300|min_samples_leaf=5|max_features=1.0|bootstrap=True", "hazard_parameters": "StandardScaler|LogisticRegression|max_iter=1000", "random_seed": C.RNG, "prospective_numeric_features": "|".join(NUMERIC_PROSPECTIVE), "prospective_categorical_features": "forest_type|climate_zone", "hazard_time_features": "month_since_drought_end|log1p_month_since_drought_end", "rf_train_complete_n": len(y), "hazard_train_month_n": len(hazard_y), "tuning_performed": 0}
    return events, spatial, temporal, biome, freeze


def run_one(scale: str) -> None:
        events = C.load_pickle(C.WORK / f"events_corrected_{scale}.pkl")
        events, spatial, temporal, biome, freeze = fit_scale(scale, events)
        C.save_pickle(C.WORK / f"events_modeled_{scale}.pkl", events)
        C.write_csv(C.WORK / f"spatial_{scale}.csv", spatial)
        C.write_csv(C.WORK / f"temporal_{scale}.csv", temporal)
        C.write_csv(C.WORK / f"biome_{scale}.csv", biome)
        C.write_csv(C.WORK / f"freeze_{scale}.csv", [freeze])
        C.log(f"models complete {scale}")


def assemble() -> None:
    all_spatial, all_temporal, all_biome, freezes = [], [], [], []
    for scale in C.SCALES:
        all_spatial.extend(C.read_csv(C.WORK / f"spatial_{scale}.csv"))
        all_temporal.extend(C.read_csv(C.WORK / f"temporal_{scale}.csv"))
        all_biome.extend(C.read_csv(C.WORK / f"biome_{scale}.csv"))
        freezes.extend(C.read_csv(C.WORK / f"freeze_{scale}.csv"))
    C.write_csv(C.RUN / "CORRECTED_SPATIAL_BLOCK_VALIDATION.csv", all_spatial)
    C.write_csv(C.RUN / "CORRECTED_TEMPORAL_HOLDOUT_VALIDATION.csv", all_temporal)
    C.write_csv(C.RUN / "CORRECTED_BIOME_HOLDOUT_VALIDATION.csv", all_biome)
    C.write_csv(C.RUN / "CORRECTED_MODEL_FREEZE_RECORD.csv", freezes)
    C.write_text(C.RUN / "CORRECTED_MODEL_VALIDATION_NOTES.md", """# Corrected model validation notes

All model types, random seed and RF hyperparameters are frozen from TASK0010A. The only changes are the predeclared R2 outcome/time origin and removal of unavailable-at-drought-end predictors from the prospective models. Missing rows are dropped; no interpolation or imputation is used.

The prospective RF predicts complete recovery time measured from drought end. The discrete-time logistic hazard uses prospective static/event-end predictors plus month since drought end and log1p(month). The retrospective association RF adds recovery-period features and is evaluated only by within-training 5-degree spatial block folds. It is not a temporal prediction model.

`CORRECTED_BIOME_HOLDOUT_VALIDATION.csv` uses forest type as the independent vegetation grouping. The duplicate `biome` label from TASK0010A was removed because it was exactly a relabeling of forest type.
""")
    C.write_json(C.RUN / "CHECKPOINT_03_CORRECTED_MODELS.json", {"status": "PASS", "spatial_rows": len(all_spatial), "temporal_rows": len(all_temporal), "forest_type_holdout_rows": len(all_biome), "completed_utc": C.utc()})
    C.log("corrected frozen model validation complete")
    print({"status": "PASS", "spatial": len(all_spatial), "temporal": len(all_temporal), "biome": len(all_biome)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=C.SCALES)
    parser.add_argument("--assemble", action="store_true")
    args = parser.parse_args()
    if args.scale:
        run_one(args.scale)
        print({"status": "PASS", "scale": args.scale})
    elif args.assemble:
        assemble()
    else:
        for scale in C.SCALES:
            run_one(scale)
        assemble()


if __name__ == "__main__":
    main()
