// ============================================================================
// Data 15 FORMAL v02
// ERA5-Land dynamic soil moisture, 2001–2024
// ALL YEARS IN ONE GEE SCRIPT
//
// Running this script once creates 24 Export tasks:
//   one task for each year from 2001 through 2024.
//
// Each year is written to a separate Google Drive folder:
//   GlobalForestResilience_Data15_ERA5Land_SoilMoisture_g005_2001_v02
//   ...
//   GlobalForestResilience_Data15_ERA5Land_SoilMoisture_g005_2024_v02
//
// Each annual task is expected to generate 8 spatial GeoTIFF parts because:
//   complete grid = 7200 × 2900
//   fileDimensions = 2048
//
// Source:
//   ECMWF/ERA5_LAND/DAILY_AGGR
//
// Native soil layers:
//   Layer 1:   0–7 cm
//   Layer 2:   7–28 cm
//   Layer 3:  28–100 cm
//   Layer 4: 100–289 cm
//
// Output:
//   Extent: longitude [-180,180], latitude [-60,85]
//   CRS: EPSG:4326
//   Grid: 0.05°
//   Complete annual size: 7200 × 2900
//   Bands/year: 12 months × 8 variables = 96
//   dtype: float32
//   NoData: -9999
//
// Monthly variables:
//   1. swvl1_mean_mXX_m3m3
//   2. swvl2_mean_mXX_m3m3
//   3. swvl3_mean_mXX_m3m3
//   4. swvl4_mean_mXX_m3m3
//   5. rootzone_0_100_mean_mXX_m3m3
//   6. profile_0_289_mean_mXX_m3m3
//   7. rootzone_0_100_p10_mXX_m3m3
//   8. temporal_valid_mXX_frac
//
// Scientific note:
//   ERA5-Land native information is about 11.1 km. The 0.05° export is an
//   alignment/storage grid and does not create independent 0.05° climate data.
//
// This formal script follows the 2020 global test that passed structural,
// band-order, numerical-range and weighted-formula checks.
// ============================================================================


// ---------------------------- 0. Settings -----------------------------------

var YEARS = [
  2001, 2002, 2003, 2004, 2005, 2006,
  2007, 2008, 2009, 2010, 2011, 2012,
  2013, 2014, 2015, 2016, 2017, 2018,
  2019, 2020, 2021, 2022, 2023, 2024
];

var SOURCE_ID = 'ECMWF/ERA5_LAND/DAILY_AGGR';

var VERSION = 'v02';

var NODATA = -9999;

var OUTPUT_CRS = 'EPSG:4326';
var OUTPUT_TRANSFORM = [0.05, 0, -180, 0, -0.05, 85];

var EPS = 1e-6;

var GLOBAL_REGION = ee.Geometry.Rectangle(
    [-180 + EPS, -60 + EPS, 180 - EPS, 85 - EPS],
    null,
    false
);

var SOURCE_BANDS = [
  'volumetric_soil_water_layer_1',
  'volumetric_soil_water_layer_2',
  'volumetric_soil_water_layer_3',
  'volumetric_soil_water_layer_4'
];

var MONTHS = ee.List.sequence(1, 12);


// ---------------------- 1. Build one annual image ---------------------------

