/**** DATA 13B FINAL EXPORT v03 — FIXED LAND368 — BATCH 01
 *
 * MERIT DEM TOPOGRAPHIC BASELINE
 *
 * GEE source:
 *   MERIT/DEM/v1_0_3
 *
 * Purpose:
 *   Provide static terrain controls for global forest-resilience analysis:
 *   elevation, sub-grid elevation variability, local relief and slope.
 *
 * Source:
 *   - MERIT DEM
 *   - approximately 3 arc-seconds / 92.77 m
 *   - elevation in meters relative to the EGM96 geoid
 *
 * Final fixed inventory:
 *   - 540 total 10-degree tiles
 *   - 368 fixed land / island / mixed GEE exports
 *   - 172 fixed pure-ocean tiles are not exported
 *   - inventory: MOD44B_g010_540tiles_land_screen_2020_v02.csv
 *   - batch 01 of 15: 25 tasks
 *
 * Target:
 *   EPSG:4326
 *   0.05 degree
 *
 * Output:
 *   8 float32 bands per retained tile
 *
 * Bands:
 *   1 terrain_support_area_frac
 *   2 elevation_mean_valid_m
 *   3 elevation_std_valid_m
 *   4 elevation_min_valid_m
 *   5 elevation_max_valid_m
 *   6 elevation_relief_range_valid_m
 *   7 slope_mean_valid_degree
 *   8 slope_std_valid_degree
 *
 * Important:
 *   - Support requires both elevation and derived slope to be valid.
 *   - Relief is recomputed as aggregated maximum minus minimum.
 *   - No forest mask is applied during export.
 *   - Source values are clipped tile-by-tile before aggregation.
 *   - No explicit reproject() call is used.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  source:
    'MERIT/DEM/v1_0_3',

  targetCrs:
    'EPSG:4326',

  targetResolutionDegree:
    0.05,

  globalLonMin:
    -180,

  globalLonMax:
    180,

  globalLatMin:
    -60,

  globalLatMax:
    85,

  bufferDegree:
    0.10,

  maxPixelsReduce:
    8192,

  maxPixelsExport:
    1e13,

  noData:
    -9999,

  version:
    'v03',

  driveFolder:
    'GlobalForestResilience_Data13_MERIT_' +
    'Topography_g005_10deg_land368_static_v03'
};


// Fixed inventory source:
// MOD44B_g010_540tiles_land_screen_2020_v02.csv
// export_required = 1
// This batch: 25 of the fixed 368 land/island/mixed tiles.

var EXPORT_TILES = [
  {
    tileId:
      2,

    name:
      'W180_W170_S50_S40',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      -50,

    latMax:
      -40,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      4,

    name:
      'W180_W170_S30_S20',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      -30,

    latMax:
      -20,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      5,

    name:
      'W180_W170_S20_S10',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      -20,

    latMax:
      -10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      6,

    name:
      'W180_W170_S10_N00',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      -10,

    latMax:
      0,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      7,

    name:
      'W180_W170_N00_N10',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      0,

    latMax:
      10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      9,

    name:
      'W180_W170_N20_N30',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      20,

    latMax:
      30,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      12,

    name:
      'W180_W170_N50_N60',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      50,

    latMax:
      60,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      13,

    name:
      'W180_W170_N60_N70',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      60,

    latMax:
      70,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      14,

    name:
      'W180_W170_N70_N80',

    lonMin:
      -180,

    lonMax:
      -170,

    latMin:
      70,

    latMax:
      80,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      20,

    name:
      'W170_W160_S20_S10',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      -20,

    latMax:
      -10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      21,

    name:
      'W170_W160_S10_N00',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      -10,

    latMax:
      0,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      22,

    name:
      'W170_W160_N00_N10',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      0,

    latMax:
      10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      24,

    name:
      'W170_W160_N20_N30',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      20,

    latMax:
      30,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      27,

    name:
      'W170_W160_N50_N60',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      50,

    latMax:
      60,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      28,

    name:
      'W170_W160_N60_N70',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      60,

    latMax:
      70,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      29,

    name:
      'W170_W160_N70_N80',

    lonMin:
      -170,

    lonMax:
      -160,

    latMin:
      70,

    latMax:
      80,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      34,

    name:
      'W160_W150_S30_S20',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      -30,

    latMax:
      -20,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      35,

    name:
      'W160_W150_S20_S10',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      -20,

    latMax:
      -10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      36,

    name:
      'W160_W150_S10_N00',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      -10,

    latMax:
      0,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      37,

    name:
      'W160_W150_N00_N10',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      0,

    latMax:
      10,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      38,

    name:
      'W160_W150_N10_N20',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      10,

    latMax:
      20,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      39,

    name:
      'W160_W150_N20_N30',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      20,

    latMax:
      30,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      42,

    name:
      'W160_W150_N50_N60',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      50,

    latMax:
      60,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      43,

    name:
      'W160_W150_N60_N70',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      60,

    latMax:
      70,

    expectedWidth:
      200,

    expectedHeight:
      200
  },

  {
    tileId:
      44,

    name:
      'W160_W150_N70_N80',

    lonMin:
      -160,

    lonMax:
      -150,

    latMin:
      70,

    latMax:
      80,

    expectedWidth:
      200,

    expectedHeight:
      200
  }
];


// ============================================================
// 1. HELPERS
// ============================================================

var EPS = 1e-6;


function clamp(value, minimum, maximum) {
  return Math.max(
    minimum,
    Math.min(
      maximum,
      value
    )
  );
}


function exactTileRegion(tile) {
  return ee.Geometry.Rectangle(
    [
      tile.lonMin,
      tile.latMin,
      tile.lonMax,
      tile.latMax
    ],
    null,
    false
  );
}


function bufferedTileRegion(tile) {
  return ee.Geometry.Rectangle(
    [
      clamp(
        tile.lonMin - CONFIG.bufferDegree,
        CONFIG.globalLonMin,
        CONFIG.globalLonMax
      ) + EPS,

      clamp(
        tile.latMin - CONFIG.bufferDegree,
        CONFIG.globalLatMin,
        CONFIG.globalLatMax
      ) + EPS,

      clamp(
        tile.lonMax + CONFIG.bufferDegree,
        CONFIG.globalLonMin,
        CONFIG.globalLonMax
      ) - EPS,

      clamp(
        tile.latMax + CONFIG.bufferDegree,
        CONFIG.globalLatMin,
        CONFIG.globalLatMax
      ) - EPS
    ],
    null,
    false
  );
}


// ============================================================
// 2. SOURCE AND DIAGNOSTICS
// ============================================================

var meritDem = ee.Image(
  CONFIG.source
)
  .select(
    'dem'
  );


var sourceProjection = meritDem
  .projection();


print('============================================================');
print('DATA 13A MERIT TOPOGRAPHY FINAL EXPORT v03 — BATCH 01');
print('Source:', CONFIG.source);
print('Source bands:', meritDem.bandNames());
print(
  'Source nominal scale, expected about 92.77 m:',
  sourceProjection.nominalScale()
);
print(
  'Fixed inventory total land / island / mixed tiles:',
  368
);
print(
  'Fixed inventory pure-ocean tiles not exported:',
  172
);
print(
  'Current batch number:',
  1
);
print(
  'Tasks in current batch, expected 25:',
  EXPORT_TILES.length
);
print('Target resolution: 0.05 degree');
print('Output bands per tile: 8');
print('Standard tile dimensions: 200x200');
print('Northern 80-85 N dimensions: 200x100');
print('reduceResolution graphs per tile: 3 (support, elevation stats, slope stats)');
print('No dynamic land screening is performed.');
print('============================================================');


// ============================================================
// 3. REDUCE ONE SOURCE IMAGE WITH ONE REDUCER
// ============================================================

function aggregateNativeImage(
  nativeImage,
  reducer,
  maxPixels
) {
  return nativeImage
    .reduceResolution({
      reducer:
        reducer,

      bestEffort:
        false,

      maxPixels:
        maxPixels
    })
    .toFloat();
}


// ============================================================
// 4. BUILD ONE 0.05-DEGREE TERRAIN TILE
// ============================================================

function buildTerrainG005(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var elevationNative = meritDem
    .clip(
      bufferedRegion
    )
    .toFloat()
    .rename(
      'elevation_native_m'
    );


  var slopeNative = ee.Terrain
    .slope(
      elevationNative
    )
    .toFloat()
    .rename(
      'slope_native_degree'
    );


  var commonSupportNative = elevationNative
    .mask()
    .and(
      slopeNative.mask()
    )
    .unmask(
      0,
      false
    )
    .toFloat()
    .rename(
      'terrain_support_area_frac'
    );


  var elevationValid = elevationNative
    .updateMask(
      commonSupportNative.eq(1)
    );


  var slopeValid = slopeNative
    .updateMask(
      commonSupportNative.eq(1)
    );


  var supportG005 = aggregateNativeImage(
    commonSupportNative,
    ee.Reducer.mean(),
    CONFIG.maxPixelsReduce
  )
    .rename(
      'terrain_support_area_frac'
    );


  // Use combined reducers to reduce the number of large native-resolution
  // aggregation graphs. The original v01 performed seven separate
  // reduceResolution operations, which was too memory intensive for a
  // 30-degree tile.

  var elevationReducer = ee.Reducer
    .mean()
    .combine({
      reducer2:
        ee.Reducer.stdDev(),

      sharedInputs:
        true
    })
    .combine({
      reducer2:
        ee.Reducer.min(),

      sharedInputs:
        true
    })
    .combine({
      reducer2:
        ee.Reducer.max(),

      sharedInputs:
        true
    });


  var elevationStatsG005 = aggregateNativeImage(
    elevationValid,
    elevationReducer,
    CONFIG.maxPixelsReduce
  )
    .rename([
      'elevation_mean_valid_m',
      'elevation_std_valid_m',
      'elevation_min_valid_m',
      'elevation_max_valid_m'
    ]);


  var elevationMeanG005 = elevationStatsG005
    .select(
      'elevation_mean_valid_m'
    );


  var elevationStdG005 = elevationStatsG005
    .select(
      'elevation_std_valid_m'
    );


  var elevationMinG005 = elevationStatsG005
    .select(
      'elevation_min_valid_m'
    );


  var elevationMaxG005 = elevationStatsG005
    .select(
      'elevation_max_valid_m'
    );


  var elevationReliefG005 = elevationMaxG005
    .subtract(
      elevationMinG005
    )
    .rename(
      'elevation_relief_range_valid_m'
    );


  var slopeReducer = ee.Reducer
    .mean()
    .combine({
      reducer2:
        ee.Reducer.stdDev(),

      sharedInputs:
        true
    });


  var slopeStatsG005 = aggregateNativeImage(
    slopeValid,
    slopeReducer,
    CONFIG.maxPixelsReduce
  )
    .rename([
      'slope_mean_valid_degree',
      'slope_std_valid_degree'
    ]);


  var slopeMeanG005 = slopeStatsG005
    .select(
      'slope_mean_valid_degree'
    );


  var slopeStdG005 = slopeStatsG005
    .select(
      'slope_std_valid_degree'
    );


  return ee.Image.cat([
      supportG005,

      elevationMeanG005,
      elevationStdG005,
      elevationMinG005,
      elevationMaxG005,
      elevationReliefG005,

      slopeMeanG005,
      slopeStdG005
    ])
    .toFloat()
    .clip(
      exactTileRegion(tile)
    )
    .set({
      dataset:
        CONFIG.source,

      tile_name:
        tile.name,

      target_grid:
        'g005',

      target_crs:
        CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      elevation_reference:
        'EGM96 geoid',

      relief_definition:
        '0.05-degree maximum elevation minus minimum elevation',

      slope_method:
        'ee.Terrain.slope from native MERIT DEM',

      forest_mask_note:
        'no forest mask applied during export',

      tile_inventory:
        'MOD44B_g010_540tiles_land_screen_2020_v02; export_required=1',

      fixed_inventory_total:
        368,

      batch_number:
        1,

      dynamic_land_screening:
        'none',

      version:
        CONFIG.version
    });
}


// ============================================================
// 5. EXPORT ONE TEST TILE
// ============================================================

function exportOneFormalTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );


  var outputG005 = buildTerrainG005(
    tile
  );


  var widthPixels = Math.round(
    (tile.lonMax - tile.lonMin) /
    CONFIG.targetResolutionDegree
  );


  var heightPixels = Math.round(
    (tile.latMax - tile.latMin) /
    CONFIG.targetResolutionDegree
  );


  var dimensionsText =
    String(widthPixels) +
    'x' +
    String(heightPixels);


  var outputPrefix =
    'MERIT_Topography_g005_tile_' +
    tile.name +
    '_static_' +
    CONFIG.version;


  print('------------------------------------------------------------');
  print('Preparing tile:', tile.name);
  print(
    'Expected dimensions:',
    dimensionsText
  );
  print(
    'Expected filename:',
    outputPrefix + '.tif'
  );


  Export.image.toDrive({
    image:
      outputG005
        .unmask(
          CONFIG.noData
        )
        .toFloat(),

    description:
      outputPrefix,

    folder:
      CONFIG.driveFolder,

    fileNamePrefix:
      outputPrefix,

    region:
      exactRegion,

    crs:
      CONFIG.targetCrs,

    dimensions:
      dimensionsText,

    maxPixels:
      CONFIG.maxPixelsExport,

    fileFormat:
      'GeoTIFF',

    formatOptions: {
      cloudOptimized:
        true,

      noData:
        CONFIG.noData
    }
  });
}


// ============================================================
// 6. CREATE FIXED-INVENTORY TASKS — BATCH 01
// ============================================================

EXPORT_TILES.forEach(function(tile) {
  exportOneFormalTile(
    tile
  );
});


print('============================================================');
print('DATA 13B FINAL TASK CREATION COMPLETED');
print('Batch number: 01 / 15');
print('Tasks created in current batch: 25');
print('Fixed land / island / mixed total: 368');
print('Fixed pure-ocean total not exported: 172');
print('Expected output bands per tile: 8');
print('Output resolution: 0.05 degree');
print('============================================================');


// No Map.addLayer(), reduceRegion(), chart, or global diagnostics.
