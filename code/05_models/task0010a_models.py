from __future__ import annotations

import csv
import json
import math
import pickle
import shutil
import sys
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Iterable, Sequence

import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RUN = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0010A_Global_Drought_Recovery_Consensus"
STD = ROOT / "010_Research_Workbench" / "04_Standardized_Data" / "Global_Drought_Recovery_Consensus_v01"
CACHE = RUN / "_processing_cache"
MAPS = RUN / "FINAL_MAP_RASTERS"
STD_MAPS = STD / "FINAL_MAP_RASTERS"
for path in (MAPS, STD_MAPS): path.mkdir(parents=True, exist_ok=True)
REF4 = ROOT / "010_Research_Workbench" / "02_Runs" / "RUN_0004_Three_Region_Benchmark_Dynamics"
sys.path.insert(0, str(REF4))
import task0004_lib as P  # noqa: E402
P.RUN_ROOT, P.OUTPUT_ROOT = RUN, STD

RNG = 9021009
SCALES = ["D1","D3","D6"]
FOREST_TYPES = [1,2,3,4,5]
BASE_FEATURES = ["drought_duration_months","minimum_SPEI","cumulative_SPEI_deficit","kNDVI_loss_amplitude_sd","antecedent_drought_frequency_5yr","interval_since_previous_drought_months","recovery_period_soil_moisture_mean_anomaly","recovery_period_VPD_mean_anomaly","recovery_period_temperature_mean_anomaly","recovery_period_precipitation_mean_anomaly","burned_fraction_during_drought","burned_fraction_during_recovery","max_monthly_burned_fraction","cumulative_burned_fraction","fire_overlap_months","fire_valid_support","forest_cover","biomass","canopy_height","field_capacity_100cm","clay_100cm","sand_100cm","elevation","slope","human_modification","intact_forest"]
HAZARD_FEATURES = ["drought_duration_months","minimum_SPEI","cumulative_SPEI_deficit","kNDVI_loss_amplitude_sd","antecedent_drought_frequency_5yr","interval_since_previous_drought_months","burned_fraction_during_drought","max_monthly_burned_fraction","fire_valid_support","forest_cover","biomass","canopy_height","field_capacity_100cm","clay_100cm","sand_100cm","elevation","slope","human_modification","intact_forest"]
REQUIRED = ["drought_duration_months","minimum_SPEI","cumulative_SPEI_deficit","kNDVI_loss_amplitude_sd","burned_fraction_during_drought","fire_valid_support"]
CONS_LABEL = {3:"3/3 Robust Core",2:"2/3 Consensus only",1:"1/3 Scale-specific",0:"0/3 None"}


def utc(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def finite(v):
    try: x=float(v)
    except Exception: return math.nan
    return x if math.isfinite(x) else math.nan
def write_csv(path:Path, rows:Sequence[dict], fields:Sequence[str]|None=None):
    if fields is None: fields=sorted(set().union(*(r.keys() for r in rows))) if rows else []
    with path.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(fields),extrasaction="ignore"); w.writeheader(); w.writerows(rows)
def infer_columns(rows:Sequence[dict], fields:Sequence[str]):
    out={}
    for f in fields:
        vals=[r.get(f,"") for r in rows]; num=[]; bad=False; missing=False
        for v in vals:
            if v is None or v=="": num.append(math.nan); missing=True; continue
            if isinstance(v,str): bad=True; break
            try:num.append(float(v))
            except Exception:bad=True;break
        if bad: out[f]=["" if v is None else str(v) for v in vals]
        elif not missing and all(math.isfinite(x) and x.is_integer() for x in num):out[f]=np.asarray(num,np.int64)
        else:out[f]=np.asarray(num,float)
    return out


def select_features(rows, candidates):
    selected=[f for f in candidates if np.mean([math.isfinite(finite(r.get(f))) for r in rows])>=.80]
    missing=[f for f in REQUIRED if f not in selected]
    if missing: raise RuntimeError(f"Frozen required features below 80%: {missing}")
    return selected


def matrix(rows, features):
    names=list(features)+[f"forest_type_{x}" for x in FOREST_TYPES]+[f"climate_zone_{x}" for x in range(1,6)]
    X=np.full((len(rows),len(names)),np.nan,float)
    for i,r in enumerate(rows):
        for j,f in enumerate(features):X[i,j]=finite(r.get(f))
        off=len(features); ft=int(finite(r.get("forest_type"))) if math.isfinite(finite(r.get("forest_type"))) else -1
        for code in FOREST_TYPES:X[i,off]=int(ft==code);off+=1
        cz=int(finite(r.get("climate_zone"))) if math.isfinite(finite(r.get("climate_zone"))) else -1
        for code in range(1,6):X[i,off]=int(cz==code);off+=1
    return X,names


def rf_model(seed=RNG): return RandomForestRegressor(n_estimators=300,min_samples_leaf=5,max_features=1.0,bootstrap=True,n_jobs=-1,random_state=seed)
def reg_metrics(y,p):
    ok=np.isfinite(y)&np.isfinite(p)
    if ok.sum()<2:return {"r2":math.nan,"rmse":math.nan,"mae":math.nan,"spearman":math.nan}
    rho=spearmanr(y[ok],p[ok]).statistic
    return {"r2":float(r2_score(y[ok],p[ok])),"rmse":float(math.sqrt(mean_squared_error(y[ok],p[ok]))),"mae":float(mean_absolute_error(y[ok],p[ok])),"spearman":float(rho) if math.isfinite(float(rho)) else math.nan}
def calibration(y,p):
    if len(y)<20 or len(np.unique(y))<2:return math.nan,math.nan
    q=np.clip(p,1e-6,1-1e-6); z=np.log(q/(1-q)).reshape(-1,1)
    m=LogisticRegression(C=1e6,solver="lbfgs",max_iter=2000,random_state=RNG).fit(z,y)
    return float(m.coef_[0,0]),float(m.intercept_[0])
