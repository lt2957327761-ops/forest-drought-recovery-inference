/**** GEE SCRIPT 01 FULL v07
 * Data 01: MOD13C1 16-day kNDVI and support-normalized QA fractions
 *
 * Project:
 *   Global forest resilience analysis on a fixed 0.5-degree grid.
 *
 * Formal analysis period:
 *   2001-2024
 *
 * Main purpose:
 *   Provide the vegetation-state time series and quality-support information
 *   required for:
 *   climatology -> anomaly -> long-term TAC -> annual TAC -> delta TAC.
 *
 * Main improvement over v06:
 *   v06 validFrac/goodFrac used the entire 0.5-degree cell as denominator.
 *   That caused coastal and island cells to mix ocean fraction with QA quality.
 *
 *   v07 separates:
 *     1. supportFrac:
 *        MOD13C1-supported area / entire 0.5-degree target-cell area
 *
 *     2. validFracSupport:
 *        good-or-marginal area / MOD13C1-supported area
 *
 *     3. goodFracSupport:
 *        good-only area / MOD13C1-supported area
 *
 * Annual output:
 *   23 kNDVI bands
 *   23 supportFrac bands
 *   23 validFracSupport bands
 *   23 goodFracSupport bands
 *   Total for a normal year: 92 bands
 *
 * Expected raster:
 *   CRS       = EPSG:4326
 *   Resolution = 0.5 degree
 *   Width      = 720
 *   Height     = 290
 *   Bounds     = [-180, -60, 180, 85]
 *   NoData     = -9999
 */


// ============================================================
// 0. MODE AND CONFIGURATION
// ============================================================

// Keep TEST_ONE_YEAR until the exported 2020 file passes local QC.
var MODE = 'FULL_2001_2024';

// After the 2020 test passes, change only this line to:
// var MODE = 'FULL_2001_2024';

var CONFIG = {
  source: 'MODIS/061/MOD13C1',

  startYear: 2001,
  endYear: 2024,
  testYear: 2020,

  resDeg: 0.5,
  crs: 'EPSG:4326',

  version: 'v07',
  noData: -9999,

  folderTest:
    'GlobalForestResilience_Data01_MOD13C1_g050_TEST_v07',

  folderProd:
    'GlobalForestResilience_Data01_MOD13C1_g050_2001_2024_v07',

  // Logical study extent:
  // longitude: -180 to 180
  // latitude :  -60 to 85
  //
  // Tiny contraction prevents an extra boundary row or column.
  region: ee.Geometry.Rectangle(
    [-180, -59.999999, 179.999999, 84.999999],
    null,
    false
  ),

  // Interior tropical QC region.
  qcRegionAmazon: ee.Geometry.Rectangle(
    [-70, -15, -50, 5],
    null,
    false
  ),

  // Mixed land/ocean QC region for checking coastal support.
  qcRegionCoastal: ee.Geometry.Rectangle(
    [105, -8, 110, -3],
    null,
    false
  ),

  maxPixels: 1e13
};

var TARGET_TRANSFORM = [
  CONFIG.resDeg, 0, -180,
  0, -CONFIG.resDeg, 90
];

var OUTPUT_FOLDER = MODE === 'TEST_ONE_YEAR'
  ? CONFIG.folderTest
  : CONFIG.folderProd;

print('============================================================');
print('Data 01 MOD13C1 kNDVI + support-normalized QA');
print('Script version:', CONFIG.version);
print('MODE:', MODE);
print('Source:', CONFIG.source);
print('Formal period:', CONFIG.startYear + '-' + CONFIG.endYear);
print('Output folder:', OUTPUT_FOLDER);
print('CRS:', CONFIG.crs);
print('Transform:', TARGET_TRANSFORM);
print('Expected raster:', '720 x 290');
print('Expected bounds:', '[-180, -60, 180, 85]');
print('Expected normal-year bands:', 92);
print('NoData:', CONFIG.noData);
print('============================================================');


// ============================================================
// 1. PREPARE ONE NATIVE MOD13C1 IMAGE
// ============================================================

