from __future__ import annotations

import csv
import hashlib
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import rasterio


ROOT=Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RUN=ROOT/"010_Research_Workbench"/"02_Runs"/"RUN_0010A_Global_Drought_Recovery_Consensus"
STD=ROOT/"010_Research_Workbench"/"04_Standardized_Data"/"Global_Drought_Recovery_Consensus_v01"


def utc():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def csv_rows(path):
    with path.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as h:
        while block:=h.read(8*1024*1024):digest.update(block)
    return digest.hexdigest()


REQUIRED=[
"RESULT_SUMMARY.md","DECISION.md","QC_REPORT.md","RUN_CONFIG.yaml","GLOBAL_INPUT_PREFLIGHT.md","GLOBAL_INPUT_METADATA.parquet","GLOBAL_TIME_COVERAGE.csv","GLOBAL_GRID_VALIDATION.csv","GLOBAL_VERSION_SELECTION.csv","GLOBAL_MISSING_INPUTS.csv","NETWORK_DATA_ACCESS_AUDIT.csv",
"GLOBAL_EVENT_LEVEL_D1.parquet","GLOBAL_EVENT_LEVEL_D3.parquet","GLOBAL_EVENT_LEVEL_D6.parquet","GLOBAL_EVENT_LEVEL_ALL.parquet","GLOBAL_SPATIAL_BLOCK_VALIDATION.csv","GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv","GLOBAL_BIOME_HOLDOUT_VALIDATION.csv",
"GLOBAL_VARIABLE_IMPORTANCE_D1.csv","GLOBAL_VARIABLE_IMPORTANCE_D3.csv","GLOBAL_VARIABLE_IMPORTANCE_D6.csv","GLOBAL_DRIVER_RESPONSE_D1.csv","GLOBAL_DRIVER_RESPONSE_D3.csv","GLOBAL_DRIVER_RESPONSE_D6.csv","GLOBAL_MULTISCALE_STABLE_DRIVERS.csv","GLOBAL_DRIVER_DIRECTION_AUDIT.md",
"GLOBAL_PIXEL_MULTISCALE_PRIORITY.parquet","GLOBAL_PIXEL_MULTISCALE_PRIORITY.csv","GLOBAL_APPLICATION_EVIDENCE_STATUS.csv","GLOBAL_CONSENSUS_RISK_ENRICHMENT.csv","GLOBAL_SINGLE_VS_CONSENSUS_PERFORMANCE.csv","GLOBAL_GPP_NPP_LEGACY_VALIDATION.csv","GLOBAL_MANAGEMENT_PRIORITY.csv","GLOBAL_MANAGEMENT_PRIORITY_SUMMARY.csv","GLOBAL_FIRE_SENSITIVITY_RESULTS.csv",
"RESULTS_DRAFT_v01.md","METHODS_DRAFT_v01.md","MAIN_FINDINGS_BULLET.md","RESULTS_NUMERIC_EVIDENCE.csv","METHODS_PARAMETER_TABLE.csv","PAPER_CLOSED_LOOP_AUDIT.md","PAPER_CLAIM_EVIDENCE_AUDIT.csv","KNOWN_LIMITATIONS.md","NEGATIVE_OR_WEAK_RESULTS.md","CAUSALITY_LANGUAGE_RESTRICTIONS.md",
"INPUT_TREE_BEFORE.csv","INPUT_TREE_AFTER.csv","INPUT_TREE_DIFF.csv","CSV_ARTIFACT_TOOL_VALIDATION.json","PDF_RENDER_QA.json"
]
MAPS=["GLOBAL_MEDIAN_RECOVERY_TIME_D1.tif","GLOBAL_MEDIAN_RECOVERY_TIME_D3.tif","GLOBAL_MEDIAN_RECOVERY_TIME_D6.tif","GLOBAL_RIGHT_CENSOR_RATE.tif","GLOBAL_INCOMPLETE_BEFORE_NEXT_DROUGHT.tif","GLOBAL_DROUGHT_RECURRENCE.tif","GLOBAL_RECOVERY_BURDEN_CONSENSUS.tif","GLOBAL_PRIORITY_AGREEMENT_COUNTS.tif","GLOBAL_PRIORITY_CONSENSUS_CLASS.tif","GLOBAL_APPLICATION_EVIDENCE_STATUS.tif","GLOBAL_MANAGEMENT_PRIORITY.tif","GLOBAL_STABLE_DOMINANT_DRIVER.tif"]
FIGS=["Figure1_Global_Events_and_Recovery","Figure2_Global_Recovery_Time","Figure3_Multiscale_Drivers","Figure4_Multiscale_Consensus_Risk","Figure5_Functional_Legacy_and_Temporal_Validation","Figure6_Management_and_Evidence_Status"]


def write_manifest():
    rows=[]
    for label,root in (("run",RUN),("standardized",STD)):
        for path in sorted((p for p in root.rglob("*") if p.is_file()),key=lambda p:p.as_posix().lower()):
            if "_processing_cache" in path.parts or "__pycache__" in path.parts or path.name=="artifact_manifest.csv":continue
            rows.append({"root":label,"relative_path":path.relative_to(root).as_posix(),"absolute_path":str(path),"size_bytes":path.stat().st_size,"sha256":sha(path)})
    with (RUN/"artifact_manifest.csv").open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=["root","relative_path","absolute_path","size_bytes","sha256"]);w.writeheader();w.writerows(rows)
    return len(rows)