def haz_metrics(y,p):
    ok=np.isfinite(p);y=y[ok];p=p[ok]
    if len(y)<20 or len(np.unique(y))<2:return {"hazard_auc":math.nan,"pr_auc":math.nan,"brier_score":math.nan,"calibration_slope":math.nan,"calibration_intercept":math.nan}
    s,i=calibration(y,p)
    return {"hazard_auc":float(roc_auc_score(y,p)),"pr_auc":float(average_precision_score(y,p)),"brier_score":float(brier_score_loss(y,p)),"calibration_slope":s,"calibration_intercept":i}


def months_between(start,end):
    sy,sm=map(int,start.split("-"));ey,em=map(int,end.split("-"));return (ey-sy)*12+em-sm
def hazard_data(rows,features,temporal=False):
    base,_=matrix(rows,features); keep_base=np.all(np.isfinite(base),axis=1)
    durations=[]; recovered=[]; kept=[]
    for i,r in enumerate(rows):
        if not keep_base[i]:continue
        if temporal:
            rc=int(finite(r.get("temporal_evaluation_right_censored")))
            d=months_between(r["recovery_start"],"2023-12") if rc else finite(r.get("recovery_time_from_minimum_months"))
        else:
            rc=int(finite(r.get("right_censored")))
            d=finite(r.get("censored_followup_months")) if rc else finite(r.get("recovery_time_from_minimum_months"))
        if not math.isfinite(d):continue
        kept.append(i);durations.append(max(1,int(round(d))));recovered.append(1-rc)
    if not kept:return np.empty((0,base.shape[1]+2)),np.empty(0,np.int8),np.empty(0,int),np.empty(0,float)
    rep=np.repeat(np.arange(len(kept)),durations); months=np.concatenate([np.arange(1,d+1,dtype=float) for d in durations])
    X=np.column_stack([base[np.asarray(kept)[rep]],months,np.log1p(months)])
    y=np.zeros(len(rep),np.int8);cursor=0
    for d,rec in zip(durations,recovered):
        if rec:y[cursor+d-1]=1
        cursor+=d
    return X,y,np.asarray(kept)[rep],months


def aggregate_hazard(row_indexes, probabilities, n):
    mean=np.full(n,np.nan); recovery=np.full(n,np.nan)
    for idx in np.unique(row_indexes):
        p=probabilities[row_indexes==idx];mean[idx]=float(np.mean(p));recovery[idx]=float(1-np.prod(1-p))
    return mean,recovery


def predict_incomplete(model, rows, features):
    base,_=matrix(rows,features);out=np.full(len(rows),np.nan)
    for i,r in enumerate(rows):
        interval=finite(r.get("next_drought_interval_months"))
        if not math.isfinite(interval) or interval<1 or not np.all(np.isfinite(base[i])):continue
        h=min(240,max(1,int(round(interval))));m=np.arange(1,h+1,dtype=float)
        X=np.column_stack([np.repeat(base[i][None],h,axis=0),m,np.log1p(m)])
        p=model.predict_proba(X)[:,1];out[i]=float(np.prod(1-p))
    return out


def aggregated_importance(names,values):
    out=defaultdict(float)
    for n,v in zip(names,values):out["forest_type" if n.startswith("forest_type_") else "climate_zone" if n.startswith("climate_zone_") else n]+=float(v)
    return dict(out)