function prepareNativeImage(img) {
  // MOD13C1 in Earth Engine is already in physical NDVI units.
  var ndvi = img.select('NDVI').toFloat();

  // Raw MOD13C1 support mask:
  // 1 where the NDVI band has product support;
  // 0 where it is outside supported land/product coverage.
  //
  // This mask is captured BEFORE QA and numerical range filtering.
  var supportMask = ndvi.mask().gt(0);

  // DetailedQA bits 0-1:
  // 0 = VI produced with good quality
  // 1 = VI produced, but check other QA information
  // 2 = pixel probably cloudy
  // 3 = pixel not produced for other reasons
  var detailedQA = img.select('DetailedQA');
  var modlandQA = detailedQA.bitwiseAnd(3);

  // Reject values outside the documented NDVI physical range.
  var rangeValid = ndvi.gte(-0.2).and(ndvi.lte(1.0));

  // Main-analysis quality:
  // good + marginal.
  var validMask = supportMask
    .and(modlandQA.lte(1))
    .and(rangeValid);

  // Strict sensitivity quality:
  // good only.
  var goodMask = supportMask
    .and(modlandQA.eq(0))
    .and(rangeValid);

  // kNDVI = tanh(NDVI^2)
  //
  // Only valid main-analysis cells contribute to the 0.5-degree
  // kNDVI mean.
  var kNDVI = ndvi
    .updateMask(validMask)
    .pow(2)
    .tanh()
    .rename('kNDVI')
    .toFloat();

  // Binary area-support bands.
  //
  // They are explicitly filled with zero before aggregation so their
  // 0.5-degree means represent area fractions of the entire target cell.
  var supportArea = supportMask
    .unmask(0)
    .rename('supportArea')
    .toFloat();

  var validArea = validMask
    .unmask(0)
    .rename('validArea')
    .toFloat();

  var goodArea = goodMask
    .unmask(0)
    .rename('goodArea')
    .toFloat();

  return kNDVI
    .addBands(supportArea)
    .addBands(validArea)
    .addBands(goodArea)
    .copyProperties(
      img,
      ['system:time_start', 'system:index']
    );
}


// ============================================================
// 2. AGGREGATE TO THE FIXED GLOBAL 0.5-DEGREE GRID
// ============================================================

function aggregateToG050(img) {
  // For kNDVI, the mean is calculated only from its valid masked cells.
  //
  // For supportArea, validArea and goodArea, means become fractions
  // of the full 0.5-degree target-cell area.
  var areaAggregates = img
    .reduceResolution({
      reducer: ee.Reducer.mean(),
      bestEffort: false,
      maxPixels: 1024
    })
    .reproject({
      crs: CONFIG.crs,
      crsTransform: TARGET_TRANSFORM
    });

  var kNDVI = areaAggregates
    .select('kNDVI')
    .rename('kNDVI');

  var supportFrac = areaAggregates
    .select('supportArea')
    .max(0)
    .min(1)
    .rename('supportFrac');

  var validAreaFrac = areaAggregates
    .select('validArea')
    .max(0)
    .min(1);

  var goodAreaFrac = areaAggregates
    .select('goodArea')
    .max(0)
    .min(1);

  // Normalize QA fractions by MOD13C1-supported area.
  //
  // Ocean/no-support cells remain masked.
  var supportPositive = supportFrac.gt(0);

  var validFracSupport = validAreaFrac
    .divide(supportFrac)
    .updateMask(supportPositive)
    .max(0)
    .min(1)
    .rename('validFracSupport');

  var goodFracSupport = goodAreaFrac
    .divide(supportFrac)
    .updateMask(supportPositive)
    .max(0)
    .min(1)
    .rename('goodFracSupport');

  // kNDVI must also be absent where support is zero.
  kNDVI = kNDVI.updateMask(supportPositive);

  return kNDVI
    .addBands(supportFrac)
    .addBands(validFracSupport)
    .addBands(goodFracSupport)
    .copyProperties(
      img,
      ['system:time_start', 'system:index']
    );
}


// ============================================================
// 3. STACK ONE VARIABLE THROUGH ALL 16-DAY DATES
// ============================================================

function stackOneBand(collection, sourceBand, outputPrefix) {
  var renamedCollection = collection.map(function(img) {
    var dateString = ee.Date(
      img.get('system:time_start')
    ).format('YYYYMMdd');

    var bandName = ee.String(outputPrefix)
      .cat('_')
      .cat(dateString);

    return img
      .select(sourceBand)
      .rename(bandName)
      .copyProperties(
        img,
        ['system:time_start', 'system:index']
      );
  });

  var cleanNames = renamedCollection
    .aggregate_array('system:time_start')
    .map(function(timeValue) {
      return ee.String(outputPrefix)
        .cat('_')
        .cat(
          ee.Date(timeValue).format('YYYYMMdd')
        );
    });

  var stack = ee.ImageCollection(renamedCollection)
    .toBands()
    .rename(cleanNames)
    .toFloat();

  return {
    image: stack,
    names: cleanNames
  };
}


// ============================================================
// 4. BUILD ONE COMPLETE ANNUAL PRODUCT
// ============================================================