function buildAnnualImage(year) {
  var startDate = ee.Date.fromYMD(year, 1, 1);
  var endDate = startDate.advance(1, 'year');

  var source = ee.ImageCollection(SOURCE_ID)
      .filterDate(startDate, endDate)
      .select(SOURCE_BANDS);

  var firstSource = ee.Image(source.first());

  var nativeProjection = firstSource
      .select('volumetric_soil_water_layer_1')
      .projection();

  // Daily thickness-weighted variables.
  function buildDailySoilMoisture(image) {
    image = ee.Image(image);

    var layer1 = image
        .select('volumetric_soil_water_layer_1')
        .rename('swvl1_m3m3')
        .toFloat();

    var layer2 = image
        .select('volumetric_soil_water_layer_2')
        .rename('swvl2_m3m3')
        .toFloat();

    var layer3 = image
        .select('volumetric_soil_water_layer_3')
        .rename('swvl3_m3m3')
        .toFloat();

    var layer4 = image
        .select('volumetric_soil_water_layer_4')
        .rename('swvl4_m3m3')
        .toFloat();

    // 0–100 cm:
    // 7 cm + 21 cm + 72 cm = 100 cm.
    var rootzone = layer1.multiply(0.07)
        .add(layer2.multiply(0.21))
        .add(layer3.multiply(0.72))
        .rename('rootzone_0_100_m3m3')
        .toFloat();

    // 0–289 cm:
    // 7 cm + 21 cm + 72 cm + 189 cm = 289 cm.
    var profile = layer1.multiply(0.07)
        .add(layer2.multiply(0.21))
        .add(layer3.multiply(0.72))
        .add(layer4.multiply(1.89))
        .divide(2.89)
        .rename('profile_0_289_m3m3')
        .toFloat();

    return layer1
        .addBands(layer2)
        .addBands(layer3)
        .addBands(layer4)
        .addBands(rootzone)
        .addBands(profile)
        .setDefaultProjection(nativeProjection)
        .copyProperties(image, ['system:time_start']);
  }

  var dailySoil = source.map(buildDailySoilMoisture);

  function monthlyMean(collection, bandName, outputName) {
    return collection
        .select(bandName)
        .mean()
        .rename(outputName);
  }

  function buildMonthlySummary(monthNumber) {
    monthNumber = ee.Number(monthNumber);

    var monthStart = ee.Date.fromYMD(year, monthNumber, 1);
    var monthEnd = monthStart.advance(1, 'month');
    var expectedMonthDays = monthEnd.difference(monthStart, 'day');

    var monthlyDaily = dailySoil.filterDate(monthStart, monthEnd);

    var monthText = monthNumber.format('%02d');

    var swvl1Mean = monthlyMean(
        monthlyDaily,
        'swvl1_m3m3',
        ee.String('swvl1_mean_m').cat(monthText).cat('_m3m3')
    );

    var swvl2Mean = monthlyMean(
        monthlyDaily,
        'swvl2_m3m3',
        ee.String('swvl2_mean_m').cat(monthText).cat('_m3m3')
    );

    var swvl3Mean = monthlyMean(
        monthlyDaily,
        'swvl3_m3m3',
        ee.String('swvl3_mean_m').cat(monthText).cat('_m3m3')
    );

    var swvl4Mean = monthlyMean(
        monthlyDaily,
        'swvl4_m3m3',
        ee.String('swvl4_mean_m').cat(monthText).cat('_m3m3')
    );

    var rootzoneMean = monthlyMean(
        monthlyDaily,
        'rootzone_0_100_m3m3',
        ee.String('rootzone_0_100_mean_m').cat(monthText).cat('_m3m3')
    );

    var profileMean = monthlyMean(
        monthlyDaily,
        'profile_0_289_m3m3',
        ee.String('profile_0_289_mean_m').cat(monthText).cat('_m3m3')
    );

    var rootzoneP10 = monthlyDaily
        .select('rootzone_0_100_m3m3')
        .reduce(ee.Reducer.percentile([10]))
        .rename(
          ee.String('rootzone_0_100_p10_m')
              .cat(monthText)
              .cat('_m3m3')
        );

    var temporalValid = monthlyDaily
        .select('rootzone_0_100_m3m3')
        .count()
        .divide(expectedMonthDays)
        .clamp(0, 1)
        .rename(
          ee.String('temporal_valid_m')
              .cat(monthText)
              .cat('_frac')
        );

    return swvl1Mean
        .addBands(swvl2Mean)
        .addBands(swvl3Mean)
        .addBands(swvl4Mean)
        .addBands(rootzoneMean)
        .addBands(profileMean)
        .addBands(rootzoneP10)
        .addBands(temporalValid)
        .toFloat()
        .setDefaultProjection(nativeProjection)
        .set({
          'year': year,
          'month': monthNumber,
          'expected_days': expectedMonthDays,
          'actual_source_images': monthlyDaily.size(),
          'system:index': monthText
        });
  }

  var monthlyImages = MONTHS.map(buildMonthlySummary);

  var januaryImage = ee.Image(monthlyImages.get(0));

  var annualStack = ee.Image(
      ee.List(monthlyImages)
          .slice(1)
          .iterate(
            function(currentImage, accumulatedImage) {
              return ee.Image(accumulatedImage)
                  .addBands(ee.Image(currentImage));
            },
            januaryImage
          )
  ).toFloat().set({
    'dataset': 'Data15 ERA5-Land dynamic soil moisture',
    'year': year,
    'version': VERSION,
    'status': 'FORMAL',
    'source': SOURCE_ID,
    'source_image_count': source.size(),
    'expected_calendar_days': endDate.difference(startDate, 'day'),
    'output_crs': OUTPUT_CRS,
    'output_resolution_degree': 0.05,
    'output_width': 7200,
    'output_height': 2900,
    'band_count': 96
  });

  return annualStack;
}