def fit_scale(scale,events):
    train=[r for r in events if r["analysis_period"]=="TRAIN_2001_2020"]
    hold=[r for r in events if r["analysis_period"]=="TEMPORAL_HOLDOUT_2021_2023"]
    features=select_features(train,BASE_FEATURES);hfeatures=select_features(train,HAZARD_FEATURES)
    complete=[r for r in train if int(r["right_censored"])==0]
    X,names=matrix(complete,features);y=np.asarray([finite(r["recovery_time_from_minimum_months"]) for r in complete]);ok=np.isfinite(y)&np.all(np.isfinite(X),axis=1)
    complete=[r for r,k in zip(complete,ok) if k];X=X[ok];y=y[ok]
    groups=np.asarray([r["spatial_block_id"] for r in complete]);oof=np.full(len(y),np.nan);spatial=[];fold_imp=[]
    splitter=GroupKFold(n_splits=5)
    for fold,(fit,test) in enumerate(splitter.split(X,y,groups),1):
        model=rf_model(RNG+fold);model.fit(X[fit],y[fit]);oof[test]=model.predict(X[test])
        spatial.append({"spei_timescale":scale,"fold":fold,"model_type":"RF_COMPLETE_RECOVERY","n_train":len(fit),"n_test":len(test),**reg_metrics(y[test],oof[test])})
        sample=test if len(test)<=10000 else np.random.default_rng(RNG+fold).choice(test,10000,False)
        perm=permutation_importance(model,X[sample],y[sample],scoring="neg_root_mean_squared_error",n_repeats=5,random_state=RNG+100+fold,n_jobs=-1)
        fold_imp.append(aggregated_importance(names,perm.importances_mean))
    lookup={r["event_id"]:p for r,p in zip(complete,oof)}
    for r in events:
        if r["event_id"] in lookup:r["predicted_recovery_time"]=r["predicted_recovery_time_months"]=float(lookup[r["event_id"]]);r["prediction_context"]="SPATIAL_BLOCK_OOF_TRAIN"
    final=rf_model();final.fit(X,y)
    allX,_=matrix(events,features);valid=np.all(np.isfinite(allX),axis=1);pred=np.full(len(events),np.nan);pred[valid]=final.predict(allX[valid])
    for r,p in zip(events,pred):
        if not math.isfinite(finite(r.get("predicted_recovery_time"))) and math.isfinite(p):r["predicted_recovery_time"]=r["predicted_recovery_time_months"]=float(p);r["prediction_context"]="FROZEN_FINAL_MODEL"
    importance=[]
    for feature in sorted(set().union(*(d.keys() for d in fold_imp))):
        vals=np.asarray([d.get(feature,0) for d in fold_imp]);importance.append({"spei_timescale":scale,"feature":feature,"importance_mean":float(vals.mean()),"importance_sd":float(vals.std(ddof=1)),"positive_fold_fraction":float(np.mean(vals>0)),"importance_method":"held-out 5-degree-fold permutation; predictive association"})
    importance.sort(key=lambda r:r["importance_mean"],reverse=True)
    for rank,r in enumerate(importance,1):r["rank"]=rank
    curves=[];feature_pos={f:i for i,f in enumerate(features)};rng=np.random.default_rng(RNG)
    sample=np.arange(len(X)) if len(X)<=10000 else rng.choice(len(X),10000,False)
    for item in importance:
        f=item["feature"]
        if f not in feature_pos or len([x for x in curves if x["feature"]==f])>=10:continue
        if sum(1 for x in set(r["feature"] for r in curves))>=5 and f not in set(r["feature"] for r in curves):continue
        j=feature_pos[f];vals=X[sample,j];breaks=np.unique(np.quantile(vals,np.linspace(0,1,11)))
        for b,(lo,hi) in enumerate(zip(breaks[:-1],breaks[1:]),1):
            center=float(np.median(vals[(vals>=lo)&(vals<=hi)]));modified=X[sample].copy();modified[:,j]=center
            curves.append({"spei_timescale":scale,"feature":f,"bin":b,"bin_lower":float(lo),"bin_upper":float(hi),"bin_center":center,"model_partial_dependence_months":float(np.mean(final.predict(modified))),"within_observed_support":1,"interpretation":"predictive association, not causal"})
    # Hazard frozen discrete-time logistic.
    HX,Hy,hidx,hmonths=hazard_data(train,hfeatures);hgroups=np.asarray([train[i]["spatial_block_id"] for i in hidx]);ho=np.full(len(Hy),np.nan)
    for fold,(fit,test) in enumerate(GroupKFold(5).split(HX,Hy,hgroups),1):
        hm=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=RNG+fold));hm.fit(HX[fit],Hy[fit]);ho[test]=hm.predict_proba(HX[test])[:,1]
        spatial.append({"spei_timescale":scale,"fold":fold,"model_type":"DISCRETE_TIME_RECOVERY_HAZARD","n_train":len(fit),"n_test":len(test),**haz_metrics(Hy[test],ho[test])})
    hmean,hrec=aggregate_hazard(hidx,ho,len(train))
    byid={r["event_id"]:(a,b) for r,a,b in zip(train,hmean,hrec)}
    for r in events:
        if r["event_id"] in byid:r["predicted_hazard"],r["predicted_recovery_probability"]=byid[r["event_id"]]
    hfinal=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=RNG));hfinal.fit(HX,Hy)
    # Final hazard event predictions for holdout/current and incomplete probability for all.
    for subset in (hold,[r for r in events if r["analysis_period"]=="CURRENT_STATUS_2024_CENSOR_ONLY"]):
        ex,ey,eidx,em=hazard_data(subset,hfeatures,temporal=(subset is hold));prob=hfinal.predict_proba(ex)[:,1] if len(ex) else np.asarray([]);meanp,recp=aggregate_hazard(eidx,prob,len(subset))
        for r,a,b in zip(subset,meanp,recp):r["predicted_hazard"],r["predicted_recovery_probability"]=a,b
    inc=predict_incomplete(hfinal,events,hfeatures)
    for r,p in zip(events,inc):r["predicted_incomplete_before_next_drought"]=float(p) if math.isfinite(p) else math.nan
    # Temporal grouped metrics.
    temporal=[];hold_complete=[r for r in hold if int(r["temporal_evaluation_right_censored"])==0]
    TX,_=matrix(hold_complete,features);ty=np.asarray([finite(r["recovery_time_from_minimum_months"]) for r in hold_complete]);tv=np.isfinite(ty)&np.all(np.isfinite(TX),axis=1);hold_complete=[r for r,k in zip(hold_complete,tv) if k];TX=TX[tv];ty=ty[tv];tp=final.predict(TX)
    hTX,hTy,hTi,_=hazard_data(hold,hfeatures,temporal=True);hTp=hfinal.predict_proba(hTX)[:,1] if len(hTX) else np.asarray([])
    dimensions=[("GLOBAL",lambda r:"GLOBAL"),("biome",lambda r:r["biome"]),("climate_zone",lambda r:r["climate_zone_label"]),("large_region",lambda r:r["large_region"]),("forest_type",lambda r:r["biome"]),("intact",lambda r:"intact" if finite(r["intact_forest"])>=.5 else "non_intact")]
    for dim,keyfun in dimensions:
        levels=sorted({str(keyfun(r)) for r in hold})
        for level in levels:
            ri=np.asarray([str(keyfun(r))==level for r in hold_complete]);temporal.append({"spei_timescale":scale,"group_dimension":dim,"group":level,"model_type":"RF_COMPLETE_RECOVERY","n_train":len(y),"n_test":int(ri.sum()),**reg_metrics(ty[ri],tp[ri])})
            hi=np.asarray([str(keyfun(hold[i]))==level for i in hTi]);temporal.append({"spei_timescale":scale,"group_dimension":dim,"group":level,"model_type":"DISCRETE_TIME_RECOVERY_HAZARD","n_train":len(Hy),"n_test":int(hi.sum()),**haz_metrics(hTy[hi],hTp[hi])})
    # Leave-one-biome-out validation in 2001-2020.
    biome=[]
    for label in sorted({r["biome"] for r in train}):
        fitrows=[r for r in train if r["biome"]!=label and int(r["right_censored"])==0];testrows=[r for r in train if r["biome"]==label and int(r["right_censored"])==0]
        FX,_=matrix(fitrows,features);fy=np.asarray([finite(r["recovery_time_from_minimum_months"]) for r in fitrows]);fk=np.isfinite(fy)&np.all(np.isfinite(FX),axis=1);FX=FX[fk];fy=fy[fk]
        EX,_=matrix(testrows,features);ey=np.asarray([finite(r["recovery_time_from_minimum_months"]) for r in testrows]);ek=np.isfinite(ey)&np.all(np.isfinite(EX),axis=1);EX=EX[ek];ey=ey[ek]
        if len(fy)>=200 and len(ey)>=50:
            bm=rf_model(RNG+500);bm.fit(FX,fy);ep=bm.predict(EX);biome.append({"spei_timescale":scale,"held_biome":label,"model_type":"RF_COMPLETE_RECOVERY","n_train":len(fy),"n_test":len(ey),**reg_metrics(ey,ep)})
        fitall=[r for r in train if r["biome"]!=label];testall=[r for r in train if r["biome"]==label];FH,Fy,_,_=hazard_data(fitall,hfeatures);EH,Ey,_,_=hazard_data(testall,hfeatures)
        if len(Fy)>=500 and len(np.unique(Ey))>1:
            bh=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=RNG+500));bh.fit(FH,Fy);bp=bh.predict_proba(EH)[:,1];biome.append({"spei_timescale":scale,"held_biome":label,"model_type":"DISCRETE_TIME_RECOVERY_HAZARD","n_train":len(Fy),"n_test":len(Ey),**haz_metrics(Ey,bp)})
    with (RUN/f"MODEL_{scale}_RF.pkl").open("wb") as h:pickle.dump({"model":final,"features":features},h,5)
    with (RUN/f"MODEL_{scale}_HAZARD.pkl").open("wb") as h:pickle.dump({"model":hfinal,"features":hfeatures},h,5)
    return events,spatial,temporal,biome,importance,curves,{"scale":scale,"rf_features":"|".join(features),"hazard_features":"|".join(hfeatures),"rf_train_n":len(y),"hazard_month_train_n":len(Hy)}