def main():
    manifest_rows=write_manifest();checks=[]
    def add(name,passed,evidence):checks.append({"check":name,"pass":bool(passed),"evidence":evidence})
    missing=[name for name in REQUIRED if not (RUN/name).is_file()];add("required_named_files",not missing,{"missing":missing,"required_count":len(REQUIRED)})
    diff=csv_rows(RUN/"INPUT_TREE_DIFF.csv");add("input_immutability",len(diff)==0,{"diff_rows":len(diff),"raw_data_changed":False if not diff else True})
    pre=json.loads((RUN/"CHECKPOINT_01_INPUT_PREFLIGHT.json").read_text());add("preflight",pre["status"]=="PASS",pre)
    dry=csv_rows(RUN/"DRY_RUN_TESTS.csv");add("dry_run_tests",all(r["pass"].lower()=="true" for r in dry),{"tests":len(dry)})
    csvqa=json.loads((RUN/"CSV_ARTIFACT_TOOL_VALIDATION.json").read_text());add("csv_artifact_tool",csvqa["fail_count"]==0,csvqa|{"results":"omitted_from_summary"})
    pdfqa=json.loads((RUN/"PDF_RENDER_QA.json").read_text());add("pdf_render_visual_qa",pdfqa["visual_inspection"]=="PASS",pdfqa)
    map_rows=[]
    for name in MAPS:
        path=RUN/"FINAL_MAP_RASTERS"/name
        if not path.exists():map_rows.append({"name":name,"pass":False,"reason":"missing"});continue
        with rasterio.open(path) as src:
            tags=src.tags(1);ok=str(src.crs)=="EPSG:4326" and tuple(src.shape)==(290,720) and src.nodata is not None and bool(src.descriptions[0]) and bool(tags.get("units")) and bool(tags.get("definition"));map_rows.append({"name":name,"pass":ok,"crs":str(src.crs),"shape":src.shape,"nodata":src.nodata,"description":src.descriptions[0],"units":tags.get("units"),"definition":tags.get("definition")})
    add("core_geotiffs",len(map_rows)==12 and all(r["pass"] for r in map_rows),map_rows)
    figure_rows=[]
    for stem in FIGS:
        found={ext:(RUN/"FIGURES_MAIN"/f"{stem}.{ext}").exists() for ext in ("pdf","svg","png")};dpi=None
        if found["png"]:
            with Image.open(RUN/"FIGURES_MAIN"/f"{stem}.png") as im:dpi=im.info.get("dpi")
        ok=all(found.values()) and dpi and dpi[0]>=599
        figure_rows.append({"stem":stem,"pass":bool(ok),"found":found,"png_dpi":dpi})
    add("six_figure_triplets",all(r["pass"] for r in figure_rows),figure_rows)
    source=list((RUN/"FIGURE_SOURCE_DATA").glob("*.csv"));scripts=list((RUN/"FIGURE_SCRIPTS").glob("*.py"));add("figure_sources_and_scripts",len(source)>=6 and len(scripts)>=7,{"source_csv":len(source),"scripts":len(scripts)})
    event_counts=csv_rows(RUN/"GLOBAL_EVENT_COUNTS.csv");events=sum(int(r["effective_events"]) for r in event_counts);add("event_products",events==280149 and all((RUN/f"GLOBAL_EVENT_LEVEL_{s}.parquet").stat().st_size>1_000_000 for s in ("D1","D3","D6")),{"events":events})
    temporal=csv_rows(RUN/"GLOBAL_TEMPORAL_HOLDOUT_VALIDATION.csv");add("temporal_validation_grouping",all(any(r["group_dimension"]==d for r in temporal) for d in ("GLOBAL","biome","climate_zone","large_region","forest_type","intact")),{"rows":len(temporal),"2024_complete_performance":False})
    evidence=csv_rows(RUN/"GLOBAL_APPLICATION_EVIDENCE_STATUS.csv");amazon=[r for r in evidence if r["group_dimension"]=="pilot_constraint"];add("amazon_limitation_retained",len(amazon)==1 and amazon[0]["application_evidence_status"]=="LIMITED" and abs(float(amazon[0]["incomplete_enrichment_ratio"])-.847)<1e-12,amazon)
    fire=csv_rows(RUN/"GLOBAL_FIRE_SENSITIVITY_RESULTS.csv");add("fire_S0_S1_S2",{r["scenario"] for r in fire}=={"S0","S1","S2"},{"rows":len(fire)})
    standard=["GLOBAL_EVENT_LEVEL_D1.parquet","GLOBAL_EVENT_LEVEL_D3.parquet","GLOBAL_EVENT_LEVEL_D6.parquet","GLOBAL_EVENT_LEVEL_ALL.parquet","GLOBAL_PIXEL_MULTISCALE_PRIORITY.parquet","GLOBAL_MONTHLY_AND_ANNUAL_STATE.zarr/.zmetadata","README.md"]
    add("standardized_product",all((STD/name).exists() for name in standard) and all((STD/"FINAL_MAP_RASTERS"/name).exists() for name in MAPS),{"required":standard,"maps":len(MAPS)})
    add("artifact_manifest",manifest_rows>0,{"rows":manifest_rows})
    passed=all(r["pass"] for r in checks);decision=(RUN/"DECISION.md").read_text(encoding="utf-8").splitlines()[2].strip("# ")
    result={"task":"TASK0010A","run_id":RUN.name,"validated_utc":utc(),"pass":passed,"decision":decision,"raw_data_changed":False if not diff else True,"events":events,"forest_pixels":16616,"checks":checks}
    (RUN/"FINAL_VALIDATION.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    manifest_rows=write_manifest()
    if not passed:raise SystemExit("FINAL_VALIDATION_FAIL")
    print(json.dumps({"pass":passed,"decision":decision,"manifest_rows":manifest_rows,"checks":len(checks)}))


if __name__=="__main__":main()
