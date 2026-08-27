/**** DATA 06 FORMAL EXPORT — MCD64A1 BURNED AREA YEAR 2001
 *
 * Dataset:
 *   MODIS/061/MCD64A1
 *
 * Formal period:
 *   2001–2024
 *
 * This script:
 *   - processes 2001;
 *   - exports 57 land / island / mixed 30° tiles;
 *   - skips three confirmed pure-ocean tiles;
 *   - aggregates monthly native ~500 m data to fixed 0.05° tiles;
 *   - exports 41 float32 bands per tile;
 *   - uses the projection and monthly-fraction logic verified in v04.
 *
 * Burned-pixel rule:
 *   BurnDate > 0
 *   AND QA bit 0 = land
 *   AND QA bit 1 = sufficient valid data
 *
 * Target grid:
 *   EPSG:4326
 *   0.05 degree
 *   [-180, -60, 180, 85]
 *
 * Standard tile:
 *   600 x 600 pixels.
 *
 * Northern 60–85 N tile:
 *   600 x 500 pixels.
 *
 * NoData:
 *   -9999
 *
 * IMPORTANT:
 *   - No explicit reproject() is used.
 *   - Native data are clipped before reduceResolution().
 *   - setDefaultProjection() restores the native MODIS projection metadata.
 *   - Exact region plus dimensions prevents extra edge rows.
 *   - This file creates 57 Drive export tasks.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  source: 'MODIS/061/MCD64A1',

  year: 2001,

  targetCrs: 'EPSG:4326',

  globalLonMin: -180,
  globalLonMax: 180,
  globalLatMin: -60,
  globalLatMax: 85,

  targetResolutionDegree: 0.05,

  bufferDegree: 0.20,

  maxPixelsReduce: 2048,

  maxPixelsExport: 1e13,

  noData: -9999,

  version: 'v05',

  driveFolder:
    'GlobalForestResilience_Data06_MCD64A1_' +
    'burned_area_g005_2001_v05_land57'
};


// ============================================================
// 1. TILE FRAMEWORK
// ============================================================

var PURE_OCEAN_TILES_NOT_EXPORTED = [
  'W150_W120_S60_S30',
  'W150_W120_N00_N30',
  'W120_W090_S60_S30'
];

var START_TILE_INDEX = 0;
var END_TILE_INDEX = 57;  // Exclusive.


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

        lonMin: lon0,
        lonMax: lon1,
        latMin: lat0,
        latMax: lat1
      });
    }
  }

  return allTiles;
}


var LAND_TILES = buildAllGlobalTiles().filter(function(tile) {
  return PURE_OCEAN_TILES_NOT_EXPORTED.indexOf(tile.name) === -1;
});


var EXPORT_TILES = LAND_TILES.slice(
  START_TILE_INDEX,
  END_TILE_INDEX
);


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


function monthText(month) {
  return month < 10 ? '0' + month : '' + month;
}


function extractBit(image, bitPosition) {
  return image
    .rightShift(bitPosition)
    .bitwiseAnd(1);
}


// ============================================================
// 3. LOAD ONE COMPLETE YEAR
// ============================================================

var YEAR = CONFIG.year;

var yearStart = ee.Date.fromYMD(
  YEAR,
  1,
  1
);

var yearEnd = yearStart.advance(
  1,
  'year'
);


var yearlyCollection = ee.ImageCollection(
    CONFIG.source
  )
  .filterDate(
    yearStart,
    yearEnd
  )
  .sort(
    'system:time_start'
  );


var referenceImage = ee.Image(
  yearlyCollection.first()
);

var nativeProjection = referenceImage
  .select('BurnDate')
  .projection();


print('============================================================');
print('DATA 06 MCD64A1 FORMAL EXPORT v05');
print('Year:', YEAR);
print(
  'Monthly source image count, expected 12:',
  yearlyCollection.size()
);
print(
  'Land/mixed tile count, expected 57:',
  LAND_TILES.length
);
print(
  'Selected task count:',
  EXPORT_TILES.length
);
print(
  'Pure-ocean tiles skipped:',
  PURE_OCEAN_TILES_NOT_EXPORTED
);
print(
  'Native nominal scale, expected about 463 m:',
  nativeProjection.nominalScale()
);
print('Output resolution: 0.05 degree');
print('Output bands per tile: 41');
print('Explicit reproject calls: 0');
print('Drive folder:', CONFIG.driveFolder);
print('============================================================');


// ============================================================
// 4. PREPARE EACH MONTH
// ============================================================

function prepareMonthlyImage(image) {
  image = ee.Image(image);

  var date = ee.Date(
    image.get('system:time_start')
  );

  var month = ee.Number(
    date.get('month')
  );


  var burnDate = image
    .select('BurnDate')
    .toFloat();


  var uncertainty = image
    .select('Uncertainty')
    .toFloat();


  var qa = image
    .select('QA');


  var land = extractBit(
    qa,
    0
  )
    .eq(1)
    .unmask(0)
    .toFloat()
    .rename('land_flag');


  var sufficientValidData = extractBit(
    qa,
    1
  )
    .eq(1);


  var validLand = land
    .eq(1)
    .and(
      sufficientValidData
    )
    .unmask(0)
    .toFloat()
    .rename('valid_land_flag');


  var shortened = extractBit(
    qa,
    2
  )
    .eq(1)
    .and(
      validLand.eq(1)
    )
    .unmask(0)
    .toFloat()
    .rename('shortened_mapping_flag');


  var fullMapping = validLand
    .eq(1)
    .and(
      shortened.eq(0)
    )
    .unmask(0)
    .toFloat()
    .rename('full_mapping_flag');


  var relabeled = extractBit(
    qa,
    3
  )
    .eq(1)
    .and(
      validLand.eq(1)
    )
    .unmask(0)
    .toFloat()
    .rename('relabeled_flag');


  var specialConditionCode = qa
    .rightShift(5)
    .bitwiseAnd(7);


  var specialCondition = specialConditionCode
    .gt(0)
    .and(
      land.eq(1)
    )
    .unmask(0)
    .toFloat()
    .rename('special_condition_flag');


  var burnedFlag = burnDate
    .gt(0)
    .and(
      validLand.eq(1)
    )
    .unmask(0)
    .toFloat()
    .rename('burned_flag');


  var burnedValidLand = burnedFlag
    .updateMask(
      validLand.eq(1)
    )
    .toFloat()
    .rename('burned_valid_land');


  var burnDoy = burnDate
    .updateMask(
      burnedFlag.eq(1)
    )
    .rename('burn_doy');


  var burnedUncertainty = uncertainty
    .updateMask(
      burnedFlag.eq(1)
    )
    .rename('burn_uncertainty');


  return ee.Image.cat([
      land,
      validLand,
      fullMapping,
      shortened,
      relabeled,
      specialCondition,
      burnedFlag,
      burnedValidLand,
      burnDoy,
      burnedUncertainty
    ])
    .toFloat()
    .setDefaultProjection(
      nativeProjection
    )
    .set({
      month: month,
      year: YEAR,
      'system:time_start':
        image.get('system:time_start')
    });
}


var preparedMonthly = yearlyCollection.map(
  prepareMonthlyImage
);


print(
  'Prepared month count, expected 12:',
  preparedMonthly.size()
);


// ============================================================
// 5. ANNUAL NATIVE-SCALE VARIABLES
// ============================================================

var landAny = preparedMonthly
  .select('land_flag')
  .max()
  .unmask(0)
  .toFloat()
  .rename(
    'land_area_frac_' +
    YEAR
  );


var validMonthCount = preparedMonthly
  .select('valid_land_flag')
  .sum()
  .toFloat();


var fullMappingMonthCount = preparedMonthly
  .select('full_mapping_flag')
  .sum()
  .toFloat();


var shortenedMonthCount = preparedMonthly
  .select('shortened_mapping_flag')
  .sum()
  .toFloat();


var relabeledMonthCount = preparedMonthly
  .select('relabeled_flag')
  .sum()
  .toFloat();


var specialConditionMonthCount = preparedMonthly
  .select('special_condition_flag')
  .sum()
  .toFloat();


var validMappingFractionMeanLand = validMonthCount
  .divide(12)
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'valid_mapping_month_fraction_mean_land_' +
    YEAR
  );


var fullMappingFractionMeanLand = fullMappingMonthCount
  .divide(12)
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'full_mapping_month_fraction_mean_land_' +
    YEAR
  );


var shortenedMappingFractionMeanLand = shortenedMonthCount
  .divide(12)
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'shortened_mapping_month_fraction_mean_land_' +
    YEAR
  );


var relabeledFractionMeanLand = relabeledMonthCount
  .divide(12)
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'relabeled_month_fraction_mean_land_' +
    YEAR
  );


var specialConditionFractionMeanLand =
  specialConditionMonthCount
    .divide(12)
    .updateMask(
      landAny.eq(1)
    )
    .rename(
      'special_condition_month_fraction_mean_land_' +
      YEAR
    );


var annualBurned = preparedMonthly
  .select('burned_flag')
  .max()
  .unmask(0)
  .toFloat();


var burnEventCount = preparedMonthly
  .select('burned_flag')
  .sum()
  .toFloat();


var annualBurnedAreaFrac = annualBurned
  .rename(
    'annual_burned_area_frac_' +
    YEAR
  );


var annualBurnedLandFrac = annualBurned
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'annual_burned_land_frac_' +
    YEAR
  );


var repeatedBurnLandFrac = burnEventCount
  .gte(2)
  .toFloat()
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'repeated_burn_land_frac_' +
    YEAR
  );


var burnEventCountMeanLand = burnEventCount
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'burn_event_count_mean_land_' +
    YEAR
  );


var firstBurnDoy = preparedMonthly
  .select('burn_doy')
  .min()
  .updateMask(
    annualBurned.eq(1)
  )
  .rename(
    'first_burn_doy_mean_' +
    YEAR
  );


var lastBurnDoy = preparedMonthly
  .select('burn_doy')
  .max()
  .updateMask(
    annualBurned.eq(1)
  )
  .rename(
    'last_burn_doy_mean_' +
    YEAR
  );


var fireSeasonSpan = lastBurnDoy
  .subtract(
    firstBurnDoy
  )
  .max(0)
  .updateMask(
    annualBurned.eq(1)
  )
  .rename(
    'fire_season_span_day_mean_' +
    YEAR
  );


var burnDoyMean = preparedMonthly
  .select('burn_doy')
  .mean()
  .updateMask(
    annualBurned.eq(1)
  )
  .rename(
    'burn_doy_mean_' +
    YEAR
  );


var burnUncertaintyMean = preparedMonthly
  .select('burn_uncertainty')
  .mean()
  .updateMask(
    annualBurned.eq(1)
  )
  .rename(
    'burn_uncertainty_day_mean_' +
    YEAR
  );


var validMonthCountMeanLand = validMonthCount
  .updateMask(
    landAny.eq(1)
  )
  .rename(
    'valid_month_count_mean_land_' +
    YEAR
  );


var fullMappingMonthCountMeanLand =
  fullMappingMonthCount
    .updateMask(
      landAny.eq(1)
    )
    .rename(
      'full_mapping_month_count_mean_land_' +
      YEAR
    );


// ============================================================
// 6. MONTHLY OUTPUT BANDS
// ============================================================

var monthlyBurnedLandBands = [];
var monthlyValidLandAreaBands = [];


for (
  var month = 1;
  month <= 12;
  month++
) {
  var monthlyImage = ee.Image(
    preparedMonthly
      .filter(
        ee.Filter.eq(
          'month',
          month
        )
      )
      .first()
  );


  var burnedLandFraction = monthlyImage
    .select(
      'burned_valid_land'
    )
    .rename(
      'burned_land_frac_m' +
      monthText(month) +
      '_' +
      YEAR
    )
    .toFloat();


  var validLandAreaFraction = monthlyImage
    .select(
      'valid_land_flag'
    )
    .unmask(0)
    .rename(
      'valid_land_area_frac_m' +
      monthText(month) +
      '_' +
      YEAR
    )
    .toFloat();


  monthlyBurnedLandBands.push(
    burnedLandFraction
  );

  monthlyValidLandAreaBands.push(
    validLandAreaFraction
  );
}


// ============================================================
// 7. BUILD THE 41-BAND NATIVE STACK
// ============================================================

var nativeStack = ee.Image.cat([
  landAny,

  validMappingFractionMeanLand,

  fullMappingFractionMeanLand,

  shortenedMappingFractionMeanLand,

  relabeledFractionMeanLand,

  specialConditionFractionMeanLand,

  annualBurnedAreaFrac,

  annualBurnedLandFrac,

  repeatedBurnLandFrac,

  burnEventCountMeanLand,

  firstBurnDoy,

  lastBurnDoy,

  fireSeasonSpan,

  burnDoyMean,

  burnUncertaintyMean,

  validMonthCountMeanLand,

  fullMappingMonthCountMeanLand,

  ee.Image.cat(
    monthlyBurnedLandBands
  ),

  ee.Image.cat(
    monthlyValidLandAreaBands
  )
])
  .toFloat()
  .setDefaultProjection(
    nativeProjection
  );


print(
  'Native stack band count, expected 41:',
  nativeStack.bandNames().size()
);

print(
  'Native stack bands:',
  nativeStack.bandNames()
);


// ============================================================
// 8. EXPORT ONE 30-DEGREE TILE
// ============================================================

function exportOneTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );

  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var nativeTileStack = nativeStack
    .clip(
      bufferedRegion
    )
    .setDefaultProjection(
      nativeProjection
    );


  var outputTileG005 = nativeTileStack
    .reduceResolution({
      reducer: ee.Reducer.mean(),

      bestEffort: false,

      maxPixels:
        CONFIG.maxPixelsReduce
    })
    .toFloat()
    .set({
      dataset: CONFIG.source,

      year: YEAR,

      tile_name: tile.name,

      target_grid: 'g005',

      target_crs: CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      burned_rule:
        'BurnDate > 0 AND land AND sufficient valid data',

      qa_bits:
        'land, valid data, shortened mapping, relabeled, special condition',

      processing:
        'native source clipped before one reduceResolution mean',

      version: CONFIG.version
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
    'MCD64A1_burned_area_g005_tile_' +
    tile.name +
    '_' +
    YEAR +
    '_' +
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
    image: outputTileG005
      .clip(
        exactRegion
      )
      .unmask(
        CONFIG.noData
      )
      .toFloat(),

    description: outputPrefix,

    folder: CONFIG.driveFolder,

    fileNamePrefix: outputPrefix,

    region: exactRegion,

    crs: CONFIG.targetCrs,

    dimensions: dimensionsText,

    maxPixels:
      CONFIG.maxPixelsExport,

    fileFormat: 'GeoTIFF',

    formatOptions: {
      cloudOptimized: true,
      noData: CONFIG.noData
    }
  });
}


// ============================================================
// 9. CREATE FORMAL YEAR TASKS
// ============================================================

EXPORT_TILES.forEach(function(tile) {
  exportOneTile(
    tile
  );
});


print('============================================================');
print('FORMAL TASK CREATION COMPLETED');
print(
  'Expected task count:',
  EXPORT_TILES.length
);
print('Year:', YEAR);
print(
  'Task range:',
  START_TILE_INDEX,
  END_TILE_INDEX
);
print(
  'Tasks created:',
  EXPORT_TILES.length
);
print('Full-year expected task count: 57');
print('Pure-ocean tasks created: 0');
print('Output resolution: 0.05 degree');
print('Output bands per tile: 41');
print('============================================================');


// ============================================================
// 10. NO LARGE MAP OR REDUCE-REGION DIAGNOSTICS
// ============================================================

// Deliberately omitted to avoid triggering extra computations.