def pixel_table(events_by_scale):
    rows=np.load(CACHE/"forest_rows.npy");cols=np.load(CACHE/"forest_cols.npy");forest=np.load(CACHE/"forest_cover_mean.npy")[rows,cols];static=dict(np.load(CACHE/"static_background.npz"));annual_type=np.load(CACHE/"annual_forest_type.npy",mmap_mode="r")
    ft=[]
    for r,c in zip(rows,cols):
        v=annual_type[:,r,c];v=v[v>=0];ft.append(int(np.bincount(v.astype(int)).argmax()) if len(v) else -1)
    groups={s:defaultdict(list) for s in SCALES}
    for s,events in events_by_scale.items():
        for e in events:
            if e["analysis_period"]=="TRAIN_2001_2020":groups[s][int(e["pixel_id"])].append(e)
    preliminary=[]
    for i,(r,c) in enumerate(zip(rows,cols)):
        pid=int(r)*720+int(c);lat=float(84.75-r*.5);lon=float(-179.75+c*.5)
        row={"pixel_id":pid,"grid_row":int(r),"grid_col":int(c),"latitude":lat,"longitude":lon,"cell_area_km2":float(6371.0088**2*math.radians(.5)*(math.sin(math.radians(lat+.25))-math.sin(math.radians(lat-.25)))),"forest_cover":float(forest[i]),"forest_type":ft[i],"biomass":float(static["biomass"][r,c]),"human_modification":float(static["human_modification"][r,c]),"intact_forest":float(static["intact_forest"][r,c]),"climate_zone":int(static["climate_zone"][r,c])}
        for s in SCALES:
            es=groups[s].get(pid,[]);bur=[finite(e["recovery_time_from_minimum_months"]) if int(e["right_censored"])==0 else finite(e["censored_followup_months"]) for e in es];bur=[x for x in bur if math.isfinite(x)];inc=[finite(e["incomplete_recovery_before_next_drought"]) for e in es if math.isfinite(finite(e["incomplete_recovery_before_next_drought"]))]
            row[f"event_count_{s}"]=len(es);row[f"median_recovery_burden_months_{s}"]=float(np.median(bur)) if bur else math.nan;row[f"median_complete_recovery_months_{s}"]=float(np.median([finite(e["recovery_time_from_minimum_months"]) for e in es if int(e["right_censored"])==0])) if any(int(e["right_censored"])==0 for e in es) else math.nan;row[f"right_censor_rate_{s}"]=float(np.mean([e["right_censored"] for e in es])) if es else math.nan;row[f"incomplete_fraction_{s}"]=float(np.mean(inc)) if inc else math.nan;row[f"recurrence_per_decade_{s}"]=len(es)/2
        preliminary.append(row)
    # Thresholds: global and forest-type p75 for slow if >=20, global p25; global static p75.
    biomass_q=float(np.nanquantile([r["biomass"] for r in preliminary],.75));hm_q=float(np.nanquantile([r["human_modification"] for r in preliminary],.75))
    for s in SCALES:
        finite_b=[r[f"median_recovery_burden_months_{s}"] for r in preliminary if math.isfinite(r[f"median_recovery_burden_months_{s}"])];slow_global=float(np.quantile(finite_b,.75));fast=float(np.quantile(finite_b,.25));rec_q=float(np.quantile([r[f"recurrence_per_decade_{s}"] for r in preliminary],.75));byft={}
        for code in FOREST_TYPES:
            v=[r[f"median_recovery_burden_months_{s}"] for r in preliminary if r["forest_type"]==code and math.isfinite(r[f"median_recovery_burden_months_{s}"])]
            if len(v)>=20:byft[code]=float(np.quantile(v,.75))
        for r in preliminary:
            slow=math.isfinite(r[f"median_recovery_burden_months_{s}"]) and r[f"median_recovery_burden_months_{s}"]>=byft.get(r["forest_type"],slow_global);incomplete=math.isfinite(r[f"incomplete_fraction_{s}"]) and r[f"incomplete_fraction_{s}"]>0;highbio=math.isfinite(r["biomass"]) and r["biomass"]>=biomass_q;intact=math.isfinite(r["intact_forest"]) and r["intact_forest"]>=.5;highhm=math.isfinite(r["human_modification"]) and r["human_modification"]>=hm_q;rec=r[f"recurrence_per_decade_{s}"]>=rec_q
            r[f"slow_recovery_{s}"]=int(slow);r[f"incomplete_recovery_{s}"]=int(incomplete);r[f"high_recurrence_{s}"]=int(rec);r[f"A_{s}"]=int(slow and incomplete and highbio and intact);r[f"B_{s}"]=int(slow and incomplete and (highhm or not intact));r[f"C_{s}"]=int((not slow) and rec and r[f"event_count_{s}"]>0)
    for r in preliminary:
        for p in "ABC":r[f"priority_agreement_count_{p}"]=sum(r[f"{p}_{s}"] for s in SCALES);r[f"priority_consensus_class_{p}"]=CONS_LABEL[r[f"priority_agreement_count_{p}"]]
        active=[p for p in "ABC" if r[f"priority_agreement_count_{p}"]>0];display=active[0] if active else "None";r["display_priority_hierarchy"]=display;r["display_agreement_count"]=0 if display=="None" else r[f"priority_agreement_count_{display}"];r["display_consensus_class"]=CONS_LABEL[r["display_agreement_count"]];r["consensus_risk_ge2"]=int(max(r["priority_agreement_count_A"],r["priority_agreement_count_B"])>=2);r["robust_risk_3of3"]=int(max(r["priority_agreement_count_A"],r["priority_agreement_count_B"])==3);r["median_recovery_burden_crossscale"]=float(np.nanmedian([r[f"median_recovery_burden_months_{s}"] for s in SCALES]));r["recurrence_crossscale"]=float(np.nanmedian([r[f"recurrence_per_decade_{s}"] for s in SCALES]));r["right_censor_crossscale"]=float(np.nanmean([r[f"right_censor_rate_{s}"] for s in SCALES]));r["incomplete_crossscale"]=float(np.nanmean([r[f"incomplete_fraction_{s}"] for s in SCALES]))
        r["management_priority"]="Priority A" if r["priority_agreement_count_A"]>=2 else "Priority B" if r["priority_agreement_count_B"]>=2 else "Priority C" if r["priority_agreement_count_C"]>=2 else "No consensus priority"
        r["risk_screening_only"]=1;r["consensus_rule"]="D1_D3_D6_unweighted_vote; DT excluded"
    return preliminary


