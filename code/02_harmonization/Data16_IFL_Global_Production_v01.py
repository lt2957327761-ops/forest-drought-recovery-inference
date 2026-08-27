# -*- coding: utf-8 -*-
"""
Data 16：Intact Forest Landscapes 全球0.05°正式生产程序
Version: v01

数据源：
    00 Official GeoPackage/IFL_2000.gpkg
    00 Official GeoPackage/IFL_2013.gpkg
    00 Official GeoPackage/IFL_2016.gpkg
    00 Official GeoPackage/IFL_2020.gpkg
    00 Official GeoPackage/IFL_2025.gpkg
    00 Official GeoPackage/Forest_zone.gpkg

正式方案：
    官方矢量 -> 0.005°内部细网格 -> 面积加权聚合 -> 0.05°固定全球网格

最终主产品：
    10波段全球GeoTIFF，EPSG:4326，7200×2900，0.05°
    Band 1-5  : IFL 2000/2013/2016/2020/2025面积比例
    Band 6-9  : 四阶段损失面积比例
    Band 10   : 2000-2025累计损失面积比例

辅助产品：
    Forest Zone面积比例，EPSG:4326，7200×2900，0.05°

重要说明：
1. 0.005°只是内部面积比例计算尺度，最终输出始终为0.05°；
2. 采用10°生产瓦片，最后一个南纬瓦片为5°；
3. 不生成全球0.005°中间文件，避免巨量磁盘占用；
4. 原始GeoPackage只读，不会被修改；
5. 正式全球模式支持断点续跑；
6. 每个瓦片完成后立即写入输出并更新checkpoint；
7. 全球模式完成后自动执行结构、范围、面积和时间单调性QC。

运行模式：
    py Data16_IFL_Global_Production_v01.py --mode pilot
    py Data16_IFL_Global_Production_v01.py --mode global
    py Data16_IFL_Global_Production_v01.py --mode qc
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pyogrio
    import rasterio
    from pyproj import CRS, Transformer
    from rasterio.enums import Resampling
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from rasterio.windows import Window
    from shapely import make_valid
    from shapely.geometry import box
    from shapely.ops import unary_union
except ImportError as exc:
    print("\n缺少必要Python库。请运行：\n")
    print("py -m pip install --upgrade pip")
    print(
        "py -m pip install numpy pandas pyogrio geopandas "
        "shapely pyproj rasterio"
    )
    raise SystemExit(1) from exc


# ============================================================================
# 0. 项目配置
# ============================================================================

VERSION = "v01"

ROOT = Path(os.environ["NEE_DATA16_ROOT"]).expanduser().resolve()

INPUT_DIR = ROOT / "00 Official GeoPackage"
OUTPUT_ROOT = ROOT / "03 Global Production"

PILOT_DIR = OUTPUT_ROOT / "00 PILOT_v01"
GLOBAL_DIR = OUTPUT_ROOT / "01 GLOBAL_v01"

YEARS = [2000, 2013, 2016, 2020, 2025]

IFL_FILES = {
    year: INPUT_DIR / f"IFL_{year}.gpkg"
    for year in YEARS
}

IFL_LAYERS = {
    year: f"IFL_{year}"
    for year in YEARS
}

FOREST_ZONE_FILE = INPUT_DIR / "Forest_zone.gpkg"
FOREST_ZONE_LAYER = "Forest_Zone"

GLOBAL_WEST = -180.0
GLOBAL_EAST = 180.0
GLOBAL_SOUTH = -60.0
GLOBAL_NORTH = 85.0

TARGET_RESOLUTION = 0.05
INTERNAL_RESOLUTION = 0.005
TILE_DEGREES = 10.0

GLOBAL_WIDTH = int(
    round((GLOBAL_EAST - GLOBAL_WEST) / TARGET_RESOLUTION)
)
GLOBAL_HEIGHT = int(
    round((GLOBAL_NORTH - GLOBAL_SOUTH) / TARGET_RESOLUTION)
)

TARGET_CRS = CRS.from_epsg(4326)
AREA_CRS = CRS.from_epsg(6933)
GLOBAL_TRANSFORM = from_origin(
    GLOBAL_WEST,
    GLOBAL_NORTH,
    TARGET_RESOLUTION,
    TARGET_RESOLUTION,
)

PROCESS_FOREST_ZONE = True
MONOTONIC_TOLERANCE = 2e-5

MAIN_TIF = (
    GLOBAL_DIR
    / "Data16_IFL_fraction_g005_global_2000_2025_10band_v01.tif"
)

FOREST_ZONE_TIF = (
    GLOBAL_DIR
    / "Data16_ForestZone_fraction_g005_global_v01.tif"
)

CHECKPOINT_JSON = (
    GLOBAL_DIR
    / "Data16_IFL_global_checkpoint_v01.json"
)

TILE_LOG_CSV = (
    GLOBAL_DIR
    / "Data16_IFL_global_tile_log_v01.csv"
)

FINAL_QC_CSV = (
    GLOBAL_DIR
    / "Data16_IFL_global_QC_bands_v01.csv"
)

FINAL_QC_TXT = (
    GLOBAL_DIR
    / "Data16_IFL_global_QC_report_v01.txt"
)

FINAL_QC_JSON = (
    GLOBAL_DIR
    / "Data16_IFL_global_QC_report_v01.json"
)

BAND_NAMES = [
    "ifl_2000_frac",
    "ifl_2013_frac",
    "ifl_2016_frac",
    "ifl_2020_frac",
    "ifl_2025_frac",
    "loss_2000_2013_frac",
    "loss_2013_2016_frac",
    "loss_2016_2020_frac",
    "loss_2020_2025_frac",
    "cumulative_loss_2000_2025_frac",
]

# 必须与全球10°瓦片边界一致。
PILOT_TILES = [
    {
        "tile_id": "Amazon_W070_W060_S05_N05",
        "west": -70.0,
        "east": -60.0,
        "south": -5.0,
        "north": 5.0,
    },
    {
        "tile_id": "Congo_E020_E030_S05_N05",
        "west": 20.0,
        "east": 30.0,
        "south": -5.0,
        "north": 5.0,
    },
    {
        "tile_id": "Siberia_E100_E110_N55_N65",
        "west": 100.0,
        "east": 110.0,
        "south": 55.0,
        "north": 65.0,
    },
    {
        "tile_id": "Ocean_W150_W140_S35_S25",
        "west": -150.0,
        "east": -140.0,
        "south": -35.0,
        "north": -25.0,
    },
    {
        "tile_id": "Dateline_E170_E180_N55_N65",
        "west": 170.0,
        "east": 180.0,
        "south": 55.0,
        "north": 65.0,
    },
    {
        "tile_id": "SouthEdge_E020_E030_S60_S55",
        "west": 20.0,
        "east": 30.0,
        "south": -60.0,
        "north": -55.0,
    },
]

# 用于验证生产流水线与此前精确基准的一致性。
PILOT_REFERENCE_FILES = {
    "Amazon_W070_W060_S05_N05": (
        ROOT
        / "02 Processing"
        / "TEST_Amazon_W065_W060_S05_N00_v01"
        / (
            "Data16_IFL_exact_fraction_g005_"
            "W065_W060_S05_N00_2000_2025_10band_LOCAL_v01.tif"
        )
    ),
    "Congo_E020_E030_S05_N05": (
        ROOT
        / "02 Processing"
        / "TEST_MultiRegion_Validation_Congo_Siberia_v01"
        / "Congo_E020_E025_S05_N00"
        / (
            "Data16_IFL_exact_g005_"
            "Congo_E020_E025_S05_N00_10band_v01.tif"
        )
    ),
    "Siberia_E100_E110_N55_N65": (
        ROOT
        / "02 Processing"
        / "TEST_MultiRegion_Validation_Congo_Siberia_v01"
        / "Siberia_E100_E105_N60_N65"
        / (
            "Data16_IFL_exact_g005_"
            "Siberia_E100_E105_N60_N65_10band_v01.tif"
        )
    ),
}


# ============================================================================
# 1. 基础工具
# ============================================================================

def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def sqlite_quick_check(path: Path) -> str:
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
        uri=True,
    )
    try:
        row = connection.execute(
            "PRAGMA quick_check;"
        ).fetchone()
        return str(row[0]) if row else "NO_RESULT"
    finally:
        connection.close()


def polygon_parts(geometry) -> list:
    if geometry is None or geometry.is_empty:
        return []

    if geometry.geom_type == "Polygon":
        return [geometry]

    if geometry.geom_type in {
        "MultiPolygon",
        "GeometryCollection",
    }:
        parts = []
        for item in geometry.geoms:
            parts.extend(polygon_parts(item))
        return parts

    return []


def repair_polygonal(geometry):
    if geometry is None or geometry.is_empty:
        return None

    repaired = (
        geometry
        if geometry.is_valid
        else make_valid(geometry)
    )

    parts = polygon_parts(repaired)

    if not parts:
        return None

    if len(parts) == 1:
        return parts[0]

    return unary_union(parts)


def config_signature() -> str:
    payload = {
        "version": VERSION,
        "years": YEARS,
        "global_extent": [
            GLOBAL_WEST,
            GLOBAL_SOUTH,
            GLOBAL_EAST,
            GLOBAL_NORTH,
        ],
        "target_resolution": TARGET_RESOLUTION,
        "internal_resolution": INTERNAL_RESOLUTION,
        "tile_degrees": TILE_DEGREES,
        "band_names": BAND_NAMES,
        "process_forest_zone": PROCESS_FOREST_ZONE,
        "input_files": {
            path.name: {
                "size": path.stat().st_size
                if path.exists()
                else None,
                "mtime_ns": path.stat().st_mtime_ns
                if path.exists()
                else None,
            }
            for path in [
                *IFL_FILES.values(),
                FOREST_ZONE_FILE,
            ]
        },
    }

    text = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_inputs() -> dict[str, Any]:
    print("\n检查输入文件...")

    results = {}

    expected = [
        *IFL_FILES.values(),
        FOREST_ZONE_FILE,
    ]

    for path in expected:
        if not path.exists():
            raise FileNotFoundError(path)

        check = sqlite_quick_check(path)

        if check.lower() != "ok":
            raise RuntimeError(
                f"{path.name} SQLite quick_check失败：{check}"
            )

        results[path.name] = {
            "size_mb": round(
                path.stat().st_size / (1024 ** 2),
                3,
            ),
            "sqlite_quick_check": check,
        }

        print(
            f"  PASS {path.name}: "
            f"{results[path.name]['size_mb']} MB"
        )

    return results


def dataset_bounds(
    path: Path,
    layer: str,
) -> tuple[float, float, float, float]:
    info = pyogrio.read_info(
        path,
        layer=layer,
    )

    bounds = info.get("total_bounds")

    if bounds is None or len(bounds) != 4:
        return (
            GLOBAL_WEST,
            GLOBAL_SOUTH,
            GLOBAL_EAST,
            GLOBAL_NORTH,
        )

    return tuple(float(item) for item in bounds)


def bounds_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    a_w, a_s, a_e, a_n = a
    b_w, b_s, b_e, b_n = b

    return not (
        a_e <= b_w
        or a_w >= b_e
        or a_n <= b_s
        or a_s >= b_n
    )


# ============================================================================
# 2. 全球瓦片与面积权重
# ============================================================================

def build_global_tiles() -> list[dict[str, Any]]:
    tiles = []
    tile_index = 0

    north = GLOBAL_NORTH
    row_index = 0

    while north > GLOBAL_SOUTH + 1e-12:
        south = max(
            north - TILE_DEGREES,
            GLOBAL_SOUTH,
        )

        west = GLOBAL_WEST
        col_index = 0

        while west < GLOBAL_EAST - 1e-12:
            east = min(
                west + TILE_DEGREES,
                GLOBAL_EAST,
            )

            target_width = int(
                round(
                    (east - west)
                    / TARGET_RESOLUTION
                )
            )
            target_height = int(
                round(
                    (north - south)
                    / TARGET_RESOLUTION
                )
            )

            row_off = int(
                round(
                    (GLOBAL_NORTH - north)
                    / TARGET_RESOLUTION
                )
            )
            col_off = int(
                round(
                    (west - GLOBAL_WEST)
                    / TARGET_RESOLUTION
                )
            )

            tile_id = (
                f"R{row_index:02d}_C{col_index:02d}_"
                f"W{west:+07.1f}_E{east:+07.1f}_"
                f"S{south:+06.1f}_N{north:+06.1f}"
            )

            tiles.append(
                {
                    "tile_index": tile_index,
                    "tile_id": tile_id,
                    "row_index": row_index,
                    "col_index": col_index,
                    "west": west,
                    "east": east,
                    "south": south,
                    "north": north,
                    "target_width": target_width,
                    "target_height": target_height,
                    "row_off": row_off,
                    "col_off": col_off,
                }
            )

            tile_index += 1
            col_index += 1
            west = east

        row_index += 1
        north = south

    return tiles


def spherical_fine_row_areas(
    north: float,
    fine_height: int,
) -> np.ndarray:
    radius = 6_371_008.8
    delta_lon_rad = math.radians(
        INTERNAL_RESOLUTION
    )

    rows = np.arange(
        fine_height,
        dtype=np.float64,
    )

    lat_north = (
        north
        - rows * INTERNAL_RESOLUTION
    )
    lat_south = (
        lat_north
        - INTERNAL_RESOLUTION
    )

    areas = (
        radius ** 2
        * delta_lon_rad
        * (
            np.sin(np.radians(lat_north))
            - np.sin(np.radians(lat_south))
        )
    )

    return areas


def aggregate_fine_mask(
    fine_mask: np.ndarray,
    row_areas: np.ndarray,
    target_height: int,
    target_width: int,
) -> np.ndarray:
    factor_float = (
        TARGET_RESOLUTION
        / INTERNAL_RESOLUTION
    )
    factor = int(round(factor_float))

    if abs(factor_float - factor) > 1e-12:
        raise RuntimeError(
            "内部尺度不能整除目标尺度"
        )

    expected_shape = (
        target_height * factor,
        target_width * factor,
    )

    if fine_mask.shape != expected_shape:
        raise RuntimeError(
            f"细网格尺寸错误：{fine_mask.shape}，"
            f"预期：{expected_shape}"
        )

    weighted = (
        fine_mask.astype(np.float64)
        * row_areas[:, None]
    )

    numerator = weighted.reshape(
        target_height,
        factor,
        target_width,
        factor,
    ).sum(axis=(1, 3))

    denominator_rows = (
        factor
        * row_areas.reshape(
            target_height,
            factor,
        ).sum(axis=1)
    )

    fraction = np.divide(
        numerator,
        denominator_rows[:, None],
        out=np.zeros_like(numerator),
        where=denominator_rows[:, None] > 0,
    )

    return np.clip(
        fraction,
        0.0,
        1.0,
    ).astype(np.float32)


# ============================================================================
# 3. 单图层、单瓦片处理
# ============================================================================

def read_repaired_shapes(
    path: Path,
    layer: str,
    tile: dict[str, Any],
    source_bounds: tuple[float, float, float, float],
) -> tuple[list, dict[str, Any]]:
    tile_bounds = (
        tile["west"],
        tile["south"],
        tile["east"],
        tile["north"],
    )

    stats = {
        "features_read": 0,
        "invalid_before": 0,
        "polygon_parts_after": 0,
        "dropped": 0,
    }

    if not bounds_overlap(
        source_bounds,
        tile_bounds,
    ):
        return [], stats

    gdf = pyogrio.read_dataframe(
        path,
        layer=layer,
        bbox=tile_bounds,
        columns=[],
        use_arrow=False,
    )

    stats["features_read"] = len(gdf)

    if gdf.empty:
        return [], stats

    if gdf.crs is None:
        raise RuntimeError(
            f"{path.name}/{layer} 缺少CRS"
        )

    tile_geometry = box(*tile_bounds)
    shapes = []

    for geometry in gdf.geometry:
        if geometry is None or geometry.is_empty:
            stats["dropped"] += 1
            continue

        if not geometry.is_valid:
            stats["invalid_before"] += 1

        repaired = repair_polygonal(geometry)

        if repaired is None or repaired.is_empty:
            stats["dropped"] += 1
            continue

        try:
            clipped = repaired.intersection(
                tile_geometry
            )
        except Exception:
            repaired = repair_polygonal(
                repaired.buffer(0)
            )

            if repaired is None:
                stats["dropped"] += 1
                continue

            clipped = repaired.intersection(
                tile_geometry
            )

        clipped = repair_polygonal(clipped)

        if clipped is None or clipped.is_empty:
            continue

        parts = polygon_parts(clipped)
        shapes.extend(parts)

    stats["polygon_parts_after"] = len(shapes)
    return shapes, stats


def fraction_from_shapes(
    shapes: list,
    tile: dict[str, Any],
    row_areas: np.ndarray,
) -> np.ndarray:
    target_width = tile["target_width"]
    target_height = tile["target_height"]

    factor = int(
        round(
            TARGET_RESOLUTION
            / INTERNAL_RESOLUTION
        )
    )

    fine_width = target_width * factor
    fine_height = target_height * factor

    if not shapes:
        fine_mask = np.zeros(
            (fine_height, fine_width),
            dtype=np.uint8,
        )
    else:
        fine_transform = from_origin(
            tile["west"],
            tile["north"],
            INTERNAL_RESOLUTION,
            INTERNAL_RESOLUTION,
        )

        fine_mask = rasterize(
            [(geometry, 1) for geometry in shapes],
            out_shape=(
                fine_height,
                fine_width,
            ),
            transform=fine_transform,
            fill=0,
            all_touched=False,
            dtype=np.uint8,
        )

    return aggregate_fine_mask(
        fine_mask=fine_mask,
        row_areas=row_areas,
        target_height=target_height,
        target_width=target_width,
    )


def process_tile(
    tile: dict[str, Any],
    source_bounds_map: dict[str, tuple],
) -> tuple[np.ndarray, np.ndarray | None, dict[str, Any]]:
    target_height = tile["target_height"]
    target_width = tile["target_width"]

    factor = int(
        round(
            TARGET_RESOLUTION
            / INTERNAL_RESOLUTION
        )
    )

    fine_height = target_height * factor

    row_areas = spherical_fine_row_areas(
        north=tile["north"],
        fine_height=fine_height,
    )

    fractions_by_year = {}
    layer_stats = {}
    start_tile = time.perf_counter()

    for year in YEARS:
        start = time.perf_counter()

        shapes, stats = read_repaired_shapes(
            path=IFL_FILES[year],
            layer=IFL_LAYERS[year],
            tile=tile,
            source_bounds=source_bounds_map[
                f"IFL_{year}"
            ],
        )

        fraction = fraction_from_shapes(
            shapes=shapes,
            tile=tile,
            row_areas=row_areas,
        )

        fractions_by_year[year] = fraction
        stats["elapsed_seconds"] = (
            time.perf_counter() - start
        )
        layer_stats[f"IFL_{year}"] = stats

    f2000 = fractions_by_year[2000]
    f2013 = fractions_by_year[2013]
    f2016 = fractions_by_year[2016]
    f2020 = fractions_by_year[2020]
    f2025 = fractions_by_year[2025]

    main_stack = np.stack(
        [
            f2000,
            f2013,
            f2016,
            f2020,
            f2025,
            np.clip(f2000 - f2013, 0, 1),
            np.clip(f2013 - f2016, 0, 1),
            np.clip(f2016 - f2020, 0, 1),
            np.clip(f2020 - f2025, 0, 1),
            np.clip(f2000 - f2025, 0, 1),
        ],
        axis=0,
    ).astype(np.float32)

    forest_zone = None

    if PROCESS_FOREST_ZONE:
        start = time.perf_counter()

        shapes, stats = read_repaired_shapes(
            path=FOREST_ZONE_FILE,
            layer=FOREST_ZONE_LAYER,
            tile=tile,
            source_bounds=source_bounds_map[
                "Forest_Zone"
            ],
        )

        forest_zone = fraction_from_shapes(
            shapes=shapes,
            tile=tile,
            row_areas=row_areas,
        )

        stats["elapsed_seconds"] = (
            time.perf_counter() - start
        )
        layer_stats["Forest_Zone"] = stats

    tile_stats = {
        "tile_id": tile["tile_id"],
        "tile_index": tile.get(
            "tile_index",
            None,
        ),
        "west": tile["west"],
        "south": tile["south"],
        "east": tile["east"],
        "north": tile["north"],
        "target_width": target_width,
        "target_height": target_height,
        "elapsed_seconds": (
            time.perf_counter() - start_tile
        ),
        "layers": layer_stats,
    }

    return main_stack, forest_zone, tile_stats


# ============================================================================
# 4. GeoTIFF输出
# ============================================================================

def main_profile(
    width: int,
    height: int,
    transform,
) -> dict[str, Any]:
    return {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 10,
        "dtype": "float32",
        "crs": TARGET_CRS,
        "transform": transform,
        "nodata": -9999.0,
        "compress": "DEFLATE",
        "zlevel": 6,
        "predictor": 3,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "YES",
    }


def forest_profile(
    width: int,
    height: int,
    transform,
) -> dict[str, Any]:
    profile = main_profile(
        width,
        height,
        transform,
    )
    profile["count"] = 1
    return profile


def set_main_metadata(dataset) -> None:
    for index, name in enumerate(
        BAND_NAMES,
        start=1,
    ):
        dataset.set_band_description(
            index,
            name,
        )

    dataset.update_tags(
        dataset="Data16 Intact Forest Landscapes",
        version=VERSION,
        source="official IFL GeoPackage",
        processing=(
            "0.005 degree internal rasterization; "
            "latitude-area-weighted aggregation"
        ),
        target_grid=(
            "EPSG:4326; 0.05 degree; "
            "origin -180,85"
        ),
        global_extent="-180,-60,180,85",
        rasterize_all_touched="False",
    )


def set_forest_metadata(dataset) -> None:
    dataset.set_band_description(
        1,
        "forest_zone_frac",
    )

    dataset.update_tags(
        dataset="Data16 IFL Forest Zone",
        version=VERSION,
        source="official Forest_zone GeoPackage",
        processing=(
            "0.005 degree internal rasterization; "
            "latitude-area-weighted aggregation"
        ),
        target_grid=(
            "EPSG:4326; 0.05 degree; "
            "origin -180,85"
        ),
    )


def write_pilot_tile(
    tile_dir: Path,
    tile: dict[str, Any],
    main_stack: np.ndarray,
    forest_zone: np.ndarray | None,
) -> tuple[Path, Path | None]:
    tile_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    transform = from_origin(
        tile["west"],
        tile["north"],
        TARGET_RESOLUTION,
        TARGET_RESOLUTION,
    )

    main_path = (
        tile_dir
        / (
            "Data16_IFL_0p005internal_"
            f"g005_{tile['tile_id']}_10band_v01.tif"
        )
    )

    with rasterio.open(
        main_path,
        "w",
        **main_profile(
            width=tile["target_width"],
            height=tile["target_height"],
            transform=transform,
        ),
    ) as dataset:
        dataset.write(main_stack)
        set_main_metadata(dataset)

    forest_path = None

    if (
        PROCESS_FOREST_ZONE
        and forest_zone is not None
    ):
        forest_path = (
            tile_dir
            / (
                "Data16_ForestZone_0p005internal_"
                f"g005_{tile['tile_id']}_v01.tif"
            )
        )

        with rasterio.open(
            forest_path,
            "w",
            **forest_profile(
                width=tile["target_width"],
                height=tile["target_height"],
                transform=transform,
            ),
        ) as dataset:
            dataset.write(
                forest_zone[np.newaxis, :, :]
            )
            set_forest_metadata(dataset)

    return main_path, forest_path


def initialize_global_outputs() -> None:
    GLOBAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not MAIN_TIF.exists():
        print(f"创建全球主TIF：{MAIN_TIF}")

        with rasterio.open(
            MAIN_TIF,
            "w",
            **main_profile(
                width=GLOBAL_WIDTH,
                height=GLOBAL_HEIGHT,
                transform=GLOBAL_TRANSFORM,
            ),
        ) as dataset:
            set_main_metadata(dataset)

    if (
        PROCESS_FOREST_ZONE
        and not FOREST_ZONE_TIF.exists()
    ):
        print(
            f"创建Forest Zone TIF：{FOREST_ZONE_TIF}"
        )

        with rasterio.open(
            FOREST_ZONE_TIF,
            "w",
            **forest_profile(
                width=GLOBAL_WIDTH,
                height=GLOBAL_HEIGHT,
                transform=GLOBAL_TRANSFORM,
            ),
        ) as dataset:
            set_forest_metadata(dataset)


def write_global_tile(
    tile: dict[str, Any],
    main_stack: np.ndarray,
    forest_zone: np.ndarray | None,
) -> None:
    window = Window(
        col_off=tile["col_off"],
        row_off=tile["row_off"],
        width=tile["target_width"],
        height=tile["target_height"],
    )

    with rasterio.open(
        MAIN_TIF,
        "r+",
    ) as dataset:
        dataset.write(
            main_stack,
            window=window,
        )

    if (
        PROCESS_FOREST_ZONE
        and forest_zone is not None
    ):
        with rasterio.open(
            FOREST_ZONE_TIF,
            "r+",
        ) as dataset:
            dataset.write(
                forest_zone[np.newaxis, :, :],
                window=window,
            )


# ============================================================================
# 5. Pilot对照
# ============================================================================

def compare_pilot_reference(
    pilot_stack: np.ndarray,
    pilot_tile: dict[str, Any],
    reference_path: Path,
) -> dict[str, Any] | None:
    if not reference_path.exists():
        return None

    with rasterio.open(
        reference_path
    ) as dataset:
        reference = dataset.read().astype(
            np.float64
        )
        bounds = dataset.bounds

    row_start = int(
        round(
            (pilot_tile["north"] - bounds.top)
            / TARGET_RESOLUTION
        )
    )
    row_end = int(
        round(
            (pilot_tile["north"] - bounds.bottom)
            / TARGET_RESOLUTION
        )
    )
    col_start = int(
        round(
            (bounds.left - pilot_tile["west"])
            / TARGET_RESOLUTION
        )
    )
    col_end = int(
        round(
            (bounds.right - pilot_tile["west"])
            / TARGET_RESOLUTION
        )
    )

    subset = pilot_stack[
        :,
        row_start:row_end,
        col_start:col_end,
    ].astype(np.float64)

    if subset.shape != reference.shape:
        raise RuntimeError(
            "Pilot与精确基准子窗口尺寸不一致："
            f"{subset.shape} vs {reference.shape}"
        )

    difference = subset - reference
    absolute = np.abs(difference)

    per_band = []

    for index, name in enumerate(BAND_NAMES):
        boundary = (
            (reference[index] > 1e-6)
            & (reference[index] < 1 - 1e-6)
        )

        per_band.append(
            {
                "band": name,
                "mae": float(
                    absolute[index].mean()
                ),
                "rmse": float(
                    np.sqrt(
                        np.mean(
                            difference[index] ** 2
                        )
                    )
                ),
                "max_abs_error": float(
                    absolute[index].max()
                ),
                "boundary_mae": (
                    float(
                        absolute[index][
                            boundary
                        ].mean()
                    )
                    if boundary.any()
                    else 0.0
                ),
            }
        )

    ifl_rows = per_band[:5]

    return {
        "reference_path": str(
            reference_path
        ),
        "max_ifl_mae": max(
            row["mae"]
            for row in ifl_rows
        ),
        "max_ifl_boundary_mae": max(
            row["boundary_mae"]
            for row in ifl_rows
        ),
        "max_all_band_mae": max(
            row["mae"]
            for row in per_band
        ),
        "passes": (
            max(
                row["mae"]
                for row in ifl_rows
            )
            <= 0.01
            and max(
                row["boundary_mae"]
                for row in ifl_rows
            )
            <= 0.05
            and max(
                row["mae"]
                for row in per_band
            )
            <= 0.01
        ),
        "per_band": per_band,
    }


def run_pilot() -> int:
    print("=" * 78)
    print("Data16 全球正式生产流水线 PILOT")
    print("=" * 78)

    validate_inputs()

    PILOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_bounds_map = {
        f"IFL_{year}": dataset_bounds(
            IFL_FILES[year],
            IFL_LAYERS[year],
        )
        for year in YEARS
    }

    source_bounds_map["Forest_Zone"] = (
        dataset_bounds(
            FOREST_ZONE_FILE,
            FOREST_ZONE_LAYER,
        )
    )

    pilot_results = []
    all_pass = True

    for index, tile in enumerate(
        PILOT_TILES,
        start=1,
    ):
        tile = dict(tile)
        tile["target_width"] = int(
            round(
                (tile["east"] - tile["west"])
                / TARGET_RESOLUTION
            )
        )
        tile["target_height"] = int(
            round(
                (tile["north"] - tile["south"])
                / TARGET_RESOLUTION
            )
        )
        tile["tile_index"] = index - 1

        print("\n" + "-" * 78)
        print(
            f"[{index}/{len(PILOT_TILES)}] "
            f"{tile['tile_id']}"
        )
        print(
            f"范围：[{tile['west']}, "
            f"{tile['south']}, "
            f"{tile['east']}, "
            f"{tile['north']}]"
        )

        main_stack, forest_zone, stats = (
            process_tile(
                tile=tile,
                source_bounds_map=(
                    source_bounds_map
                ),
            )
        )

        tile_dir = (
            PILOT_DIR / tile["tile_id"]
        )

        main_path, forest_path = (
            write_pilot_tile(
                tile_dir=tile_dir,
                tile=tile,
                main_stack=main_stack,
                forest_zone=forest_zone,
            )
        )

        structural_pass = (
            main_stack.shape
            == (
                10,
                tile["target_height"],
                tile["target_width"],
            )
            and int(
                np.isnan(main_stack).sum()
            )
            == 0
            and int(
                np.isinf(main_stack).sum()
            )
            == 0
            and float(main_stack.min()) >= 0
            and float(main_stack.max()) <= 1
        )

        reference_result = None
        reference_path = (
            PILOT_REFERENCE_FILES.get(
                tile["tile_id"]
            )
        )

        if reference_path is not None:
            reference_result = (
                compare_pilot_reference(
                    pilot_stack=main_stack,
                    pilot_tile=tile,
                    reference_path=reference_path,
                )
            )

        tile_pass = structural_pass and (
            reference_result is None
            or reference_result["passes"]
        )

        all_pass = all_pass and tile_pass

        record = {
            "tile_id": tile["tile_id"],
            "main_tif": str(main_path),
            "forest_zone_tif": (
                str(forest_path)
                if forest_path is not None
                else None
            ),
            "structural_pass": structural_pass,
            "reference_comparison": (
                reference_result
            ),
            "tile_pass": tile_pass,
            "processing_stats": stats,
        }

        atomic_write_json(
            tile_dir
            / "Data16_PILOT_tile_report_v01.json",
            record,
        )

        pilot_results.append(record)

        print(
            f"耗时：{stats['elapsed_seconds']:.2f}s"
        )
        print(
            f"结构检查：{structural_pass}"
        )

        if reference_result is not None:
            print(
                "精确基准最大IFL MAE："
                f"{reference_result['max_ifl_mae']:.8f}"
            )
            print(
                "精确基准最大边界MAE："
                f"{reference_result['max_ifl_boundary_mae']:.8f}"
            )
            print(
                "精确对照通过："
                f"{reference_result['passes']}"
            )

    report = {
        "generated_at": utc_now(),
        "version": VERSION,
        "all_pilot_tiles_pass": all_pass,
        "pilot_tiles": pilot_results,
        "next_action": (
            "Run global mode"
            if all_pass
            else "Inspect failed pilot tile"
        ),
    }

    atomic_write_json(
        PILOT_DIR
        / "Data16_IFL_PRODUCTION_PILOT_report_v01.json",
        report,
    )

    lines = [
        "Data 16：IFL全球正式生产流水线PILOT报告",
        "=" * 78,
        f"生成时间：{report['generated_at']}",
        f"内部计算尺度：{INTERNAL_RESOLUTION}°",
        f"最终输出尺度：{TARGET_RESOLUTION}°",
        f"测试瓦片数：{len(PILOT_TILES)}",
        (
            "全部PILOT瓦片通过："
            f"{all_pass}"
        ),
        "",
    ]

    for item in pilot_results:
        lines.extend(
            [
                f"瓦片：{item['tile_id']}",
                (
                    "  结构检查："
                    f"{item['structural_pass']}"
                ),
                (
                    "  最终通过："
                    f"{item['tile_pass']}"
                ),
                (
                    "  用时："
                    f"{item['processing_stats']['elapsed_seconds']:.3f}s"
                ),
            ]
        )

        comparison = item[
            "reference_comparison"
        ]

        if comparison is not None:
            lines.extend(
                [
                    (
                        "  最大IFL MAE："
                        f"{comparison['max_ifl_mae']:.8f}"
                    ),
                    (
                        "  最大边界MAE："
                        f"{comparison['max_ifl_boundary_mae']:.8f}"
                    ),
                    (
                        "  精确对照通过："
                        f"{comparison['passes']}"
                    ),
                ]
            )

        lines.append("")

    (
        PILOT_DIR
        / "Data16_IFL_PRODUCTION_PILOT_report_v01.txt"
    ).write_text(
        "\n".join(lines),
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 78)
    print(
        "PILOT完成。全部通过："
        f"{all_pass}"
    )
    print(
        "报告："
        f"{PILOT_DIR / 'Data16_IFL_PRODUCTION_PILOT_report_v01.txt'}"
    )
    print("=" * 78)

    return 0 if all_pass else 3


# ============================================================================
# 6. 全球正式生产
# ============================================================================

def load_or_create_checkpoint(
    tiles: list[dict[str, Any]],
) -> dict[str, Any]:
    signature = config_signature()

    if CHECKPOINT_JSON.exists():
        checkpoint = json.loads(
            CHECKPOINT_JSON.read_text(
                encoding="utf-8"
            )
        )

        if (
            checkpoint.get(
                "config_signature"
            )
            != signature
        ):
            raise RuntimeError(
                "现有checkpoint与当前配置或输入文件不一致。"
                "请不要继续覆盖；先备份GLOBAL目录。"
            )

        return checkpoint

    if MAIN_TIF.exists() or (
        PROCESS_FOREST_ZONE
        and FOREST_ZONE_TIF.exists()
    ):
        raise RuntimeError(
            "检测到全球输出TIF，但没有checkpoint。"
            "为防止误覆盖，请先备份并移走GLOBAL_v01目录。"
        )

    checkpoint = {
        "version": VERSION,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "config_signature": signature,
        "total_tiles": len(tiles),
        "completed_tiles": {},
        "status": "RUNNING",
    }

    atomic_write_json(
        CHECKPOINT_JSON,
        checkpoint,
    )

    return checkpoint


def checkpoint_to_csv(
    checkpoint: dict[str, Any],
) -> None:
    records = []

    for tile_id, record in checkpoint[
        "completed_tiles"
    ].items():
        row = {
            "tile_id": tile_id,
            "completed_at": record.get(
                "completed_at"
            ),
            "elapsed_seconds": record.get(
                "elapsed_seconds"
            ),
            "west": record.get("west"),
            "south": record.get("south"),
            "east": record.get("east"),
            "north": record.get("north"),
        }

        layers = record.get("layers", {})

        for layer_name, layer_stats in (
            layers.items()
        ):
            prefix = layer_name.replace(
                " ",
                "_",
            )

            row[
                f"{prefix}_features"
            ] = layer_stats.get(
                "features_read"
            )
            row[
                f"{prefix}_invalid"
            ] = layer_stats.get(
                "invalid_before"
            )
            row[
                f"{prefix}_parts"
            ] = layer_stats.get(
                "polygon_parts_after"
            )
            row[
                f"{prefix}_seconds"
            ] = layer_stats.get(
                "elapsed_seconds"
            )

        records.append(row)

    if not records:
        return

    all_fields = []

    for record in records:
        for key in record:
            if key not in all_fields:
                all_fields.append(key)

    with TILE_LOG_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=all_fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)


def build_overviews(path: Path) -> None:
    print(f"构建概览金字塔：{path.name}")

    with rasterio.open(
        path,
        "r+",
    ) as dataset:
        factors = [
            factor
            for factor in [
                2,
                4,
                8,
                16,
                32,
                64,
            ]
            if (
                dataset.width // factor >= 1
                and dataset.height // factor >= 1
            )
        ]

        dataset.build_overviews(
            factors,
            Resampling.average,
        )

        dataset.update_tags(
            ns="rio_overview",
            resampling="average",
        )


def run_global() -> int:
    print("=" * 78)
    print("Data16 IFL 全球0.05°正式生产")
    print("=" * 78)

    validate_inputs()

    tiles = build_global_tiles()

    if len(tiles) != 540:
        raise RuntimeError(
            f"全球瓦片数量应为540，实际为{len(tiles)}"
        )

    GLOBAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = load_or_create_checkpoint(
        tiles
    )

    initialize_global_outputs()

    source_bounds_map = {
        f"IFL_{year}": dataset_bounds(
            IFL_FILES[year],
            IFL_LAYERS[year],
        )
        for year in YEARS
    }

    source_bounds_map["Forest_Zone"] = (
        dataset_bounds(
            FOREST_ZONE_FILE,
            FOREST_ZONE_LAYER,
        )
    )

    completed = checkpoint[
        "completed_tiles"
    ]
    total = len(tiles)
    run_start = time.perf_counter()

    for sequence, tile in enumerate(
        tiles,
        start=1,
    ):
        tile_id = tile["tile_id"]

        if tile_id in completed:
            print(
                f"[{sequence}/{total}] SKIP {tile_id}"
            )
            continue

        print("\n" + "-" * 78)
        print(
            f"[{sequence}/{total}] {tile_id}"
        )
        print(
            f"范围：[{tile['west']}, "
            f"{tile['south']}, "
            f"{tile['east']}, "
            f"{tile['north']}]"
        )

        start = time.perf_counter()

        main_stack, forest_zone, stats = (
            process_tile(
                tile=tile,
                source_bounds_map=(
                    source_bounds_map
                ),
            )
        )

        write_global_tile(
            tile=tile,
            main_stack=main_stack,
            forest_zone=forest_zone,
        )

        elapsed = time.perf_counter() - start

        completed[tile_id] = {
            "completed_at": utc_now(),
            "elapsed_seconds": elapsed,
            "west": tile["west"],
            "south": tile["south"],
            "east": tile["east"],
            "north": tile["north"],
            "target_width": (
                tile["target_width"]
            ),
            "target_height": (
                tile["target_height"]
            ),
            "layers": stats["layers"],
        }

        checkpoint["updated_at"] = utc_now()
        checkpoint[
            "completed_tile_count"
        ] = len(completed)

        atomic_write_json(
            CHECKPOINT_JSON,
            checkpoint,
        )

        checkpoint_to_csv(checkpoint)

        remaining = total - len(completed)
        average = (
            sum(
                record[
                    "elapsed_seconds"
                ]
                for record in completed.values()
            )
            / len(completed)
        )

        eta_hours = (
            remaining * average / 3600.0
        )

        print(
            f"完成，用时：{elapsed:.2f}s"
        )
        print(
            f"进度：{len(completed)}/{total}"
        )
        print(
            f"当前平均：{average:.2f}s/瓦片"
        )
        print(
            f"粗略剩余时间：{eta_hours:.2f}小时"
        )

    checkpoint["status"] = "TILES_COMPLETE"
    checkpoint["updated_at"] = utc_now()
    checkpoint[
        "global_run_elapsed_seconds"
    ] = time.perf_counter() - run_start

    atomic_write_json(
        CHECKPOINT_JSON,
        checkpoint,
    )
    checkpoint_to_csv(checkpoint)

    build_overviews(MAIN_TIF)

    if (
        PROCESS_FOREST_ZONE
        and FOREST_ZONE_TIF.exists()
    ):
        build_overviews(
            FOREST_ZONE_TIF
        )

    qc_result = run_qc()

    if qc_result == 0:
        checkpoint["status"] = "COMPLETE"
        checkpoint["updated_at"] = utc_now()

        atomic_write_json(
            CHECKPOINT_JSON,
            checkpoint,
        )

    return qc_result


# ============================================================================
# 7. 全球QC
# ============================================================================

def epsg6933_target_row_areas() -> np.ndarray:
    transformer = Transformer.from_crs(
        TARGET_CRS,
        AREA_CRS,
        always_xy=True,
    )

    x0, _ = transformer.transform(
        0.0,
        0.0,
    )
    x1, _ = transformer.transform(
        TARGET_RESOLUTION,
        0.0,
    )
    cell_width = abs(x1 - x0)

    row_areas = np.empty(
        GLOBAL_HEIGHT,
        dtype=np.float64,
    )

    for row in range(GLOBAL_HEIGHT):
        north = (
            GLOBAL_NORTH
            - row * TARGET_RESOLUTION
        )
        south = (
            north - TARGET_RESOLUTION
        )

        _, y_north = transformer.transform(
            0.0,
            north,
        )
        _, y_south = transformer.transform(
            0.0,
            south,
        )

        row_areas[row] = (
            cell_width
            * abs(y_north - y_south)
        )

    return row_areas


def verify_tif_structure(
    path: Path,
    count: int,
) -> dict[str, Any]:
    with rasterio.open(path) as dataset:
        result = {
            "path": str(path),
            "width": dataset.width,
            "height": dataset.height,
            "count": dataset.count,
            "crs": str(dataset.crs),
            "transform": tuple(
                dataset.transform
            ),
            "nodata": dataset.nodata,
            "descriptions": list(
                dataset.descriptions
            ),
        }

    result["passes"] = (
        result["width"] == GLOBAL_WIDTH
        and result["height"] == GLOBAL_HEIGHT
        and result["count"] == count
        and result["crs"] == "EPSG:4326"
        and np.allclose(
            result["transform"],
            tuple(GLOBAL_TRANSFORM),
            atol=1e-12,
        )
    )

    return result


def run_qc() -> int:
    print("=" * 78)
    print("Data16 IFL 全球结果QC")
    print("=" * 78)

    if not MAIN_TIF.exists():
        raise FileNotFoundError(MAIN_TIF)

    tiles = build_global_tiles()

    if CHECKPOINT_JSON.exists():
        checkpoint = json.loads(
            CHECKPOINT_JSON.read_text(
                encoding="utf-8"
            )
        )
        completed_count = len(
            checkpoint.get(
                "completed_tiles",
                {},
            )
        )
    else:
        checkpoint = {}
        completed_count = 0

    structure = verify_tif_structure(
        MAIN_TIF,
        10,
    )

    forest_structure = None

    if (
        PROCESS_FOREST_ZONE
        and FOREST_ZONE_TIF.exists()
    ):
        forest_structure = (
            verify_tif_structure(
                FOREST_ZONE_TIF,
                1,
            )
        )

    row_areas = (
        epsg6933_target_row_areas()
    )

    band_stats = [
        {
            "band_index": index,
            "band": BAND_NAMES[index - 1],
            "min": math.inf,
            "max": -math.inf,
            "sum": 0.0,
            "count": 0,
            "nan_count": 0,
            "inf_count": 0,
            "below_zero_count": 0,
            "above_one_count": 0,
            "area_km2": 0.0,
        }
        for index in range(1, 11)
    ]

    monotonic_violation_count = 0
    monotonic_max_increase = 0.0

    with rasterio.open(
        MAIN_TIF
    ) as dataset:
        for tile in tiles:
            window = Window(
                tile["col_off"],
                tile["row_off"],
                tile["target_width"],
                tile["target_height"],
            )

            stack = dataset.read(
                window=window
            ).astype(np.float64)

            area = row_areas[
                tile["row_off"]:
                tile["row_off"]
                + tile["target_height"]
            ][:, None]

            for band_index in range(10):
                array = stack[band_index]
                finite = np.isfinite(array)

                stats = band_stats[
                    band_index
                ]

                stats["nan_count"] += int(
                    np.isnan(array).sum()
                )
                stats["inf_count"] += int(
                    np.isinf(array).sum()
                )
                stats[
                    "below_zero_count"
                ] += int(
                    (array < -1e-7).sum()
                )
                stats[
                    "above_one_count"
                ] += int(
                    (array > 1 + 1e-7).sum()
                )

                if finite.any():
                    values = array[finite]
                    stats["min"] = min(
                        stats["min"],
                        float(values.min()),
                    )
                    stats["max"] = max(
                        stats["max"],
                        float(values.max()),
                    )
                    stats["sum"] += float(
                        values.sum()
                    )
                    stats["count"] += int(
                        values.size
                    )

                stats["area_km2"] += float(
                    np.sum(
                        np.where(
                            finite,
                            array,
                            0.0,
                        )
                        * area
                    )
                    / 1_000_000.0
                )

            epochs = stack[:5]
            increases = np.stack(
                [
                    epochs[1] - epochs[0],
                    epochs[2] - epochs[1],
                    epochs[3] - epochs[2],
                    epochs[4] - epochs[3],
                ],
                axis=0,
            )

            monotonic_violation_count += int(
                (
                    increases
                    > MONOTONIC_TOLERANCE
                ).any(axis=0).sum()
            )

            monotonic_max_increase = max(
                monotonic_max_increase,
                float(increases.max()),
            )

    for stats in band_stats:
        stats["mean"] = (
            stats["sum"] / stats["count"]
            if stats["count"] > 0
            else None
        )

        stats["passes"] = (
            stats["nan_count"] == 0
            and stats["inf_count"] == 0
            and stats[
                "below_zero_count"
            ]
            == 0
            and stats[
                "above_one_count"
            ]
            == 0
            and stats["min"] >= -1e-7
            and stats["max"] <= 1 + 1e-7
        )

    with FINAL_QC_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=list(
                band_stats[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(band_stats)

    all_bands_pass = all(
        item["passes"]
        for item in band_stats
    )

    all_tiles_complete = (
        completed_count == len(tiles)
    )

    qc_pass = (
        structure["passes"]
        and all_bands_pass
        and all_tiles_complete
        and (
            forest_structure is None
            or forest_structure[
                "passes"
            ]
        )
    )

    report = {
        "generated_at": utc_now(),
        "version": VERSION,
        "qc_pass": qc_pass,
        "main_structure": structure,
        "forest_zone_structure": (
            forest_structure
        ),
        "completed_tiles": completed_count,
        "expected_tiles": len(tiles),
        "all_tiles_complete": (
            all_tiles_complete
        ),
        "band_stats": band_stats,
        "monotonic_tolerance": (
            MONOTONIC_TOLERANCE
        ),
        "monotonic_violation_cells": (
            monotonic_violation_count
        ),
        "monotonic_max_increase": (
            monotonic_max_increase
        ),
    }

    atomic_write_json(
        FINAL_QC_JSON,
        report,
    )

    lines = [
        "Data 16：IFL全球0.05°正式结果QC报告",
        "=" * 78,
        f"生成时间：{report['generated_at']}",
        f"主TIF：{MAIN_TIF}",
        f"主TIF结构通过：{structure['passes']}",
        (
            "完成瓦片："
            f"{completed_count}/{len(tiles)}"
        ),
        (
            "所有瓦片完成："
            f"{all_tiles_complete}"
        ),
        (
            "所有波段数值通过："
            f"{all_bands_pass}"
        ),
        (
            "时间单调性容差："
            f"{MONOTONIC_TOLERANCE}"
        ),
        (
            "超过容差的网格数："
            f"{monotonic_violation_count}"
        ),
        (
            "最大后期增加："
            f"{monotonic_max_increase:.10f}"
        ),
        "",
        "波段统计",
        "-" * 78,
    ]

    for item in band_stats:
        lines.append(
            f"{item['band']}: "
            f"min={item['min']:.8f}, "
            f"max={item['max']:.8f}, "
            f"mean={item['mean']:.8f}, "
            f"area={item['area_km2']:.3f} km², "
            f"PASS={item['passes']}"
        )

    lines.extend(
        [
            "",
            f"最终QC通过：{qc_pass}",
        ]
    )

    FINAL_QC_TXT.write_text(
        "\n".join(lines),
        encoding="utf-8-sig",
    )

    print(
        f"全球QC完成：{qc_pass}"
    )
    print(
        f"报告：{FINAL_QC_TXT}"
    )

    return 0 if qc_pass else 4


# ============================================================================
# 8. 命令行
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Data16 IFL global production"
        )
    )

    parser.add_argument(
        "--mode",
        choices=[
            "pilot",
            "global",
            "qc",
        ],
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode == "pilot":
        return run_pilot()

    if args.mode == "global":
        return run_global()

    if args.mode == "qc":
        return run_qc()

    raise RuntimeError(
        f"未知模式：{args.mode}"
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print(
            "\n运行失败。GLOBAL模式已完成瓦片会保留；"
            "修复问题后重新运行会断点续跑。"
        )
        sys.exit(1)