function buildAnnualProduct(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');

  var rawCollection = ee.ImageCollection(CONFIG.source)
    .filterDate(start, end)
    .sort('system:time_start');

  var g050Collection = rawCollection
    .map(prepareNativeImage)
    .map(aggregateToG050)
    .sort('system:time_start');

  var kndviStack = stackOneBand(
    g050Collection,
    'kNDVI',
    'kNDVI'
  );

  var supportStack = stackOneBand(
    g050Collection,
    'supportFrac',
    'supportFrac'
  );

  var validStack = stackOneBand(
    g050Collection,
    'validFracSupport',
    'validFracSupport'
  );

  var goodStack = stackOneBand(
    g050Collection,
    'goodFracSupport',
    'goodFracSupport'
  );

  // Band-group order:
  // 1. all kNDVI dates
  // 2. all supportFrac dates
  // 3. all validFracSupport dates
  // 4. all goodFracSupport dates
  var combined = kndviStack.image
    .addBands(supportStack.image)
    .addBands(validStack.image)
    .addBands(goodStack.image)
    .set({
      dataset: CONFIG.source,
      product:
        'kNDVI_supportFrac_validFracSupport_goodFracSupport',
      year: year,
      resolution_degree: CONFIG.resDeg,
      main_QA:
        'DetailedQA_MODLAND_bits_0_1_le_1',
      strict_QA:
        'DetailedQA_MODLAND_bits_0_1_eq_0',
      support_definition:
        'raw_NDVI_band_mask_before_QA',
      noData: CONFIG.noData,
      version: CONFIG.version
    });

  return {
    rawCollection: rawCollection,
    g050Collection: g050Collection,
    combined: combined,
    kndviNames: kndviStack.names,
    supportNames: supportStack.names,
    validNames: validStack.names,
    goodNames: goodStack.names
  };
}


// ============================================================
// 5. EXPORT ONE YEAR
// ============================================================

function exportAnnualProduct(year) {
  var result = buildAnnualProduct(year);

  var prefixCore =
    'MOD13C1_kNDVI_supportQA_16day_g050_global_' +
    year +
    '_' +
    CONFIG.version;

  var prefix = MODE === 'TEST_ONE_YEAR'
    ? 'TEST_' + prefixCore
    : prefixCore;

  var exportImage = result.combined
    .unmask({
      value: CONFIG.noData,
      sameFootprint: false
    })
    .toFloat();

  print('------------------------------------------------------------');
  print('Preparing export:', prefix);
  print('Year:', year);
  print('Raw image count:', result.rawCollection.size());
  print(
    'kNDVI band count:',
    ee.List(result.kndviNames).length()
  );
  print(
    'supportFrac band count:',
    ee.List(result.supportNames).length()
  );
  print(
    'validFracSupport band count:',
    ee.List(result.validNames).length()
  );
  print(
    'goodFracSupport band count:',
    ee.List(result.goodNames).length()
  );
  print(
    'Total output bands:',
    exportImage.bandNames().length()
  );
  print('Output bands:', exportImage.bandNames());
  print('Folder:', OUTPUT_FOLDER);
  print('------------------------------------------------------------');

  Export.image.toDrive({
    image: exportImage,
    description: prefix,
    folder: OUTPUT_FOLDER,
    fileNamePrefix: prefix,
    region: CONFIG.region,
    crs: CONFIG.crs,
    crsTransform: TARGET_TRANSFORM,
    maxPixels: CONFIG.maxPixels,
    fileFormat: 'GeoTIFF',
    formatOptions: {
      cloudOptimized: true,
      noData: CONFIG.noData
    }
  });
}


// ============================================================
// 6. CONSOLE QC FOR THE TEST YEAR
// ============================================================

var previewYear = CONFIG.testYear;
var preview = buildAnnualProduct(previewYear);

print('============================================================');
print('PREVIEW QC YEAR:', previewYear);
print(
  'Raw MOD13C1 image count:',
  preview.rawCollection.size()
);
print(
  'Expected normal-year image count:',
  'approximately 23'
);

print(
  'First raw date:',
  ee.Date(
    ee.Image(
      preview.rawCollection.first()
    ).get('system:time_start')
  ).format('YYYY-MM-dd')
);

print(
  'Last raw date:',
  ee.Date(
    ee.Image(
      preview.rawCollection
        .sort('system:time_start', false)
        .first()
    ).get('system:time_start')
  ).format('YYYY-MM-dd')
);

print(
  'Combined output band count:',
  preview.combined.bandNames().length()
);

print(
  'Expected normal-year output band count:',
  92
);

print(
  'Combined band names:',
  preview.combined.bandNames()
);

print(
  'First-band projection:',
  preview.combined.select(0).projection()
);

print('============================================================');

var firstG050 = ee.Image(
  preview.g050Collection.first()
);


// ------------------------------------------------------------
// 6.1 Interior tropical-region statistics
// ------------------------------------------------------------

var amazonStats = firstG050.reduceRegion({
  reducer: ee.Reducer.minMax()
    .combine({
      reducer2: ee.Reducer.mean(),
      sharedInputs: true
    }),
  geometry: CONFIG.qcRegionAmazon,
  crs: CONFIG.crs,
  crsTransform: TARGET_TRANSFORM,
  maxPixels: 1e8,
  bestEffort: false
});