def bootstrap_er(events,pixel_lookup,outcome,key="consensus_risk_ge2",reps=500,seed=RNG):
    usable=[e for e in events if int(e["pixel_id"]) in pixel_lookup and math.isfinite(finite(e.get(outcome)))]
    if not usable:return math.nan,math.nan,math.nan,0
    def est(rows):
        a=[finite(e[outcome]) for e in rows if pixel_lookup[int(e["pixel_id"])][key]==1];b=[finite(e[outcome]) for e in rows]
        return float(np.mean(a)/np.mean(b)) if a and b and np.mean(b)>0 else math.nan
    point=est(usable);blocks=sorted({e["spatial_block_id"] for e in usable});by={b:[e for e in usable if e["spatial_block_id"]==b] for b in blocks};rng=np.random.default_rng(seed);vals=[]
    for _ in range(reps):
        draw=[e for b in rng.choice(blocks,len(blocks),True) for e in by[str(b)]];v=est(draw)
        if math.isfinite(v):vals.append(v)
    return point,float(np.quantile(vals,.025)) if vals else math.nan,float(np.quantile(vals,.975)) if vals else math.nan,len(usable)


def evidence_tables(events_by_scale,pixels):
    lookup={r["pixel_id"]:r for r in pixels};all_hold=[e for es in events_by_scale.values() for e in es if e["analysis_period"]=="TEMPORAL_HOLDOUT_2021_2023"]
    dims=[("biome",lambda e:e["biome"]),("climate_zone",lambda e:e["climate_zone_label"]),("large_region",lambda e:e["large_region"]),("forest_type",lambda e:e["biome"])]
    rows=[]
    for dim,keyfun in dims:
        for group in sorted({keyfun(e) for e in all_hold}):
            es=[e for e in all_hold if keyfun(e)==group];er,lo,hi,n=bootstrap_er(es,lookup,"incomplete_recovery_before_next_drought",seed=RNG+zlib.crc32((dim+str(group)).encode()))
            slow_threshold=np.nanquantile([finite(e["recovery_time_from_minimum_months"]) for e in es if math.isfinite(finite(e["recovery_time_from_minimum_months"]))],.75) if any(math.isfinite(finite(e["recovery_time_from_minimum_months"])) for e in es) else math.nan
            for e in es:e["slow_outcome_tmp"]=int(finite(e["recovery_time_from_minimum_months"])>=slow_threshold) if math.isfinite(finite(e["recovery_time_from_minimum_months"])) else math.nan
            ers,lows,his,_=bootstrap_er(es,lookup,"slow_outcome_tmp",seed=RNG+1+zlib.crc32((dim+str(group)).encode()));erc,loc,hic,_=bootstrap_er(es,lookup,"right_censored",seed=RNG+2+zlib.crc32((dim+str(group)).encode()))
            y=np.asarray([finite(e["incomplete_recovery_before_next_drought"]) for e in es]);p=np.asarray([finite(e["predicted_incomplete_before_next_drought"]) for e in es]);ok=np.isfinite(y)&np.isfinite(p);metric={"hazard_auc":math.nan,"pr_auc":math.nan,"brier_score":math.nan,"calibration_slope":math.nan,"calibration_intercept":math.nan}
            if ok.sum()>=20 and len(np.unique(y[ok]))>1:
                s,i=calibration(y[ok].astype(int),p[ok]);metric={"hazard_auc":float(roc_auc_score(y[ok],p[ok])),"pr_auc":float(average_precision_score(y[ok],p[ok])),"brier_score":float(brier_score_loss(y[ok],p[ok])),"calibration_slope":s,"calibration_intercept":i}
            supported=((math.isfinite(lo) and lo>1) or (math.isfinite(lows) and lows>1) or (math.isfinite(loc) and loc>1)) and metric["hazard_auc"]>.60
            conditional=(er>1 or ers>1 or erc>1 or metric["hazard_auc"]>.60) and not supported
            status="SUPPORTED" if supported else "CONDITIONAL" if conditional and n>=100 else "LIMITED"
            rows.append({"group_dimension":dim,"group":group,"sample_events":n,"incomplete_enrichment_ratio":er,"incomplete_er_ci_low":lo,"incomplete_er_ci_high":hi,"slow_recovery_enrichment_ratio":ers,"slow_er_ci_low":lows,"slow_er_ci_high":his,"right_censor_enrichment_ratio":erc,"right_censor_er_ci_low":loc,"right_censor_er_ci_high":hic,**metric,"application_evidence_status":status,"consensus_not_automatically_high_risk":1})
    rows.append({"group_dimension":"pilot_constraint","group":"Amazon >=2/3 consensus (TASK0009D frozen)","sample_events":"pilot","incomplete_enrichment_ratio":0.847,"incomplete_er_ci_low":math.nan,"incomplete_er_ci_high":math.nan,"slow_recovery_enrichment_ratio":math.nan,"slow_er_ci_low":math.nan,"slow_er_ci_high":math.nan,"right_censor_enrichment_ratio":math.nan,"right_censor_er_ci_low":math.nan,"right_censor_er_ci_high":math.nan,"hazard_auc":math.nan,"pr_auc":math.nan,"brier_score":math.nan,"calibration_slope":math.nan,"calibration_intercept":math.nan,"application_evidence_status":"LIMITED","consensus_not_automatically_high_risk":1})
    # assign biome status conservatively
    bstatus={r["group"]:r["application_evidence_status"] for r in rows if r["group_dimension"]=="biome"};ft_labels={1:"Evergreen needleleaf forest",2:"Evergreen broadleaf forest",3:"Deciduous needleleaf forest",4:"Deciduous broadleaf forest",5:"Mixed forest"}
    for p in pixels:p["application_evidence_status"]=bstatus.get(ft_labels.get(p["forest_type"],"Other forest"),"LIMITED")
    return rows