// ----------------------- 2. Create all 24 export tasks -----------------------

print('Years to export', YEARS);
print('Expected number of export tasks', YEARS.length);

YEARS.forEach(function(year) {
  var annualImage = buildAnnualImage(year);

  var yearText = String(year);

  var driveFolder =
      'GlobalForestResilience_Data15_ERA5Land_SoilMoisture_g005_' +
      yearText + '_' + VERSION;

  var filePrefix =
      'Data15_ERA5Land_dynamicSoilMoisture_g005_global_' +
      yearText + '_96band_' + VERSION;

  print(
      'Prepared year ' + yearText +
      ' | expected days: ' +
      ((year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0))
        ? 366 : 365)
  );

  Export.image.toDrive({
    image: annualImage.unmask(NODATA, false),
    description: filePrefix,
    folder: driveFolder,
    fileNamePrefix: filePrefix,
    region: GLOBAL_REGION,
    crs: OUTPUT_CRS,
    crsTransform: OUTPUT_TRANSFORM,
    maxPixels: 3e9,
    shardSize: 256,
    fileDimensions: 2048,
    skipEmptyTiles: false,
    fileFormat: 'GeoTIFF',
    formatOptions: {
      cloudOptimized: true,
      noData: NODATA
    }
  });
});


// ---------------------------- 3. Optional preview ----------------------------

// Only 2020 is shown on the map. This does not create another export task.

var preview2020 = buildAnnualImage(2020);

var annualRootzoneMean2020 = preview2020
    .select('rootzone_0_100_mean_m.*_m3m3')
    .reduce(ee.Reducer.mean())
    .rename('annual_rootzone_0_100_mean_m3m3');

Map.setOptions('SATELLITE');
Map.setCenter(15, 15, 2);

Map.addLayer(
    annualRootzoneMean2020,
    {
      min: 0.05,
      max: 0.45,
      palette: [
        '8c510a', 'd8b365', 'f6e8c3',
        'c7eae5', '5ab4ac', '01665e'
      ]
    },
    'Data15 preview: 2020 root-zone soil moisture',
    false
);


// ============================================================================
// After clicking RUN:
//
//   Tasks panel should show 24 tasks.
//   Each task corresponds to one year.
//   Each year has its own Google Drive folder.
//   Each completed task should normally produce 8 TIF parts.
//
// Expected leap years with 366 daily images:
//   2004, 2008, 2012, 2016, 2020, 2024
//
// All other years should have 365 daily images.
//
// Recommended operation:
//   Do not start all 24 large exports simultaneously on one account.
//   Start 1–3 annual tasks at a time and record:
//     READY → RUNNING → COMPLETED → DOWNLOADED → QC_PASS
// ============================================================================
