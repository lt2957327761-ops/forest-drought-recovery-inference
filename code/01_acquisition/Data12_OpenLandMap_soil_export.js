/**** DATA 12B FORMAL EXPORT v02
 *
 * OPENLANDMAP SOIL HYDRAULIC AND EDAPHIC BASELINE
 *
 * GEE sources (all approximately 250 m):
 *   1. OpenLandMap clay content
 *   2. OpenLandMap sand content
 *   3. OpenLandMap soil organic carbon
 *   4. OpenLandMap fine-earth bulk density
 *   5. OpenLandMap soil pH in H2O
 *   6. OpenLandMap soil water content at 33 kPa
 *
 * Selected standard depths:
 *   0 cm, 30 cm and 100 cm
 *
 * Purpose:
 *   Provide static soil controls for global forest-resilience analysis:
 *   texture, organic matter, compaction, acidity and field capacity.
 *
 * Formal spatial partition:
 *   57 land / island / mixed 30-degree tiles
 *   Three confirmed pure-ocean tiles are skipped.
 *
 * Target:
 *   EPSG:4326
 *   0.05 degree
 *
 * Output:
 *   57 tasks by default
 *   19 float32 bands per tile
 *
 * Conversion rules:
 *   - Clay and sand: source values already represent percent.
 *   - Organic carbon: source values are x 5 g/kg; multiply by 5.
 *   - Bulk density: source values are 10 x kg/m3; multiply by 10.
 *   - pH: source values are pH x 10; divide by 10.
 *   - Field capacity: source values represent volumetric percent.
 *
 * Important:
 *   - One common native-pixel support mask is required across all
 *     18 selected source bands.
 *   - Valid zero values are retained.
 *   - No forest mask is applied during export.
 *   - Later forest analysis must intersect this file with the common
 *     forest-analysis mask.
 *   - Source images are clipped before reduceResolution().
 *   - No explicit reproject() is used.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  claySource:
    'OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02',

  sandSource:
    'OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02',

  organicCarbonSource:
    'OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02',

  bulkDensitySource:
    'OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02',

  phSource:
    'OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02',

  fieldCapacitySource:
    'OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01',

  selectedDepthBands:
    ['b0', 'b30', 'b100'],

  selectedDepthLabels:
    ['0cm', '30cm', '100cm'],

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
    0.20,

  maxPixelsReduce:
    4096,

  maxPixelsExport:
    1e13,

  noData:
    -9999,

  version:
    'v02',

  driveFolder:
    'GlobalForestResilience_Data12_OpenLandMap_' +
    'SoilBaseline_g005_2000_static_land57_v02'
};


var PURE_OCEAN_TILES_NOT_EXPORTED = [
  'W150_W120_S60_S30',
  'W150_W120_N00_N30',
  'W120_W090_S60_S30'
];


function lonCode(value) {
  return value < 0
    ? 'W' + String(Math.abs(value)).padStart(3, '0')
    : 'E' + String(value).padStart(3, '0');
}


function latCode(value) {
  return value < 0
    ? 'S' + String(Math.abs(value)).padStart(2, '0')
    : 'N' + String(value).padStart(2, '0');
}


function buildAllGlobalTiles() {
  var allTiles = [];

  for (var lon0 = -180; lon0 < 180; lon0 += 30) {
    for (var lat0 = -60; lat0 < 85; lat0 += 30) {
      var lon1 = lon0 + 30;
      var lat1 = Math.min(lat0 + 30, 85);

      allTiles.push({
        name:
          lonCode(lon0) + '_' +
          lonCode(lon1) + '_' +
          latCode(lat0) + '_' +
          latCode(lat1),

        lonMin:
          lon0,

        lonMax:
          lon1,

        latMin:
          lat0,

        latMax:
          lat1
      });
    }
  }

  return allTiles;
}


var LAND_TILES = buildAllGlobalTiles().filter(function(tile) {
  return PURE_OCEAN_TILES_NOT_EXPORTED.indexOf(tile.name) === -1;
});


// Change these two values only when a smaller task batch is required.
// The default values create all 57 tasks.
var START_TILE_INDEX = 0;
var END_TILE_INDEX = 57;  // Exclusive.


var EXPORT_TILES = LAND_TILES.slice(
  START_TILE_INDEX,
  END_TILE_INDEX
);


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


function supportObservation(
  image,
  bandName
) {
  return image
    .select(
      bandName
    )
    .toFloat()
    .rename(
      'support_observation'
    );
}


function addImageListAsBands(
  imageList
) {
  var stack = ee.Image(
    imageList[0]
  );


  for (
    var index = 1;
    index < imageList.length;
    index++
  ) {
    stack = stack.addBands(
      imageList[index]
    );
  }


  return stack;
}


// ============================================================
// 2. LOAD STATIC SOURCES
// ============================================================

var claySource = ee.Image(
  CONFIG.claySource
);


var sandSource = ee.Image(
  CONFIG.sandSource
);


var organicCarbonSource = ee.Image(
  CONFIG.organicCarbonSource
);


var bulkDensitySource = ee.Image(
  CONFIG.bulkDensitySource
);


var phSource = ee.Image(
  CONFIG.phSource
);


var fieldCapacitySource = ee.Image(
  CONFIG.fieldCapacitySource
);


var referenceProjection = claySource
  .select('b0')
  .projection();


print('============================================================');
print('DATA 12A OPENLANDMAP SOIL BASELINE FORMAL EXPORT v02');
print('Clay bands:', claySource.bandNames());
print('Sand bands:', sandSource.bandNames());
print(
  'Organic-carbon bands:',
  organicCarbonSource.bandNames()
);
print(
  'Bulk-density bands:',
  bulkDensitySource.bandNames()
);
print('pH bands:', phSource.bandNames());
print(
  'Field-capacity bands:',
  fieldCapacitySource.bandNames()
);
print(
  'Reference nominal scale, expected about 250 m:',
  referenceProjection.nominalScale()
);
print(
  'Selected depths:',
  CONFIG.selectedDepthLabels
);
print(
  'Land / island / mixed tile count, expected 57:',
  LAND_TILES.length
);
print(
  'Selected formal task count:',
  EXPORT_TILES.length
);
print(
  'Pure-ocean tiles skipped:',
  PURE_OCEAN_TILES_NOT_EXPORTED
);
print('Output resolution: 0.05 degree');
print('Output bands per tile: 19');
print('============================================================');


// ============================================================
// 3. BUILD ONE TILE'S 19-BAND NATIVE STACK
// ============================================================

function buildNativeSoilStack(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var clay = claySource.clip(
    bufferedRegion
  );


  var sand = sandSource.clip(
    bufferedRegion
  );


  var organicCarbon = organicCarbonSource.clip(
    bufferedRegion
  );


  var bulkDensity = bulkDensitySource.clip(
    bufferedRegion
  );


  var ph = phSource.clip(
    bufferedRegion
  );


  var fieldCapacity = fieldCapacitySource.clip(
    bufferedRegion
  );


  var supportImages = [];

  var valueImages = [];


  for (
    var depthIndex = 0;
    depthIndex < CONFIG.selectedDepthBands.length;
    depthIndex++
  ) {
    var sourceBand =
      CONFIG.selectedDepthBands[
        depthIndex
      ];


    var depthLabel =
      CONFIG.selectedDepthLabels[
        depthIndex
      ];


    supportImages.push(
      supportObservation(
        clay,
        sourceBand
      )
    );


    supportImages.push(
      supportObservation(
        sand,
        sourceBand
      )
    );


    supportImages.push(
      supportObservation(
        organicCarbon,
        sourceBand
      )
    );


    supportImages.push(
      supportObservation(
        bulkDensity,
        sourceBand
      )
    );


    supportImages.push(
      supportObservation(
        ph,
        sourceBand
      )
    );


    supportImages.push(
      supportObservation(
        fieldCapacity,
        sourceBand
      )
    );


    valueImages.push(
      clay
        .select(
          sourceBand
        )
        .toFloat()
        .rename(
          'clay_content_pct_' +
          depthLabel
        )
    );


    valueImages.push(
      sand
        .select(
          sourceBand
        )
        .toFloat()
        .rename(
          'sand_content_pct_' +
          depthLabel
        )
    );


    valueImages.push(
      organicCarbon
        .select(
          sourceBand
        )
        .multiply(
          5
        )
        .toFloat()
        .rename(
          'soil_organic_carbon_g_kg_' +
          depthLabel
        )
    );


    valueImages.push(
      bulkDensity
        .select(
          sourceBand
        )
        .multiply(
          10
        )
        .toFloat()
        .rename(
          'bulk_density_kg_m3_' +
          depthLabel
        )
    );


    valueImages.push(
      ph
        .select(
          sourceBand
        )
        .divide(
          10
        )
        .toFloat()
        .rename(
          'soil_ph_h2o_' +
          depthLabel
        )
    );


    valueImages.push(
      fieldCapacity
        .select(
          sourceBand
        )
        .toFloat()
        .rename(
          'field_capacity_vol_pct_' +
          depthLabel
        )
    );
  }


  var requiredSupportCount =
    supportImages.length;


  var validSupportCount = ee.ImageCollection
    .fromImages(
      supportImages
    )
    .count();


  var commonSupport = validSupportCount
    .eq(
      requiredSupportCount
    )
    .unmask(
      0,
      false
    )
    .toFloat()
    .rename(
      'soil_common_support_area_frac'
    );


  var valueStack = addImageListAsBands(
    valueImages
  )
    .updateMask(
      commonSupport.eq(1)
    )
    .toFloat();


  return commonSupport
    .addBands(
      valueStack
    )
    .toFloat()
    .setDefaultProjection(
      referenceProjection
    )
    .clip(
      bufferedRegion
    );
}


// ============================================================
// 4. AGGREGATE AND EXPORT ONE TEST TILE
// ============================================================

function exportOneFormalTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );


  var nativeStack = buildNativeSoilStack(
    tile
  );


  var outputG005 = nativeStack
    .reduceResolution({
      reducer:
        ee.Reducer.mean(),

      bestEffort:
        false,

      maxPixels:
        CONFIG.maxPixelsReduce
    })
    .toFloat()
    .clip(
      exactRegion
    )
    .set({
      dataset_group:
        'OpenLandMap soil hydraulic and edaphic baseline',

      selected_depths_cm:
        '0,30,100',

      tile_name:
        tile.name,

      target_grid:
        'g005',

      target_crs:
        CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      common_support:
        'simultaneously valid across 6 properties x 3 depths = 18 source bands',

      conversion_soc:
        'raw x 5 -> g/kg',

      conversion_bulk_density:
        'raw x 10 -> kg/m3',

      conversion_ph:
        'raw / 10 -> pH',

      forest_mask_note:
        'no forest mask applied during export',

      range_note:
        'catalog min/max values are estimated; no clipping applied during export',

      field_capacity_note:
        '33 kPa volumetric water content, not plant-available water capacity',

      version:
        CONFIG.version
    });


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
    'OpenLandMap_SoilBaseline_' +
    'g005_tile_' +
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
    'Expected output filename:',
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
// 5. CREATE FORMAL 30-DEGREE TASKS
// ============================================================

EXPORT_TILES.forEach(function(tile) {
  exportOneFormalTile(
    tile
  );
});


print('============================================================');
print('DATA 12B FORMAL TASK CREATION COMPLETED');
print('Total formal land-tile count: 57');
print('Tasks created in current range:', EXPORT_TILES.length);
print('Expected output bands per tile: 19');
print('Standard dimensions: 600x600');
print('Northern 60-85 N dimensions: 600x500');
print('Output resolution: 0.05 degree');
print('============================================================');


// No Map.addLayer(), reduceRegion(), chart, or global diagnostics.