def comparison_tables(events_by_scale,pixels):
    lookup={p["pixel_id"]:p for p in pixels};hold=[e for es in events_by_scale.values() for e in es if e["analysis_period"]=="TEMPORAL_HOLDOUT_2021_2023"]
    comps={"SPEI-1":lambda p:p["A_D1"] or p["B_D1"],"SPEI-3":lambda p:p["A_D3"] or p["B_D3"],"SPEI-6":lambda p:p["A_D6"] or p["B_D6"],">=2/3 Consensus":lambda p:p["consensus_risk_ge2"],"3/3 Robust Core":lambda p:p["robust_risk_3of3"]}
    rows=[]
    for name,flag in comps.items():
        es=[e for e in hold if e["pixel_id"] in lookup and math.isfinite(finite(e["incomplete_recovery_before_next_drought"]))];y=np.asarray([finite(e["incomplete_recovery_before_next_drought"]) for e in es]);f=np.asarray([flag(lookup[e["pixel_id"]]) for e in es],int);base=float(y.mean()) if len(y) else math.nan;rate=float(y[f==1].mean()) if np.any(f==1) else math.nan;ppv=rate;recall=float(np.sum((f==1)&(y==1))/np.sum(y==1)) if np.sum(y==1)>0 else math.nan;area=sum(p["cell_area_km2"] for p in pixels if flag(p));er=rate/base if base>0 else math.nan
        pred=f.astype(float);metric=haz_metrics(y.astype(int),pred) if len(np.unique(y))>1 else {"hazard_auc":math.nan,"pr_auc":math.nan,"brier_score":math.nan,"calibration_slope":math.nan,"calibration_intercept":math.nan}
        rows.append({"comparison":name,"n_events":len(es),"ppv":ppv,"recall":recall,"coverage_area_km2":area,"risk_enrichment_ratio":er,"spatial_stability":"reported_by_5deg_bootstrap","regional_stability":"see evidence status",**metric})
    return rows


def functional(events_by_scale,pixels):
    lookup={p["pixel_id"]:p for p in pixels};events=events_by_scale["D3"];rows=[];comparisons=[("consensus_3_vs_0",lambda e:lookup[e["pixel_id"]]["display_agreement_count"]==3,lambda e:lookup[e["pixel_id"]]["display_agreement_count"]==0),("slow_vs_fast",lambda e:finite(e["recovery_time_from_minimum_months"])>=3,lambda e:finite(e["recovery_time_from_minimum_months"])<=1),("incomplete_vs_recovered",lambda e:finite(e["incomplete_recovery_before_next_drought"])==1,lambda e:finite(e["incomplete_recovery_before_next_drought"])==0),("fire_vs_no_fire",lambda e:finite(e["any_fire_overlap"])==1,lambda e:finite(e["any_fire_overlap"])==0),("intact_vs_nonintact",lambda e:finite(e["intact_forest"])>=.5,lambda e:finite(e["intact_forest"])<.5)]
    for metric in ("gpp_legacy","npp_legacy"):
        for ci,(label,a,b) in enumerate(comparisons):
            usable=[e for e in events if e["pixel_id"] in lookup and math.isfinite(finite(e[metric])) and (a(e) or b(e))];blocks=sorted({e["spatial_block_id"] for e in usable});by={x:[e for e in usable if e["spatial_block_id"]==x] for x in blocks};av=[finite(e[metric]) for e in usable if a(e)];bv=[finite(e[metric]) for e in usable if b(e)];diff=float(np.mean(av)-np.mean(bv)) if av and bv else math.nan;rng=np.random.default_rng(RNG+ci);boot=[]
            for _ in range(500):
                draw=[e for block in rng.choice(blocks,len(blocks),True) for e in by[str(block)]] if blocks else []
                aa=[finite(e[metric]) for e in draw if a(e)];bb=[finite(e[metric]) for e in draw if b(e)]
                if aa and bb:boot.append(float(np.mean(aa)-np.mean(bb)))
            rows.append({"metric":metric,"comparison":label,"n_a":len(av),"n_b":len(bv),"mean_a":float(np.mean(av)) if av else math.nan,"mean_b":float(np.mean(bv)) if bv else math.nan,"difference_a_minus_b":diff,"ci_low":float(np.quantile(boot,.025)) if boot else math.nan,"ci_high":float(np.quantile(boot,.975)) if boot else math.nan,"bootstrap_repetitions":500,"bootstrap_unit":"5-degree spatial block","interpretation":"functional association; not causal"})
    return rows


