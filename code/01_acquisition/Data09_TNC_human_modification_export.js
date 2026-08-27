/**** DATA 09 FORMAL EXPORT v05
 *
 * TNC GLOBAL HUMAN MODIFICATION v3
 *
 * Dataset:
 *   TNC/HM/v3/300m_c
 *
 * Source years retained in one static multitemporal stack:
 *   2000, 2005, 2010, 2015 and 2020
 *
 * Formal export:
 *   - 57 land / island / mixed 30-degree tiles
 *   - three confirmed pure-ocean tiles skipped
 *   - native 300 m source aggregated to fixed 0.05-degree tiles
 *   - 15 float32 bands per tile
 *
 * Target grid:
 *   EPSG:4326
 *   longitude [-180, 180]
 *   latitude  [-60, 85]
 *   0.05 degree
 *
 * Standard output tile:
 *   600 x 600 pixels
 *
 * Northern 60–85 N output tile:
 *   600 x 500 pixels
 *
 * Output bands:
 *   1  common_support_area_frac_2000_2020
 *   2  human_modification_all_2000
 *   3  human_modification_all_2005
 *   4  human_modification_all_2010
 *   5  human_modification_all_2015
 *   6  human_modification_all_2020
 *   7  human_modification_delta_2000_2020
 *   8  agriculture_2020
 *   9  built_up_2020
 *   10 energy_production_and_mining_2020
 *   11 biological_resource_use_2020
 *   12 human_accessibility_2020
 *   13 natural_system_modification_2020
 *   14 pollution_2020
 *   15 transportation_and_service_corridors_2020
 *
 * Important:
 *   - The 15-band logic is identical to the QC-passed v04 test.
 *   - All 14 numeric variables use one common native-pixel support mask.
 *   - Support requires simultaneous validity of 13 source bands.
 *   - Source images are clipped tile-by-tile before reduceResolution().
 *   - No explicit reproject() is used.
 *   - No intact/managed threshold is imposed during export.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  source:
    'TNC/HM/v3/300m_c',

  years:
    [2000, 2005, 2010, 2015, 2020],

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
    'v05',

  driveFolder:
    'GlobalForestResilience_Data09_TNC_HM_v3_' +
    'g005_2000_2020_v05_land57'
};


// ============================================================
// 1. FORMAL 57-TILE FRAMEWORK
// ============================================================

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


var START_TILE_INDEX = 0;
var END_TILE_INDEX = 57;  // Exclusive.


var EXPORT_TILES = LAND_TILES.slice(
  START_TILE_INDEX,
  END_TILE_INDEX
);


// ============================================================
// 2. HELPERS
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


function getYearImage(collection, year, region) {
  return ee.Image(
      collection
        .filter(
          ee.Filter.calendarRange(
            year,
            year,
            'year'
          )
        )
        .first()
    )
    .clip(
      region
    );
}


function makeSupportObservation(
  image,
  sourceBand
) {
  return image
    .select(
      sourceBand
    )
    .toFloat()
    .rename(
      'support_observation'
    );
}


function prepareCombined(
  image,
  year,
  commonSupportNative
) {
  return image
    .select(
      'All_threats_combined'
    )
    .updateMask(
      commonSupportNative.eq(1)
    )
    .toFloat()
    .rename(
      'human_modification_all_' +
      year
    );
}


function prepare2020Component(
  image2020,
  sourceBand,
  outputBand,
  commonSupportNative
) {
  return image2020
    .select(
      sourceBand
    )
    .updateMask(
      commonSupportNative.eq(1)
    )
    .toFloat()
    .rename(
      outputBand
    );
}


// ============================================================
// 3. SOURCE COLLECTION
// ============================================================

var collection = ee.ImageCollection(
  CONFIG.source
);


print('============================================================');
print('DATA 09 TNC HUMAN MODIFICATION FORMAL EXPORT v05');
print('Source:', CONFIG.source);
print('Source years:', CONFIG.years);
print(
  'Land / island / mixed tile count, expected 57:',
  LAND_TILES.length
);
print(
  'Selected task count, expected 57:',
  EXPORT_TILES.length
);
print(
  'Pure-ocean tiles skipped:',
  PURE_OCEAN_TILES_NOT_EXPORTED
);
print('Output resolution: 0.05 degree');
print('Output bands per tile: 15');
print('Explicit reproject calls: 0');
print('Drive folder:', CONFIG.driveFolder);
print('============================================================');


CONFIG.years.forEach(function(year) {
  print(
    'Source image count for ' + year + ', expected 1:',
    collection
      .filter(
        ee.Filter.calendarRange(
          year,
          year,
          'year'
        )
      )
      .size()
  );
});


// ============================================================
// 4. BUILD ONE TILE'S QC-PASSED 15-BAND STACK
// ============================================================

function buildTileStack(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var image2000 = getYearImage(
    collection,
    2000,
    bufferedRegion
  );


  var image2005 = getYearImage(
    collection,
    2005,
    bufferedRegion
  );


  var image2010 = getYearImage(
    collection,
    2010,
    bufferedRegion
  );


  var image2015 = getYearImage(
    collection,
    2015,
    bufferedRegion
  );


  var image2020 = getYearImage(
    collection,
    2020,
    bufferedRegion
  );


  var nativeProjection = image2000
    .select(
      'All_threats_combined'
    )
    .projection();


  var supportSourceImages = [
    makeSupportObservation(
      image2000,
      'All_threats_combined'
    ),

    makeSupportObservation(
      image2005,
      'All_threats_combined'
    ),

    makeSupportObservation(
      image2010,
      'All_threats_combined'
    ),

    makeSupportObservation(
      image2015,
      'All_threats_combined'
    ),

    makeSupportObservation(
      image2020,
      'All_threats_combined'
    ),

    makeSupportObservation(
      image2020,
      'Agriculture'
    ),

    makeSupportObservation(
      image2020,
      'Built_up'
    ),

    makeSupportObservation(
      image2020,
      'Energy_production_and_mining'
    ),

    makeSupportObservation(
      image2020,
      'Biological_resource_use'
    ),

    makeSupportObservation(
      image2020,
      'Human_accessibility'
    ),

    makeSupportObservation(
      image2020,
      'Natural_system_modification'
    ),

    makeSupportObservation(
      image2020,
      'Pollution'
    ),

    makeSupportObservation(
      image2020,
      'Transportation_and_service_corridors'
    )
  ];


  var requiredSupportBandCount =
    supportSourceImages.length;


  var validSupportBandCount = ee.ImageCollection
    .fromImages(
      supportSourceImages
    )
    .count()
    .rename(
      'valid_support_band_count'
    );


  var commonSupportNative = validSupportBandCount
    .eq(
      requiredSupportBandCount
    )
    .unmask(0)
    .toFloat()
    .rename(
      'common_support_area_frac_2000_2020'
    );


  var hm2000 = prepareCombined(
    image2000,
    2000,
    commonSupportNative
  );


  var hm2005 = prepareCombined(
    image2005,
    2005,
    commonSupportNative
  );


  var hm2010 = prepareCombined(
    image2010,
    2010,
    commonSupportNative
  );


  var hm2015 = prepareCombined(
    image2015,
    2015,
    commonSupportNative
  );


  var hm2020 = prepareCombined(
    image2020,
    2020,
    commonSupportNative
  );


  var hmDelta2000To2020 = hm2020
    .subtract(
      hm2000
    )
    .rename(
      'human_modification_delta_2000_2020'
    );


  var agriculture2020 = prepare2020Component(
    image2020,
    'Agriculture',
    'agriculture_2020',
    commonSupportNative
  );


  var builtUp2020 = prepare2020Component(
    image2020,
    'Built_up',
    'built_up_2020',
    commonSupportNative
  );


  var energyMining2020 = prepare2020Component(
    image2020,
    'Energy_production_and_mining',
    'energy_production_and_mining_2020',
    commonSupportNative
  );


  var biologicalResourceUse2020 = prepare2020Component(
    image2020,
    'Biological_resource_use',
    'biological_resource_use_2020',
    commonSupportNative
  );


  var humanAccessibility2020 = prepare2020Component(
    image2020,
    'Human_accessibility',
    'human_accessibility_2020',
    commonSupportNative
  );


  var naturalSystemModification2020 = prepare2020Component(
    image2020,
    'Natural_system_modification',
    'natural_system_modification_2020',
    commonSupportNative
  );


  var pollution2020 = prepare2020Component(
    image2020,
    'Pollution',
    'pollution_2020',
    commonSupportNative
  );


  var transportation2020 = prepare2020Component(
    image2020,
    'Transportation_and_service_corridors',
    'transportation_and_service_corridors_2020',
    commonSupportNative
  );


  return ee.Image.cat([
      commonSupportNative,

      hm2000,
      hm2005,
      hm2010,
      hm2015,
      hm2020,

      hmDelta2000To2020,

      agriculture2020,
      builtUp2020,
      energyMining2020,
      biologicalResourceUse2020,
      humanAccessibility2020,
      naturalSystemModification2020,
      pollution2020,
      transportation2020
    ])
    .toFloat()
    .setDefaultProjection(
      nativeProjection
    )
    .clip(
      bufferedRegion
    );
}


// ============================================================
// 5. EXPORT ONE 30-DEGREE TILE
// ============================================================

function exportOneTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );


  var nativeTileStack = buildTileStack(
    tile
  );


  var outputG005 = nativeTileStack
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
      dataset:
        CONFIG.source,

      source_years:
        '2000,2005,2010,2015,2020',

      tile_name:
        tile.name,

      target_grid:
        'g005',

      target_crs:
        CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      aggregation:
        'native 300m source clipped per tile before one reduceResolution mean',

      temporal_support:
        'simultaneously valid native pixels across 5 HM years and 8 component bands',

      classification_note:
        'continuous human modification; no intact-managed threshold imposed',

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
    'TNC_HM_v3_g005_tile_' +
    tile.name +
    '_2000_2020_' +
    CONFIG.version;


  print('------------------------------------------------------------');
  print('Preparing tile:', tile.name);
  print(
    'Exact bounds:',
    [
      tile.lonMin,
      tile.latMin,
      tile.lonMax,
      tile.latMax
    ]
  );
  print(
    'Forced output dimensions:',
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
// 6. CREATE ALL 57 FORMAL TASKS
// ============================================================

EXPORT_TILES.forEach(function(tile) {
  exportOneTile(
    tile
  );
});


print('============================================================');
print('FORMAL TASK CREATION COMPLETED');
print('Expected task count: 57');
print('Tasks created:', EXPORT_TILES.length);
print('Output resolution: 0.05 degree');
print('Output bands per tile: 15');
print('Pure-ocean tasks created: 0');
print('============================================================');


// No Map.addLayer(), reduceRegion(), chart, or global diagnostics.
