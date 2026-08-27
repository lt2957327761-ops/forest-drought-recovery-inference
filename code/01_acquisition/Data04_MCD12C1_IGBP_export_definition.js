/**** DATA 04 FORMAL EXPORT — MCD12C1 IGBP 2001–2024
 *
 * Dataset:
 *   MODIS/061/MCD12C1
 *
 * Output:
 *   24 annual global GeoTIFF files
 *
 * Years:
 *   2001–2024
 *
 * Grid:
 *   CRS        : EPSG:4326
 *   Resolution : 0.05 degree
 *   Bounds     : [-180, -60, 180, 85]
 *   Width      : 7200
 *   Height     : 2900
 *
 * Bands per year:
 *   1. IGBP majority class
 *   2. Majority confidence / assessment
 *   3–19. IGBP percentage classes 0–16
 *
 * Data type:
 *   uint8
 *
 * NoData:
 *   255
 *
 * IMPORTANT:
 * - This is the formal version of the 2020 test that passed QC.
 * - No spatial aggregation is performed in GEE.
 * - The complete native 0.05° IGBP information is retained.
 * - The later 0.5° products will be generated locally with Python.
 * - Running this script creates exactly 24 export tasks.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  source: 'MODIS/061/MCD12C1',

  startYear: 2001,
  endYear: 2024,

  crs: 'EPSG:4326',

  crsTransform: [
    0.05, 0, -180,
    0, -0.05, 85
  ],

  noData: 255,

  maxPixels: 1e13,

  version: 'v01',

  driveFolder:
    'GlobalForestResilience_Data04_MCD12C1_' +
    'IGBP_g005_global_2001_2024_v01'
};


// Build a normal JavaScript year array.
// This allows Export.image.toDrive to create one task per year.

var YEARS = [];

for (
  var year = CONFIG.startYear;
  year <= CONFIG.endYear;
  year++
) {
  YEARS.push(year);
}


// ============================================================
// 1. EXACT GLOBAL EXPORT REGION
// ============================================================

// A tiny inward offset avoids ambiguity at the exact global edges.
// The raster grid itself remains fixed by crsTransform.

var EPS = 1e-6;

var GLOBAL_REGION_EXPORT = ee.Geometry.Rectangle(
  [
    -180 + EPS,
    -60 + EPS,
     180 - EPS,
      85 - EPS
  ],
  null,
  false
);


// ============================================================
// 2. SOURCE BAND LIST
// ============================================================

var SOURCE_BANDS = [
  'Majority_Land_Cover_Type_1',
  'Majority_Land_Cover_Type_1_Assessment',

  'Land_Cover_Type_1_Percent_Class_0',
  'Land_Cover_Type_1_Percent_Class_1',
  'Land_Cover_Type_1_Percent_Class_2',
  'Land_Cover_Type_1_Percent_Class_3',
  'Land_Cover_Type_1_Percent_Class_4',
  'Land_Cover_Type_1_Percent_Class_5',
  'Land_Cover_Type_1_Percent_Class_6',
  'Land_Cover_Type_1_Percent_Class_7',
  'Land_Cover_Type_1_Percent_Class_8',
  'Land_Cover_Type_1_Percent_Class_9',
  'Land_Cover_Type_1_Percent_Class_10',
  'Land_Cover_Type_1_Percent_Class_11',
  'Land_Cover_Type_1_Percent_Class_12',
  'Land_Cover_Type_1_Percent_Class_13',
  'Land_Cover_Type_1_Percent_Class_14',
  'Land_Cover_Type_1_Percent_Class_15',
  'Land_Cover_Type_1_Percent_Class_16'
];


// ============================================================
// 3. OUTPUT BAND NAMES
// ============================================================

function getOutputBandNames(year) {
  return [
    'igbp_majority_' + year,
    'igbp_confidence_pct_' + year,

    'igbp_pct_c00_water_' + year,
    'igbp_pct_c01_evergreen_needleleaf_forest_' + year,
    'igbp_pct_c02_evergreen_broadleaf_forest_' + year,
    'igbp_pct_c03_deciduous_needleleaf_forest_' + year,
    'igbp_pct_c04_deciduous_broadleaf_forest_' + year,
    'igbp_pct_c05_mixed_forest_' + year,
    'igbp_pct_c06_closed_shrubland_' + year,
    'igbp_pct_c07_open_shrubland_' + year,
    'igbp_pct_c08_woody_savanna_' + year,
    'igbp_pct_c09_savanna_' + year,
    'igbp_pct_c10_grassland_' + year,
    'igbp_pct_c11_permanent_wetland_' + year,
    'igbp_pct_c12_cropland_' + year,
    'igbp_pct_c13_urban_' + year,
    'igbp_pct_c14_crop_natural_mosaic_' + year,
    'igbp_pct_c15_snow_ice_' + year,
    'igbp_pct_c16_barren_' + year
  ];
}


// ============================================================
// 4. LOAD AND FORMAT ONE YEAR
// ============================================================

function buildYearImage(year) {
  var start = ee.Date.fromYMD(
    year,
    1,
    1
  );

  var end = start.advance(
    1,
    'year'
  );

  var yearlyCollection = ee.ImageCollection(
      CONFIG.source
    )
    .filterDate(start, end)
    .sort('system:time_start');

  print(
    'Year ' + year +
    ' source image count, expected 1:',
    yearlyCollection.size()
  );

  var sourceImage = ee.Image(
    yearlyCollection.first()
  );

  var outputImage = sourceImage
    .select(
      SOURCE_BANDS,
      getOutputBandNames(year)
    )
    .clip(
      GLOBAL_REGION_EXPORT
    )
    .unmask(
      CONFIG.noData
    )
    .toUint8()
    .set({
      dataset: CONFIG.source,
      year: year,

      grid_name: 'g005',
      crs: CONFIG.crs,

      resolution_degree: 0.05,

      lon_min: -180,
      lon_max: 180,
      lat_min: -60,
      lat_max: 85,

      width: 7200,
      height: 2900,

      band_count: 19,
      no_data: CONFIG.noData,

      version: CONFIG.version,

      processing:
        'Native 0.05-degree MCD12C1 IGBP information retained; ' +
        'no spatial aggregation performed in GEE'
    });

  return outputImage;
}


// ============================================================
// 5. CREATE 24 EXPORT TASKS
// ============================================================

print('============================================================');
print('DATA 04 MCD12C1 FORMAL EXPORT');
print('Years:', YEARS);
print('Expected task count:', YEARS.length);
print('Drive folder:', CONFIG.driveFolder);
print('Grid: EPSG:4326, 0.05 degree, 7200 x 2900');
print('Bands per file: 19');
print('============================================================');


YEARS.forEach(function(year) {
  var outputImage = buildYearImage(year);

  var outputPrefix =
    'MCD12C1_IGBP_g005_global_' +
    year +
    '_' +
    CONFIG.version;

  print('------------------------------------------------------------');
  print('Preparing year:', year);
  print('Expected filename:', outputPrefix + '.tif');
  print('Output bands:', outputImage.bandNames());
  print('------------------------------------------------------------');

  Export.image.toDrive({
    image: outputImage,

    description: outputPrefix,

    folder: CONFIG.driveFolder,

    fileNamePrefix: outputPrefix,

    region: GLOBAL_REGION_EXPORT,

    crs: CONFIG.crs,

    crsTransform: CONFIG.crsTransform,

    maxPixels: CONFIG.maxPixels,

    fileFormat: 'GeoTIFF',

    formatOptions: {
      cloudOptimized: true,
      noData: CONFIG.noData
    }
  });
});


print('============================================================');
print('Task creation completed.');
print('Expected task count:', YEARS.length);
print('Expected years: 2001–2024');
print('============================================================');


// ============================================================
// 6. LIGHTWEIGHT REFERENCE-YEAR DIAGNOSTICS
// ============================================================

// Only use 2020 for lightweight visual and console checks.
// These checks do not affect any export.

var referenceYear = 2020;

var referenceImage = buildYearImage(
  referenceYear
);

var referenceMajority = referenceImage
  .select(
    'igbp_majority_' +
    referenceYear
  );

var referenceForestPct = referenceImage
  .select([
    'igbp_pct_c01_evergreen_needleleaf_forest_' +
      referenceYear,

    'igbp_pct_c02_evergreen_broadleaf_forest_' +
      referenceYear,

    'igbp_pct_c03_deciduous_needleleaf_forest_' +
      referenceYear,

    'igbp_pct_c04_deciduous_broadleaf_forest_' +
      referenceYear,

    'igbp_pct_c05_mixed_forest_' +
      referenceYear
  ])
  .reduce(
    ee.Reducer.sum()
  )
  .rename(
    'strict_forest_pct_' +
    referenceYear
  );


var referenceClassSum = referenceImage
  .select(
    'igbp_pct_c.*_' +
    referenceYear
  )
  .reduce(
    ee.Reducer.sum()
  )
  .rename(
    'igbp_class_sum_' +
    referenceYear
  );


print(
  'Reference 2020 class-percentage sum diagnostics:',
  referenceClassSum.reduceRegion({
    reducer:
      ee.Reducer.min()
      .combine({
        reducer2: ee.Reducer.max(),
        sharedInputs: true
      })
      .combine({
        reducer2: ee.Reducer.mean(),
        sharedInputs: true
      }),

    geometry: GLOBAL_REGION_EXPORT,

    scale: 50000,

    maxPixels: 1e8,

    bestEffort: true
  })
);


Map.setCenter(
  0,
  20,
  2
);

Map.addLayer(
  referenceMajority,
  {
    min: 0,
    max: 16
  },
  'MCD12C1 IGBP majority 2020',
  false
);

Map.addLayer(
  referenceForestPct,
  {
    min: 0,
    max: 100
  },
  'Strict forest percentage 2020',
  false
);