def write_tif(name,values,dtype,nodata,desc,units,definition):
    path=MAPS/name;profile={"driver":"GTiff","height":290,"width":720,"count":1,"dtype":dtype,"crs":"EPSG:4326","transform":from_origin(-180,85,.5,.5),"nodata":nodata,"compress":"deflate","tiled":True,"blockxsize":256,"blockysize":256}
    with rasterio.open(path,"w",**profile) as dst:dst.write(np.asarray(values).astype(dtype),1);dst.set_band_description(1,desc);dst.update_tags(1,units=units,definition=definition);dst.update_tags(TASK="0010A",risk_screening_only="true")
    shutil.copyfile(path,STD_MAPS/name)


def maps(pixels,stable):
    shape=(290,720);fr=lambda fill=-9999:np.full(shape,fill,np.float32);ir=lambda fill=-1:np.full(shape,fill,np.int16)
    arrays={}
    for s in SCALES:arrays[f"recovery_{s}"]=fr()
    censor=fr();incomplete=fr();recurrence=fr();burden=fr();agree=ir();cons=ir();evidence=ir();manage=ir();driver=ir()
    status_code={"LIMITED":1,"CONDITIONAL":2,"SUPPORTED":3};manage_code={"Priority A":1,"Priority B":2,"Priority C":3,"No consensus priority":0};top=stable[0]["feature"] if stable else "none";drivers={r["feature"]:i+1 for i,r in enumerate(stable)}
    for p in pixels:
        r,c=p["grid_row"],p["grid_col"]
        for s in SCALES:
            v=p[f"median_complete_recovery_months_{s}"];arrays[f"recovery_{s}"][r,c]=v if math.isfinite(v) else -9999
        censor[r,c]=p["right_censor_crossscale"];incomplete[r,c]=p["incomplete_crossscale"];recurrence[r,c]=p["recurrence_crossscale"];burden[r,c]=p["median_recovery_burden_crossscale"];agree[r,c]=p["display_agreement_count"];cons[r,c]=p["display_agreement_count"];evidence[r,c]=status_code[p["application_evidence_status"]];manage[r,c]=manage_code[p["management_priority"]];driver[r,c]=drivers.get(top,0)
    for s in SCALES:write_tif(f"GLOBAL_MEDIAN_RECOVERY_TIME_{s}.tif",arrays[f"recovery_{s}"],"float32",-9999,f"median recovery time {s}","months","median complete-event recovery time from kNDVI minimum, training/main period")
    write_tif("GLOBAL_RIGHT_CENSOR_RATE.tif",censor,"float32",-9999,"right censor rate","fraction","cross-scale mean right-censor fraction")
    write_tif("GLOBAL_INCOMPLETE_BEFORE_NEXT_DROUGHT.tif",incomplete,"float32",-9999,"incomplete before next drought","fraction","cross-scale mean observed incomplete fraction")
    write_tif("GLOBAL_DROUGHT_RECURRENCE.tif",recurrence,"float32",-9999,"drought recurrence","events decade-1","cross-scale median effective drought events per decade")
    write_tif("GLOBAL_RECOVERY_BURDEN_CONSENSUS.tif",burden,"float32",-9999,"recovery burden consensus","months","cross-scale median recovery burden including censored follow-up")
    write_tif("GLOBAL_PRIORITY_AGREEMENT_COUNTS.tif",agree,"int16",-1,"priority agreement count","count","unweighted D1/D3/D6 agreement, DT excluded")
    write_tif("GLOBAL_PRIORITY_CONSENSUS_CLASS.tif",cons,"int16",-1,"priority consensus class","code 0-3","0 none, 1 scale-specific, 2 consensus, 3 robust core")
    write_tif("GLOBAL_APPLICATION_EVIDENCE_STATUS.tif",evidence,"int16",-1,"application evidence status","code","1 LIMITED, 2 CONDITIONAL, 3 SUPPORTED")
    write_tif("GLOBAL_MANAGEMENT_PRIORITY.tif",manage,"int16",-1,"management screening priority","code","0 none, 1 A, 2 B, 3 C; not intervention effect")
    write_tif("GLOBAL_STABLE_DOMINANT_DRIVER.tif",driver,"int16",-1,"stable dominant driver","code",f"global predictive-association stable driver code; top={top}")


