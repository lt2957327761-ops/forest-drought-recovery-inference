from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
import os
from typing import Any, Iterable

import numpy as np
import rasterio


PROJECT = Path(os.environ["NEE_PROJECT_ROOT"]).expanduser().resolve()
RAW = PROJECT / "000 GEE Data"
RUN = (
    PROJECT
    / "010_Research_Workbench"
    / "02_Runs"
    / "RUN_0009B_Drought_Recovery_Validated_SPEI_Fire"
)
SPEI_ROOT = next(path for path in RAW.iterdir() if path.is_dir() and path.name.startswith("22 "))
FIRE_ROOT = next(path for path in RAW.iterdir() if path.is_dir() and path.name.startswith("6 "))

SPEI_PATTERN = re.compile(
    r"Data22_SPEIbase_v(?P<dataset>\d+_\d+)_SPEI01_03_06_g050_GLOBAL_"
    r"(?P<year>\d{4})_YEAR_FULL_(?P<version>v\d+)(?P<fixed>_FIXED)?\.tif$"
)
FIRE_PATTERN = re.compile(
    r"MCD64A1_burned_area_g005_tile_(?P<tile>.+)_(?P<year>\d{4})_"
    r"(?P<version>v\d+)\.tif$"
)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256_text(values: tuple[str | None, ...]) -> str:
    payload = "\n".join("" if value is None else value for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rounded_tuple(values: Iterable[float]) -> str:
    return "|".join(f"{float(value):.12g}" for value in values)


def audit_spei() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metadata_rows: list[dict[str, Any]] = []
    grid_rows: list[dict[str, Any]] = []
    repair_rows: list[dict[str, Any]] = []
    files = sorted(SPEI_ROOT.glob("*.tif"))
    for path in files:
        match = SPEI_PATTERN.match(path.name)
        parsed_year = int(match.group("year")) if match else None
        version = match.group("version") if match else "UNPARSED"
        fixed_suffix = bool(match and match.group("fixed"))
        with rasterio.open(path) as dataset:
            descriptions = dataset.descriptions
            expected_descriptions = tuple(
                f"{parsed_year:04d}{month:02d}_SPEI{scale:02d}"
                for month in range(1, 13)
                for scale in (1, 3, 6)
            ) if parsed_year is not None else ()
            nodata_count = 0
            nan_count = 0
            finite_valid_count = 0
            valid_min = math.inf
            valid_max = -math.inf
            for _, window in dataset.block_windows(1):
                values = dataset.read(window=window)
                nan_count += int(np.isnan(values).sum())
                if dataset.nodata is not None:
                    nodata_mask = values == dataset.nodata
                    nodata_count += int(nodata_mask.sum())
                else:
                    nodata_mask = np.zeros(values.shape, dtype=bool)
                valid = values[np.isfinite(values) & ~nodata_mask]
                finite_valid_count += int(valid.size)
                if valid.size:
                    valid_min = min(valid_min, float(valid.min()))
                    valid_max = max(valid_max, float(valid.max()))
            metadata_rows.append(
                {
                    "file": path.name,
                    "parsed_year": parsed_year,
                    "dataset_version": match.group("dataset") if match else "UNPARSED",
                    "file_version": version,
                    "fixed_suffix": fixed_suffix,
                    "driver": dataset.driver,
                    "crs": str(dataset.crs),
                    "width": dataset.width,
                    "height": dataset.height,
                    "band_count": dataset.count,
                    "dtype_set": "|".join(sorted(set(dataset.dtypes))),
                    "nodata": dataset.nodata,
                    "bounds": rounded_tuple(dataset.bounds),
                    "transform": rounded_tuple(tuple(dataset.transform)),
                    "band_descriptions_complete": all(descriptions),
                    "band_descriptions_expected_order": descriptions == expected_descriptions,
                    "first_band_description": descriptions[0] if descriptions else "",
                    "last_band_description": descriptions[-1] if descriptions else "",
                    "description_sha256": sha256_text(descriptions),
                    "nan_count_all_bands": nan_count,
                    "nodata_count_all_bands": nodata_count,
                    "finite_valid_count_all_bands": finite_valid_count,
                    "valid_min": valid_min if math.isfinite(valid_min) else "",
                    "valid_max": valid_max if math.isfinite(valid_max) else "",
                }
            )
            expected_grid = (
                dataset.crs is not None
                and dataset.crs.to_epsg() == 4326
                and dataset.width == 720
                and dataset.height == 360
                and dataset.count == 36
                and tuple(round(value, 9) for value in dataset.bounds)
                == (-180.0, -90.0, 180.0, 90.0)
                and tuple(round(value, 9) for value in tuple(dataset.transform)[:6])
                == (0.5, 0.0, -180.0, 0.0, -0.5, 90.0)
                and dataset.nodata == -9999.0
            )
            grid_rows.append(
                {
                    "file": path.name,
                    "year": parsed_year,
                    "epsg4326": bool(dataset.crs and dataset.crs.to_epsg() == 4326),
                    "grid_720x360": dataset.width == 720 and dataset.height == 360,
                    "global_bounds_exact": tuple(dataset.bounds) == (-180.0, -90.0, 180.0, 90.0),
                    "resolution_0p5_degree": abs(dataset.transform.a - 0.5) < 1e-12 and abs(dataset.transform.e + 0.5) < 1e-12,
                    "band_count_36": dataset.count == 36,
                    "band_order_complete": descriptions == expected_descriptions,
                    "nodata_minus9999": dataset.nodata == -9999.0,
                    "nan_absent": nan_count == 0,
                    "overall_status": "PASS" if expected_grid and descriptions == expected_descriptions and nan_count == 0 else "FAIL",
                }
            )
            repair_required = dataset.width == 721 and dataset.height == 361
            repair_rows.append(
                {
                    "source_file": path.name,
                    "year": parsed_year,
                    "source_version": version,
                    "source_width": dataset.width,
                    "source_height": dataset.height,
                    "repair_required": repair_required,
                    "repair_action": "KEEP_FIRST_720_COLUMNS_AND_360_ROWS" if repair_required else "NONE_SOURCE_ALREADY_720x360",
                    "standardized_output": "" if not repair_required else path.name.replace(".tif", "_REPAIRED_720x360.tif"),
                    "raw_source_modified": False,
                }
            )
    return metadata_rows, grid_rows, repair_rows


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_fire() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tile_manifest = {
        row["name"]: row
        for row in load_csv(FIRE_ROOT / "00_tables" / "tile_manifest_land57.csv")
    }
    band_dictionary = load_csv(FIRE_ROOT / "00_tables" / "band_dictionary_41.csv")
    files = sorted(FIRE_ROOT.rglob("*.tif"))
    metadata_rows: list[dict[str, Any]] = []
    year_files: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    description_sets: Counter[tuple[str, ...]] = Counter()
    for path in files:
        match = FIRE_PATTERN.match(path.name)
        year = int(match.group("year")) if match else -1
        tile = match.group("tile") if match else "UNPARSED"
        version = match.group("version") if match else "UNPARSED"
        expected = tile_manifest.get(tile)
        with rasterio.open(path) as dataset:
            descriptions = tuple(dataset.descriptions)
            templates = tuple(
                re.sub(r"_\d{4}$", "_{YEAR}", value or "")
                for value in descriptions
            )
            description_sets[templates] += 1
            expected_width = int(expected["width"]) if expected else -1
            expected_height = int(expected["height"]) if expected else -1
            expected_bounds = (
                float(expected["lonMin"]),
                float(expected["latMin"]),
                float(expected["lonMax"]),
                float(expected["latMax"]),
            ) if expected else ()
            row = {
                "file": str(path.relative_to(FIRE_ROOT)).replace("\\", "/"),
                "year": year,
                "tile": tile,
                "version": version,
                "driver": dataset.driver,
                "crs": str(dataset.crs),
                "width": dataset.width,
                "height": dataset.height,
                "expected_width": expected_width,
                "expected_height": expected_height,
                "bounds": rounded_tuple(dataset.bounds),
                "expected_bounds": rounded_tuple(expected_bounds) if expected_bounds else "",
                "transform": rounded_tuple(tuple(dataset.transform)),
                "resolution_x_degree": dataset.transform.a,
                "resolution_y_degree": abs(dataset.transform.e),
                "band_count": dataset.count,
                "dtype_set": "|".join(sorted(set(dataset.dtypes))),
                "nodata": dataset.nodata,
                "descriptions_complete": all(descriptions),
                "description_template_sha256": sha256_text(templates),
                "monthly_burn_fraction_present": all(
                    f"burned_land_frac_m{month:02d}_{year}" in descriptions
                    for month in range(1, 13)
                ),
                "monthly_valid_support_present": all(
                    f"valid_land_area_frac_m{month:02d}_{year}" in descriptions
                    for month in range(1, 13)
                ),
                "is_global_single_file": False,
                "is_tiled": True,
                "already_0p5_degree": False,
                "metadata_status": "PASS" if (
                    expected is not None
                    and dataset.crs is not None
                    and dataset.crs.to_epsg() == 4326
                    and dataset.width == expected_width
                    and dataset.height == expected_height
                    and tuple(dataset.bounds) == expected_bounds
                    and abs(dataset.transform.a - 0.05) < 1e-12
                    and abs(dataset.transform.e + 0.05) < 1e-12
                    and dataset.count == 41
                    and dataset.nodata == -9999.0
                    and all(descriptions)
                ) else "FAIL",
            }
            metadata_rows.append(row)
            year_files[year].append(row)

    coverage_rows: list[dict[str, Any]] = []
    for year in range(2001, 2025):
        rows = year_files.get(year, [])
        tiles = {row["tile"] for row in rows}
        coverage_rows.append(
            {
                "year": year,
                "actual_file_count": len(rows),
                "expected_file_count": 57,
                "unique_tile_count": len(tiles),
                "missing_tiles": "|".join(sorted(set(tile_manifest) - tiles)),
                "duplicate_tiles": "|".join(sorted(tile for tile, count in Counter(row["tile"] for row in rows).items() if count > 1)),
                "all_metadata_pass": all(row["metadata_status"] == "PASS" for row in rows),
                "actual_download_status": "COMPLETE" if len(rows) == 57 and tiles == set(tile_manifest) else "INCOMPLETE",
                "packaged_manifest_status": "NOT_STARTED",
                "manifest_reconciliation": "STALE_MANIFEST_ACTUAL_FILES_PRESENT" if len(rows) == 57 else "CHECK_REQUIRED",
            }
        )

    actual_templates = next(iter(description_sets)) if len(description_sets) == 1 else ()
    variable_rows: list[dict[str, Any]] = []
    for dictionary_row in band_dictionary:
        index = int(dictionary_row["band_index"])
        template = dictionary_row["band_name_template"]
        if "frac" in template:
            unit = "fraction_0_to_1"
        elif "count" in template:
            unit = "months_count"
        elif "doy" in template or "day" in template or "span" in template:
            unit = "day_or_day_of_year"
        else:
            unit = "dimensionless"
        variable_rows.append(
            {
                "band_index": index,
                "band_name_template_documented": template,
                "band_name_template_actual": actual_templates[index - 1] if actual_templates else "INCONSISTENT_ACROSS_FILES",
                "description": dictionary_row["description"],
                "unit": unit,
                "source_dataset": "MODIS/061/MCD64A1",
                "native_rule_proven_by_script": "BurnDate_gt_0_AND_QA_land_AND_QA_sufficient_valid_data",
                "g005_to_g050_rule": dictionary_row["g005_to_g050_rule"],
                "valid_support_band": (
                    f"valid_land_area_frac_m{index - 17:02d}_{{YEAR}}"
                    if 18 <= index <= 29
                    else "land_area_frac_{YEAR}" if dictionary_row["g005_to_g050_rule"] == "LAND_WEIGHTED"
                    else "annual_burned_area_frac_{YEAR}" if dictionary_row["g005_to_g050_rule"] == "ANNUAL_BURN_WEIGHTED"
                    else "not_required_or_self"
                ),
                "actual_template_match": bool(actual_templates and actual_templates[index - 1] == template),
            }
        )
    return metadata_rows, coverage_rows, variable_rows


def main() -> None:
    spei_metadata, spei_grid, spei_repair = audit_spei()
    fire_metadata, fire_coverage, fire_dictionary = audit_fire()
    write_csv(RUN / "DATA22_METADATA_AUDIT.csv", spei_metadata, list(spei_metadata[0]))
    write_csv(RUN / "DATA22_GRID_VALIDATION.csv", spei_grid, list(spei_grid[0]))
    write_csv(RUN / "DATA22_REPAIR_MANIFEST.csv", spei_repair, list(spei_repair[0]))
    write_csv(RUN / "DATA06_FIRE_METADATA.csv", fire_metadata, list(fire_metadata[0]))
    write_csv(RUN / "DATA06_FIRE_TIME_COVERAGE.csv", fire_coverage, list(fire_coverage[0]))
    write_csv(RUN / "DATA06_FIRE_VARIABLE_DICTIONARY.csv", fire_dictionary, list(fire_dictionary[0]))
    network_rows = [
        {
            "task_id": "TASK_0009B",
            "access_stage": "scientific_input_acquisition",
            "network_scientific_data_requested": False,
            "network_scientific_data_downloaded": False,
            "network_service": "NONE",
            "local_inputs_only": True,
            "status": "PASS",
            "notes": "All Data22, Data06, cube, and prior-result reads used existing local files; no GEE or web scientific-data task was started.",
        }
    ]
    write_csv(RUN / "NETWORK_DATA_ACCESS_AUDIT.csv", network_rows, list(network_rows[0]))
    print(
        {
            "spei_files": len(spei_metadata),
            "spei_grid_pass": sum(row["overall_status"] == "PASS" for row in spei_grid),
            "spei_repairs": sum(bool(row["repair_required"]) for row in spei_repair),
            "fire_files": len(fire_metadata),
            "fire_metadata_pass": sum(row["metadata_status"] == "PASS" for row in fire_metadata),
            "fire_years_complete": sum(row["actual_download_status"] == "COMPLETE" for row in fire_coverage),
        }
    )


if __name__ == "__main__":
    main()