print(
  'First-date Amazon statistics:',
  amazonStats
);


// ------------------------------------------------------------
// 6.2 Mixed coastal-region statistics
// ------------------------------------------------------------

var coastalStats = firstG050.reduceRegion({
  reducer: ee.Reducer.minMax()
    .combine({
      reducer2: ee.Reducer.mean(),
      sharedInputs: true
    }),
  geometry: CONFIG.qcRegionCoastal,
  crs: CONFIG.crs,
  crsTransform: TARGET_TRANSFORM,
  maxPixels: 1e8,
  bestEffort: false
});

print(
  'First-date coastal statistics:',
  coastalStats
);


// ------------------------------------------------------------
// 6.3 Logical checks
// ------------------------------------------------------------

// goodFracSupport must never exceed validFracSupport.
var goodGreaterThanValid = firstG050
  .select('goodFracSupport')
  .gt(
    firstG050.select('validFracSupport')
  )
  .rename('violation_good_gt_valid');

var logicalCheck1 = goodGreaterThanValid.reduceRegion({
  reducer: ee.Reducer.max(),
  geometry: CONFIG.qcRegionAmazon,
  crs: CONFIG.crs,
  crsTransform: TARGET_TRANSFORM,
  maxPixels: 1e8,
  bestEffort: false
});

print(
  'Logical check 1: max(goodFracSupport > validFracSupport), expected 0:',
  logicalCheck1.get('violation_good_gt_valid')
);


// All normalized QA values must remain within [0,1].
var qaRangeViolation = firstG050
  .select([
    'validFracSupport',
    'goodFracSupport'
  ])
  .reduce(ee.Reducer.min())
  .lt(0)
  .or(
    firstG050
      .select([
        'validFracSupport',
        'goodFracSupport'
      ])
      .reduce(ee.Reducer.max())
      .gt(1)
  )
  .rename('violation_QA_range');

var logicalCheck2 = qaRangeViolation.reduceRegion({
  reducer: ee.Reducer.max(),
  geometry: CONFIG.qcRegionAmazon,
  crs: CONFIG.crs,
  crsTransform: TARGET_TRANSFORM,
  maxPixels: 1e8,
  bestEffort: false
});

print(
  'Logical check 2: QA fraction outside [0,1], expected 0:',
  logicalCheck2.get('violation_QA_range')
);


// supportFrac itself must remain in [0,1].
var supportRangeViolation = firstG050
  .select('supportFrac')
  .lt(0)
  .or(
    firstG050.select('supportFrac').gt(1)
  )
  .rename('violation_support_range');

var logicalCheck3 = supportRangeViolation.reduceRegion({
  reducer: ee.Reducer.max(),
  geometry: CONFIG.qcRegionCoastal,
  crs: CONFIG.crs,
  crsTransform: TARGET_TRANSFORM,
  maxPixels: 1e8,
  bestEffort: false
});

print(
  'Logical check 3: supportFrac outside [0,1], expected 0:',
  logicalCheck3.get('violation_support_range')
);


// ============================================================
// 7. MAP PREVIEW
// ============================================================

Map.setCenter(107.5, -5.5, 5);

Map.addLayer(
  firstG050.select('kNDVI'),
  {
    min: 0,
    max: 0.7,
    palette: [
      'ffffff',
      'f7e26b',
      '7cb342',
      '1b5e20'
    ]
  },
  'First-date kNDVI g050 ' + previewYear
);

Map.addLayer(
  firstG050.select('supportFrac'),
  {
    min: 0,
    max: 1,
    palette: [
      '000000',
      '9ecae1',
      'ffffff'
    ]
  },
  'First-date support fraction g050 ' + previewYear
);

Map.addLayer(
  firstG050.select('validFracSupport'),
  {
    min: 0,
    max: 1,
    palette: [
      '8b0000',
      'ffd54f',
      '1b5e20'
    ]
  },
  'First-date valid fraction within support ' + previewYear
);

Map.addLayer(
  firstG050.select('goodFracSupport'),
  {
    min: 0,
    max: 1,
    palette: [
      '8b0000',
      'ffd54f',
      '1b5e20'
    ]
  },
  'First-date good fraction within support ' + previewYear
);

Map.addLayer(
  CONFIG.qcRegionCoastal,
  {
    color: '00ffff'
  },
  'Coastal QC region',
  false
);


// ============================================================
// 8. CREATE EXPORT TASKS
// ============================================================

if (MODE === 'TEST_ONE_YEAR') {
  exportAnnualProduct(CONFIG.testYear);
}

if (MODE === 'FULL_2001_2024') {
  for (
    var year = CONFIG.startYear;
    year <= CONFIG.endYear;
    year++
  ) {
    exportAnnualProduct(year);
  }
}