def main():
    events_by_scale={};spatial=[];temporal=[];biome=[];importance={};curves={};freeze=[]
    for scale in SCALES:
        with (CACHE/f"events_{scale}.pkl").open("rb") as h:events=pickle.load(h)
        events,sp,te,bi,imp,cur,fr=fit_scale(scale,events);events_by_scale[scale]=events;spatial+=sp;temporal+=te;biome+=bi;importance[scale]=imp;curves[scale]=cur;freeze.append(fr)
        with (CACHE/f"events_modeled_{scale}.pkl").open("wb") as h:pickle.dump(events,h,5)
        fields=list(events[0]);P.write_parquet(RUN/f"GLOBAL_EVENT_LEVEL_{scale}.parquet",infer_columns(events,fields),{"task":"0010A","model":"frozen TASK0009D RF and discrete hazard"})
        write_csv(RUN/f"GLOBAL_VARIABLE_IMPORTANCE_{scale}.csv",imp);write_csv(RUN/f"GLOBAL_DRIVER_RESPONSE_{scale}.csv",cur)
        shutil.copyfile(RUN/f"GLOBAL_EVENT_LEVEL_{scale}.parquet",STD/f"GLOBAL_EVENT_LEVEL_{scale}.parquet")
        print(json.dumps({"modeled":scale,"events":len(events)}),flush=True)
    all_events=[e for s in SCALES for e in events_by_scale[s]];P.write_parquet(RUN/"GLOBAL_EVENT_LEVEL_ALL.parquet",infer_columns(all_events,list(all_events[0])),{"task":"0010A","scales":"D1|D3|D6"});shutil.copyfile(RUN/"GLOBAL_EVENT_LEVEL_ALL.parquet",STD/"GLOBAL_EVENT_LEVEL_ALL.parquet")
    write_csv(RUN/"GLOBAL_SPATIAL_BLOCK_VALIDATION.csv",spatial);write_csv(RUN/"GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv",temporal);write_csv(RUN/"GLOBAL_BIOME_HOLDOUT_VALIDATION.csv",biome);write_csv(RUN/"MODEL_FREEZE_RECORD.csv",freeze)
    # Stable driver audit.
    ranks=defaultdict(dict);dirs=defaultdict(dict)
    for s in SCALES:
        train=[e for e in events_by_scale[s] if e["analysis_period"]=="TRAIN_2001_2020" and int(e["right_censored"])==0]
        for item in importance[s]:
            ranks[item["feature"]][s]=item["rank"]
            vals=[(finite(e.get(item["feature"])),finite(e["recovery_time_from_minimum_months"])) for e in train];vals=[x for x in vals if all(math.isfinite(v) for v in x)];dirs[item["feature"]][s]=float(spearmanr([x[0] for x in vals],[x[1] for x in vals]).statistic) if len(vals)>=20 else math.nan
    stable=[]
    for f in sorted(ranks):
        top=sum(ranks[f].get(s,999)<=5 for s in SCALES);signs={int(np.sign(dirs[f].get(s,math.nan))) for s in SCALES if math.isfinite(dirs[f].get(s,math.nan)) and abs(dirs[f][s])>.02};cls="Stable driver" if top>=2 and not ({-1,1}<=signs) else "Scale-specific driver" if top==1 or ({-1,1}<=signs) else "Unstable driver"
        stable.append({"feature":f,"D1_rank":ranks[f].get("D1",999),"D3_rank":ranks[f].get("D3",999),"D6_rank":ranks[f].get("D6",999),"top5_scale_count":top,"D1_direction_spearman":dirs[f].get("D1",math.nan),"D3_direction_spearman":dirs[f].get("D3",math.nan),"D6_direction_spearman":dirs[f].get("D6",math.nan),"classification":cls,"interpretation":"predictive association, not causal"})
    stable.sort(key=lambda r:(r["classification"]!="Stable driver",-r["top5_scale_count"],min(r["D1_rank"],r["D3_rank"],r["D6_rank"])))
    write_csv(RUN/"GLOBAL_MULTISCALE_STABLE_DRIVERS.csv",stable)
    (RUN/"GLOBAL_DRIVER_DIRECTION_AUDIT.md").write_text("# Global driver direction audit\n\nDirections are unadjusted rank associations within complete training events and are not causal effects. Biomass, soil moisture, field capacity, clay, and sand are retained whether positive, negative, or weak.\n\n"+"\n".join(f"- {r['feature']}: {r['classification']}; ranks {r['D1_rank']}/{r['D3_rank']}/{r['D6_rank']}; directions {r['D1_direction_spearman']:.3g}/{r['D3_direction_spearman']:.3g}/{r['D6_direction_spearman']:.3g}." for r in stable),encoding="utf-8")
    pixels=pixel_table(events_by_scale);evidence=evidence_tables(events_by_scale,pixels);comparison=comparison_tables(events_by_scale,pixels);functional_rows=functional(events_by_scale,pixels)
    pfields=list(pixels[0]);P.write_parquet(RUN/"GLOBAL_PIXEL_MULTISCALE_PRIORITY.parquet",infer_columns(pixels,pfields),{"task":"0010A","vote":"D1 D3 D6; DT excluded"});write_csv(RUN/"GLOBAL_PIXEL_MULTISCALE_PRIORITY.csv",pixels,pfields);shutil.copyfile(RUN/"GLOBAL_PIXEL_MULTISCALE_PRIORITY.parquet",STD/"GLOBAL_PIXEL_MULTISCALE_PRIORITY.parquet")
    write_csv(RUN/"GLOBAL_APPLICATION_EVIDENCE_STATUS.csv",evidence);write_csv(RUN/"GLOBAL_CONSENSUS_RISK_ENRICHMENT.csv",comparison);write_csv(RUN/"GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv",comparison);write_csv(RUN/"GLOBAL_GPP_NPP_LEGACY_VALIDATION.csv",functional_rows)
    management=[{"pixel_id":p["pixel_id"],"latitude":p["latitude"],"longitude":p["longitude"],"priority_class":p["management_priority"],"consensus_level":p["display_consensus_class"],"application_evidence_status":p["application_evidence_status"],"risk_screening_only":1,"not_intervention_effect":1} for p in pixels];write_csv(RUN/"GLOBAL_MANAGEMENT_PRIORITY.csv",management)
    summary=[]
    for pr in sorted({r["priority_class"] for r in management}):
        group=[(r,p) for r,p in zip(management,pixels) if r["priority_class"]==pr];summary.append({"priority_class":pr,"pixels":len(group),"area_km2":sum(p["cell_area_km2"] for _,p in group),"interpretation":"screening priority, not intervention effect"})
    write_csv(RUN/"GLOBAL_MANAGEMENT_PRIORITY_SUMMARY.csv",summary)
    fire_rows=[]
    for s,es in events_by_scale.items():
        base=[e for e in es if e["analysis_period"]=="TRAIN_2001_2020"]
        for scenario,threshold in (("S0",None),("S1",.01),("S2",.05)):
            use=base if threshold is None else [e for e in base if max(finite(e["burned_fraction_during_drought"]),finite(e["burned_fraction_during_recovery"]))<=threshold];fire_rows.append({"scale":s,"scenario":scenario,"fire_exclusion_threshold":threshold if threshold is not None else "NONE","events":len(use),"median_recovery_burden":float(np.nanmedian([finite(e["recovery_time_from_minimum_months"]) if not e["right_censored"] else finite(e["censored_followup_months"]) for e in use])),"incomplete_fraction":float(np.nanmean([finite(e["incomplete_recovery_before_next_drought"]) for e in use]))})
    write_csv(RUN/"GLOBAL_FIRE_SENSITIVITY_RESULTS.csv",fire_rows)
    maps(pixels,[r for r in stable if r["classification"]=="Stable driver"])
    (RUN/"CHECKPOINT_08_CONSENSUS_APPLICATION.json").write_text(json.dumps({"status":"PASS","pixels":len(pixels),"evidence_status_counts":{s:sum(p["application_evidence_status"]==s for p in pixels) for s in ("SUPPORTED","CONDITIONAL","LIMITED")},"amazon_pilot_er":.847,"completed_utc":utc()},indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","pixels":len(pixels),"events":len(all_events)}))


if __name__=="__main__":main()
