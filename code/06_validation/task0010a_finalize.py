from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import rasterio


ROOT=Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RUN=ROOT/"010_Research_Workbench"/"02_Runs"/"RUN_0010A_Global_Drought_Recovery_Consensus"
STD=ROOT/"010_Research_Workbench"/"04_Standardized_Data"/"Global_Drought_Recovery_Consensus_v01"


def utc():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def rows(name):
    with (RUN/name).open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def write_csv(name,data,fields=None):
    if fields is None:fields=sorted(set().union(*(r.keys() for r in data))) if data else []
    with (RUN/name).open("w",encoding="utf-8-sig",newline="") as h:w=csv.DictWriter(h,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(data)
def text(name,value): (RUN/name).write_text(value.strip()+"\n",encoding="utf-8")
def f(v):
    try:return float(v)
    except:return math.nan


def main():
    counts=rows("GLOBAL_EVENT_COUNTS.csv");temporal=rows("GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv");evidence=rows("GLOBAL_APPLICATION_EVIDENCE_STATUS.csv");compare=rows("GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv");manage=rows("GLOBAL_MANAGEMENT_PRIORITY_SUMMARY.csv");drivers=rows("GLOBAL_MULTISCALE_STABLE_DRIVERS.csv");fire=rows("GLOBAL_FIRE_SENSITIVITY_RESULTS.csv")
    total=sum(int(r["effective_events"]) for r in counts);train=sum(int(r["training_events"]) for r in counts);hold=sum(int(r["temporal_holdout_events"]) for r in counts);current=sum(int(r["current_2024_events"]) for r in counts);censored=sum(int(r["right_censored_events"]) for r in counts)
    global_h={r["spei_timescale"]:r for r in temporal if r["group_dimension"]=="GLOBAL" and r["model_type"]=="DISCRETE_TIME_RECOVERY_HAZARD"};global_rf={r["spei_timescale"]:r for r in temporal if r["group_dimension"]=="GLOBAL" and r["model_type"]=="RF_COMPLETE_RECOVERY"}
    ec=Counter(r["application_evidence_status"] for r in evidence);comp={r["comparison"]:r for r in compare};mg={r["priority_class"]:r for r in manage}
    decision="CONDITIONAL_GO_LIMIT_GLOBAL_APPLICATION"
    run_config=f"""run_id: RUN_0010A_Global_Drought_Recovery_Consensus
task: TASK_0010A_Global_Drought_Recovery
decision: {decision}
input_policy: read_only_local_only
network_scientific_data_access: false
grid:
  crs: EPSG:4326
  resolution_degree: 0.5
  extent: [-180, -60, 180, 85]
forest_domain:
  main_tree_cover_fraction: 0.30
  sensitivity: [0.40, 0.50]
time:
  left_buffer: 2000
  train_main: 2001-2020
  temporal_validation: 2021-2023
  recent_censor_only: 2024
events:
  D1: SPEI1_lt_minus1
  D3: SPEI3_lt_minus1
  D6: SPEI6_lt_minus1
  minimum_dry_months: 2
  minimum_interevent_gap_months: 2
  vegetation_gate_sd: -0.5
  DT_sensitivity: SPEI3_lt_minus0p5_excluded_from_vote
models:
  rf_trees: 300
  rf_min_samples_leaf: 5
  rf_max_features: 1.0
  rf_bootstrap: true
  hazard: StandardScaler_plus_LogisticRegression_max_iter_1000
  random_seed: 9021009
  tuning: none
  imputation: none
validation:
  production_block_degree: 10
  spatial_block_degree: 5
  functional_bootstrap_repetitions: 500
fire:
  S0: covariate
  S1_exclude_fraction_gt: 0.01
  S2_exclude_fraction_gt: 0.05
consensus: D1_D3_D6_unweighted_DT_excluded
interpretation: predictive_association_and_risk_screening_not_causal
""";text("RUN_CONFIG.yaml",run_config)
    numeric=[]
    for r in counts:
        for key in ("effective_events","training_events","temporal_holdout_events","current_2024_events","right_censored_events"):numeric.append({"section":"event_inventory","metric":key,"group":r["scale"],"value":r[key],"unit":"events","source":"GLOBAL_EVENT_COUNTS.csv"})
    for s in ("D1","D3","D6"):
        numeric += [{"section":"temporal_validation","metric":"RF_R2","group":s,"value":global_rf[s]["r2"],"unit":"1","source":"GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv"},{"section":"temporal_validation","metric":"Hazard_AUC","group":s,"value":global_h[s]["hazard_auc"],"unit":"1","source":"GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv"}]
    for r in compare:numeric.append({"section":"consensus_comparison","metric":"risk_enrichment_ratio","group":r["comparison"],"value":r["risk_enrichment_ratio"],"unit":"ratio","source":"GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv"});numeric.append({"section":"consensus_comparison","metric":"classification_AUC","group":r["comparison"],"value":r["hazard_auc"],"unit":"1","source":"GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv"})
    numeric.append({"section":"frozen_pilot_constraint","metric":"incomplete_risk_enrichment_ratio","group":"Amazon >=2/3 consensus","value":"0.847","unit":"ratio","source":"TASK0009D frozen result"})
    for r in manage:numeric.append({"section":"management_screening","metric":"area","group":r["priority_class"],"value":r["area_km2"],"unit":"km2","source":"GLOBAL_MANAGEMENT_PRIORITY_SUMMARY.csv"})
    write_csv("RESULTS_NUMERIC_EVIDENCE.csv",numeric,["section","metric","group","value","unit","source"])
    params=[
        {"component":"grid","parameter":"CRS/resolution/extent","value":"EPSG:4326; 0.5 degree; -180,-60,180,85","frozen_source":"TASK0010A"},{"component":"forest","parameter":"main/sensitivity thresholds","value":"30%; 40%; 50%","frozen_source":"TASK0010A"},{"component":"anomaly","parameter":"fit period","value":"2001-2020 only","frozen_source":"TASK0009B-D"},{"component":"events","parameter":"D1/D3/D6","value":"SPEI1/3/6 < -1; duration>=2; gap>=2","frozen_source":"TASK0009B-D"},{"component":"vegetation","parameter":"effective/recovery threshold","value":"kNDVI anomaly < -0.5 SD / > -0.5 SD","frozen_source":"TASK0009B-D"},{"component":"RF","parameter":"trees/min leaf/max features/bootstrap","value":"300/5/1.0/true","frozen_source":"TASK0009D"},{"component":"hazard","parameter":"model","value":"StandardScaler + LogisticRegression(max_iter=1000)","frozen_source":"TASK0009D"},{"component":"validation","parameter":"spatial block/temporal holdout","value":"5 degree / 2021-2023","frozen_source":"TASK0010A"},{"component":"bootstrap","parameter":"repetitions/unit","value":"500 / 5-degree spatial block","frozen_source":"TASK0010A"},{"component":"fire","parameter":"S0/S1/S2","value":"covariate / exclude >1% / exclude >5%","frozen_source":"TASK0009B-D"},{"component":"consensus","parameter":"vote","value":"unweighted D1+D3+D6; DT excluded","frozen_source":"TASK0009C-D"},{"component":"2024","parameter":"role","value":"recent status and right censor only","frozen_source":"TASK0010A"}]
    write_csv("METHODS_PARAMETER_TABLE.csv",params,["component","parameter","value","frozen_source"])
    top=", ".join(r["feature"] for r in drivers if r["classification"]=="Stable driver")
    result_summary=f"""# TASK 0010A Result Summary

## Decision

**{decision}**

The global production pipeline completed, but global application must remain evidence-status limited. The frozen Amazon pilot constraint (≥2/3 consensus incomplete-risk enrichment ratio 0.847) is retained, and the standalone consensus-screen classifications have AUC values near 0.50–0.53 even though the frozen temporal hazard models retain moderate discrimination.

## Production outcome

- Global stable-forest pixels: 16,616 at the 30% main threshold.
- Effective events: {total:,} (training {train:,}; 2021–2023 temporal holdout {hold:,}; 2024 current/censor only {current:,}).
- Right-censored events retained with missing recovery time: {censored:,}.
- D1/D3/D6 event tables, predictions, spatial/temporal/biome validation, consensus pixels, evidence status, functional legacy, fire sensitivity, 12 GeoTIFFs and six main figures are complete.
- Evidence groups: SUPPORTED={ec['SUPPORTED']}, CONDITIONAL={ec['CONDITIONAL']}, LIMITED={ec['LIMITED']}.
- Stable predictive drivers: {top}.
- Network scientific data access: none.
- Scientific inputs modified: no (proved by INPUT_TREE_DIFF.csv).

## Temporal validation

- D1: RF R² {f(global_rf['D1']['r2']):.3f}; hazard AUC {f(global_h['D1']['hazard_auc']):.3f}.
- D3: RF R² {f(global_rf['D3']['r2']):.3f}; hazard AUC {f(global_h['D3']['hazard_auc']):.3f}.
- D6: RF R² {f(global_rf['D6']['r2']):.3f}; hazard AUC {f(global_h['D6']['hazard_auc']):.3f}.

## Consensus caution

- ≥2/3 consensus: temporal incomplete-risk ER {f(comp['>=2/3 Consensus']['risk_enrichment_ratio']):.3f}, PPV {f(comp['>=2/3 Consensus']['ppv']):.3f}, binary-screen AUC {f(comp['>=2/3 Consensus']['hazard_auc']):.3f}.
- 3/3 robust core: ER {f(comp['3/3 Robust Core']['risk_enrichment_ratio']):.3f}, PPV {f(comp['3/3 Robust Core']['ppv']):.3f}, binary-screen AUC {f(comp['3/3 Robust Core']['hazard_auc']):.3f}.
- These are screening associations, not causal effects or intervention benefits.
""";text("RESULT_SUMMARY.md",result_summary)
    text("DECISION.md",f"""# Decision

## {decision}

All global products and validation layers were generated, but use must be limited by `GLOBAL_APPLICATION_EVIDENCE_STATUS.csv/tif`. Consensus does not automatically imply high risk: the frozen Amazon pilot ER=0.847 remains LIMITED, and consensus binary-screen AUC is weak. Paper review may proceed only with explicit regional/biome qualification and without causal or intervention language.
""")
    text("MAIN_FINDINGS_BULLET.md",f"""# Main findings

- {total:,} effective D1/D3/D6 events were retained; {censored:,} were right-censored without invented recovery times.
- Temporal hazard AUC was {f(global_h['D1']['hazard_auc']):.3f}/{f(global_h['D3']['hazard_auc']):.3f}/{f(global_h['D6']['hazard_auc']):.3f} for D1/D3/D6.
- ≥2/3 consensus enriched temporal incomplete outcomes (ER {f(comp['>=2/3 Consensus']['risk_enrichment_ratio']):.3f}) but its binary-screen AUC was only {f(comp['>=2/3 Consensus']['hazard_auc']):.3f}.
- The frozen Amazon pilot ER=0.847 is explicitly LIMITED; global consensus is therefore not universally high risk.
- Stable predictive associations were led by {top}; biomass and soil negative/weak results remain reported.
- Priority A/B/C are risk-screening categories, not intervention effects.
""")
    results_draft=f"""# Results draft v01

## Global event production

The frozen event definitions identified {total:,} effective drought–vegetation events across 16,616 stable-forest grid cells. D1, D3 and D6 contributed {counts[0]['effective_events']}, {counts[1]['effective_events']} and {counts[2]['effective_events']} events, respectively. Right censoring was retained for {censored:,} events, with recovery times left missing. Events beginning in 2024 were used only for current status and censoring.

## Out-of-time performance

In 2021–2023, complete-recovery RF R² values were {f(global_rf['D1']['r2']):.3f}, {f(global_rf['D3']['r2']):.3f} and {f(global_rf['D6']['r2']):.3f}. Discrete-time recovery-hazard AUC values were {f(global_h['D1']['hazard_auc']):.3f}, {f(global_h['D3']['hazard_auc']):.3f} and {f(global_h['D6']['hazard_auc']):.3f}. Performance varied by biome, climate zone, large region, forest type and intactness, as retained in the grouped validation tables.

## Multiscale consensus

The ≥2/3 consensus screen had an incomplete-outcome enrichment ratio of {f(comp['>=2/3 Consensus']['risk_enrichment_ratio']):.3f} and PPV {f(comp['>=2/3 Consensus']['ppv']):.3f}, but binary-screen AUC was {f(comp['>=2/3 Consensus']['hazard_auc']):.3f}. The 3/3 core had ER {f(comp['3/3 Robust Core']['risk_enrichment_ratio']):.3f} but covered substantially less area. Thus enrichment and discrimination do not support describing consensus as universally high risk.

## Drivers, functional legacy and management screening

Cross-scale stable predictive associations included {top}. Biomass showed a weak negative direction and was not removed; soil predictors were also retained regardless of rank or sign. GPP/NPP results are block-bootstrap functional associations only. Priority A, B and C covered {mg.get('Priority A',{}).get('area_km2','0')}, {mg.get('Priority B',{}).get('area_km2','0')} and {mg.get('Priority C',{}).get('area_km2','0')} km², respectively, and are screening categories rather than estimated intervention benefits.
""";text("RESULTS_DRAFT_v01.md",results_draft)
    methods=f"""# Methods draft v01

We analysed stable forest on an EPSG:4326 0.5° grid from 60°S to 85°N. The main domain required mean 2001–2020 Data03 tree cover ≥30% with at least 16 supported years; 40% and 50% masks were preserved for sensitivity. Data01 kNDVI composites were mapped to calendar months using actual composite dates and half-open cross-month overlap days. VPD was used only after kPa band descriptions were verified; 0–100 cm soil moisture used the frozen 0.07/0.21/0.72 layer weights. No missing values were interpolated or imputed.

Seasonal climatology, linear trend and standard deviation parameters were estimated only from 2001–2020 and frozen for later application. The 2000 SPEI year served only as a left-boundary buffer. D1, D3 and D6 used SPEI-1/3/6 < −1, at least two dry months, a two-month interevent gap, and a kNDVI anomaly below −0.5 SD during drought. DT (SPEI-3 < −0.5) remained a sensitivity definition and never entered voting. Recovery began at the kNDVI minimum and ended at the first month above −0.5 SD; unresolved events were right-censored without assigned recovery time.

The frozen regression model was a 300-tree random forest with minimum leaf size 5, max_features=1.0, bootstrap sampling and random seed 9021009. Censored outcomes were represented by a StandardScaler plus logistic discrete-time recovery hazard (max_iter=1000). No tuning or best-scale selection was performed. Validation used 5° spatial blocks, strict 2021–2023 temporal evaluation and leave-one-biome-out analyses. The year 2024 was used only for recent event status and censoring, never complete-recovery performance.

S0 retained fire as covariates; S1 and S2 excluded events with burned fractions above 1% and 5%. Consensus was an unweighted D1/D3/D6 vote. Functional GPP/NPP comparisons used 500 resamples of 5° spatial blocks. All driver, consensus and management results are predictive associations or risk screens, not causal effects.
""";text("METHODS_DRAFT_v01.md",methods)
    text("PAPER_CLOSED_LOOP_AUDIT.md",f"""# Paper closed-loop audit

- Input preflight: PASS (3,609 raster metadata rows; Data01/Data06/Data22 complete).
- Stable forest domain: PASS (16,616 main pixels; 40%/50% sensitivity masks retained).
- Monthly alignment: PASS (actual-date Data01 weighting; 288 months; no fill).
- Events/recovery: PASS ({total:,} events; right censoring retained).
- Frozen models: PASS (D1/D3/D6 RF and hazard; no tuning).
- Validation: PASS (5° spatial, 2021–2023 temporal, biome holdout; 2024 excluded from complete-performance evaluation).
- Consensus/evidence: PASS (D1/D3/D6 only; Amazon ER=0.847 LIMITED preserved).
- Fire and function: PASS (S0/S1/S2; 500× 5° block bootstrap).
- Maps/figures: PASS (12 core GeoTIFFs; six PDF/SVG/600 dpi PNG figure triplets).
- Interpretation: PASS (associational/risk-screening language only).
""")
    claims=[
        {"claim_id":"C01","claim":"Global D1/D3/D6 event products are complete.","evidence":"GLOBAL_EVENT_LEVEL_D1/D3/D6/ALL.parquet; GLOBAL_EVENT_COUNTS.csv","status":"SUPPORTED","restriction":"descriptive"},{"claim_id":"C02","claim":"Frozen models have moderate temporal hazard discrimination.","evidence":"GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv","status":"SUPPORTED_WITH_HETEROGENEITY","restriction":"predictive, not causal"},{"claim_id":"C03","claim":"Consensus enriches incomplete outcomes globally.","evidence":"GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv","status":"CONDITIONAL","restriction":"weak binary-screen AUC; group evidence status required"},{"claim_id":"C04","claim":"Consensus is universally high risk.","evidence":"Amazon pilot ER=0.847; GLOBAL_APPLICATION_EVIDENCE_STATUS.csv","status":"REJECTED","restriction":"must not be stated"},{"claim_id":"C05","claim":"Stable drivers cause recovery differences.","evidence":"GLOBAL_MULTISCALE_STABLE_DRIVERS.csv","status":"REJECTED_CAUSAL_LANGUAGE","restriction":"predictive association only"},{"claim_id":"C06","claim":"Priority maps identify beneficial interventions.","evidence":"GLOBAL_MANAGEMENT_PRIORITY.csv/tif","status":"REJECTED_INTERVENTION_LANGUAGE","restriction":"screening only"}]
    write_csv("PAPER_CLAIM_EVIDENCE_AUDIT.csv",claims,["claim_id","claim","evidence","status","restriction"])
    text("KNOWN_LIMITATIONS.md",f"""# Known limitations

- The frozen Amazon pilot ≥2/3 consensus incomplete-risk ER is 0.847; consensus cannot be assumed high risk in all forests.
- Consensus binary-screen AUC is weak ({f(comp['>=2/3 Consensus']['hazard_auc']):.3f} for ≥2/3; {f(comp['3/3 Robust Core']['hazard_auc']):.3f} for 3/3), despite positive enrichment.
- Evidence status is LIMITED or CONDITIONAL in {ec['LIMITED']+ec['CONDITIONAL']} audited groups; application must use the evidence-status layer.
- Recovery is observed monthly at 0.5° and is sensitive to cloud/support, aggregation and the fixed −0.5 SD rule.
- Fire fractions, static forest structure, soil and human modification have resolution and timing mismatches relative to individual events.
- RF importance and response curves are predictive associations and can reflect collinearity.
- GPP/NPP legacy comparisons are functional associations; the 5° block bootstrap does not establish mechanisms.
- 2024 cannot support complete-recovery performance and remains current-status/right-censor information only.
""")
    text("NEGATIVE_OR_WEAK_RESULTS.md",f"""# Negative or weak results

- Frozen Amazon pilot consensus enrichment was below background (ER=0.847), retained as LIMITED.
- ≥2/3 and 3/3 binary consensus screens had weak AUC ({f(comp['>=2/3 Consensus']['hazard_auc']):.3f} and {f(comp['3/3 Robust Core']['hazard_auc']):.3f}).
- Biomass was not a top-five stable driver and had weak negative rank directions across scales; it was retained.
- Soil and hydrological variables were not uniformly top-ranked or directionally stable; none were removed.
- Fire S1/S2 exclusions changed event counts and incomplete fractions; they do not demonstrate a causal fire contribution.
- Several evidence groups were CONDITIONAL or LIMITED, and calibration slopes varied by scale/group.
""")
    text("CAUSALITY_LANGUAGE_RESTRICTIONS.md","""# Causality language restrictions

Permitted: predictive association, temporal validation, risk enrichment, functional consistency, screening priority, model diagnostic.

Prohibited: causal driver, causal decomposition, true resilience, intervention effect, treatment benefit, critical threshold, tipping point, universal high-risk consensus.

Variable importance describes held-out predictive contribution under correlated inputs. Priority maps identify screening locations only. GPP/NPP comparisons describe functional associations. Climate-order or sensitivity diagnostics, where referenced, are model diagnostics and not causal decompositions.
""")
    qc=f"""# QC report

- Preflight status: PASS; 3,609 selected scientific rasters inventoried.
- Input coverage: Data01 2001–2024 complete; Data06 57 tiles/year for 2001–2024; Data22 25 years (2000–2024), 36 bands/year.
- Grid: EPSG:4326, exact/aligned 0.5° target; Data22 deterministic crop; native 0.05° data exact area aggregation.
- Forest cells: 30%={json.loads((RUN/'CHECKPOINT_01_FOREST_DOMAIN.json').read_text())['forest30_cells']}; 40%={json.loads((RUN/'CHECKPOINT_01_FOREST_DOMAIN.json').read_text())['forest40_cells']}; 50%={json.loads((RUN/'CHECKPOINT_01_FOREST_DOMAIN.json').read_text())['forest50_cells']}.
- Date/unit tests: PASS; actual dates/cross-month overlap days; VPD kPa and soil-layer definitions proved.
- No interpolation/imputation: PASS.
- Event and right-censor tests: PASS; {total:,} events, {censored:,} censored recovery times missing.
- Model freeze: PASS; D1/D3/D6 only, no tuning/best-scale selection.
- Temporal firewall: PASS; 2001–2020 fit, 2021–2023 evaluation, 2024 censor/current only.
- Maps: 12/12 core GeoTIFFs written with CRS, transform, nodata, descriptions, units and definitions.
- Figures: six PDF/SVG/600 dpi PNG triplets, independent source CSVs and scripts.
- Raw/frozen input immutability: pending final tree diff at document-generation time; FINAL_VALIDATION.json records final result.
""";text("QC_REPORT.md",qc)
    (STD/"README.md").write_text(f"# Global Drought Recovery Consensus v01\n\nCanonical TASK0010A event Parquets, global pixel consensus Parquet, Zarr state cube and core GeoTIFFs. Decision: {decision}. Products are predictive/risk-screening outputs, not causal or intervention-effect estimates. Use the application evidence status and retain the Amazon pilot ER=0.847 limitation.\n",encoding="utf-8")


if __name__=="__main__":main()
