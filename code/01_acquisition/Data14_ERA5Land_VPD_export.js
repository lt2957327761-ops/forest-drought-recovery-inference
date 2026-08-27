// ============================================================================
// Data 14 FORMAL v04
// ERA5-Land daily-derived VPD, 2001–2024
// ALL YEARS IN ONE GEE SCRIPT
//
// Run this script once in the Earth Engine Code Editor.
// It creates 24 Export tasks:
//   2001–2024, one task per year.
//
// Each year is exported to a separate Google Drive folder:
//   GlobalForestResilience_Data14_ERA5Land_VPD_g005_2001_v04
//   ...
//   GlobalForestResilience_Data14_ERA5Land_VPD_g005_2024_v04
//
// Each annual task is expected to generate 8 GeoTIFF spatial parts:
//   complete global grid = 7200 × 2900
//   fileDimensions = 2048
//
// Source:
//   ECMWF/ERA5_LAND/DAILY_AGGR
//
// VPD definition:
//   Daily-mean VPD is calculated from daily-mean 2 m air temperature and
//   daily-mean 2 m dew-point temperature.
//
// Output grid:
//   Extent: longitude [-180,180], latitude [-60,85]
//   CRS: EPSG:4326
//   Resolution: 0.05°
//   Complete annual size: 7200 × 2900
//   dtype: float32
//   NoData: -9999
//
// Monthly output variables:
//   1. vpd_mean_mXX_kPa
//   2. vpd_p90_mXX_kPa
//   3. vpd_max_mXX_kPa
//   4. vpd_std_mXX_kPa
//   5. temporal_valid_mXX_frac
//
// Bands/year:
//   12 months × 5 variables = 60 bands
//
// Scientific note:
//   ERA5-Land native information is about 11.1 km. The 0.05° export is only
//   an alignment/storage grid and does not create new independent 0.05°
//   climate information.
//
// This formal script follows the tested 2020 global configuration.
// ============================================================================


// ---------------------------- 0. Settings -----------------------------------

var YEARS = [
  2001, 2002, 2003, 2004, 2005, 2006,
  2007, 2008, 2009, 2010, 2011, 2012,
  2013, 2014, 2015, 2016, 2017, 2018,
  2019, 2020, 2021, 2022, 2023, 2024
];

var SOURCE_ID = 'ECMWF/ERA5_LAND/DAILY_AGGR';

var VERSION = 'v04';

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
  'temperature_2m',
  'dewpoint_temperature_2m'
];

var MONTHS = ee.List.sequence(1, 12);


// ------------------------- 1. VPD helper function ---------------------------

// Saturation vapour pressure in kPa:
//   e(T) = 0.6108 * exp[17.27*T / (T + 237.3)]
// Temperature must be in degrees Celsius.

function vapourPressureKPa(tempC) {
  return ee.Image(0.6108).multiply(
      tempC.multiply(17.27)
          .divide(tempC.add(237.3))
          .exp()
  );
}


// ----------------------- 2. Build one annual image --------------------------

function buildAnnualVPD(year) {
  var startDate = ee.Date.fromYMD(year, 1, 1);
  var endDate = startDate.advance(1, 'year');

  var source = ee.ImageCollection(SOURCE_ID)
      .filterDate(startDate, endDate)
      .select(SOURCE_BANDS);

  var firstSource = ee.Image(source.first());

  var nativeProjection = firstSource
      .select('temperature_2m')
      .projection();

  function calculateDailyMeanVPD(image) {
    image = ee.Image(image);

    var temperatureC = image
        .select('temperature_2m')
        .subtract(273.15);

    var dewpointC = image
        .select('dewpoint_temperature_2m')
        .subtract(273.15);

    var saturationVP = vapourPressureKPa(temperatureC);
    var actualVP = vapourPressureKPa(dewpointC);

    var vpd = saturationVP
        .subtract(actualVP)
        .max(0)
        .rename('vpd_dailymean_kPa')
        .toFloat()
        .setDefaultProjection(nativeProjection);

    return vpd.copyProperties(image, ['system:time_start']);
  }

  var dailyVPD = source.map(calculateDailyMeanVPD);

  function buildMonthlySummary(monthNumber) {
    monthNumber = ee.Number(monthNumber);

    var monthStart = ee.Date.fromYMD(year, monthNumber, 1);
    var monthEnd = monthStart.advance(1, 'month');

    var expectedMonthDays = monthEnd.difference(monthStart, 'day');

    var monthlyDailyVPD = dailyVPD.filterDate(monthStart, monthEnd);

    var vpdMean = monthlyDailyVPD
        .mean()
        .rename('vpd_mean');

    var vpdP90 = monthlyDailyVPD
        .reduce(ee.Reducer.percentile([90]))
        .rename('vpd_p90');

    var vpdMax = monthlyDailyVPD
        .max()
        .rename('vpd_max');

    var vpdStd = monthlyDailyVPD
        .reduce(ee.Reducer.stdDev())
        .rename('vpd_std');

    var temporalValid = monthlyDailyVPD
        .count()
        .divide(expectedMonthDays)
        .clamp(0, 1)
        .rename('temporal_valid');

    var monthText = monthNumber.format('%02d');

    var outputNames = ee.List([
      ee.String('vpd_mean_m').cat(monthText).cat('_kPa'),
      ee.String('vpd_p90_m').cat(monthText).cat('_kPa'),
      ee.String('vpd_max_m').cat(monthText).cat('_kPa'),
      ee.String('vpd_std_m').cat(monthText).cat('_kPa'),
      ee.String('temporal_valid_m').cat(monthText).cat('_frac')
    ]);

    return vpdMean
        .addBands(vpdP90)
        .addBands(vpdMax)
        .addBands(vpdStd)
        .addBands(temporalValid)
        .rename(outputNames)
        .toFloat()
        .setDefaultProjection(nativeProjection)
        .set({
          'year': year,
          'month': monthNumber,
          'expected_days': expectedMonthDays,
          'actual_source_images': monthlyDailyVPD.size(),
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
    'dataset': 'Data14 ERA5-Land daily-derived VPD',
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
    'band_count': 60
  });

  return annualStack;
}


// ----------------------- 3. Create all 24 export tasks -----------------------

print('Years to export', YEARS);
print('Expected number of export tasks', YEARS.length);

YEARS.forEach(function(year) {
  var annualImage = buildAnnualVPD(year);

  var yearText = String(year);

  var driveFolder =
      'GlobalForestResilience_Data14_ERA5Land_VPD_g005_' +
      yearText + '_' + VERSION;

  var filePrefix =
      'Data14_ERA5Land_dailyMeanVPD_g005_global_' +
      yearText + '_60band_' + VERSION;

  var expectedDays =
      (year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0))
      ? 366 : 365;

  print(
      'Prepared year ' + yearText +
      ' | expected days: ' + expectedDays +
      ' | expected bands: 60'
  );

  Export.image.toDrive({
    image: annualImage.unmask(NODATA, false),
    description: filePrefix,
    folder: driveFolder,
    fileNamePrefix: filePrefix,
    region: GLOBAL_REGION,
    crs: OUTPUT_CRS,
    crsTransform: OUTPUT_TRANSFORM,
    maxPixels: 2e9,
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


// ---------------------------- 4. Optional preview ----------------------------

// Only 2020 is displayed on the map.
// This does not create an additional Export task.

var preview2020 = buildAnnualVPD(2020);

var annualMeanVPD2020 = preview2020
    .select('vpd_mean_m.*_kPa')
    .reduce(ee.Reducer.mean())
    .rename('annual_mean_dailymean_vpd_kPa');

Map.setOptions('SATELLITE');
Map.setCenter(15, 15, 2);

Map.addLayer(
    annualMeanVPD2020,
    {
      min: 0,
      max: 3.5,
      palette: [
        '313695', '4575b4', '74add1', 'abd9e9',
        'e0f3f8', 'ffffbf', 'fee090', 'fdae61',
        'f46d43', 'd73027', 'a50026'
      ]
    },
    'Data14 preview: 2020 annual mean VPD',
    false
);


// ============================================================================
// After clicking RUN:
//
//   Tasks panel should contain 24 annual tasks.
//   Each task exports one year to its own Google Drive folder.
//   Each completed annual task should normally produce 8 TIF parts.
//
// Leap years expected to contain 366 daily images:
//   2004, 2008, 2012, 2016, 2020, 2024
//
// Other years should contain 365 daily images.
//
// Suggested operating procedure:
//   Start 1–3 large annual tasks at a time on each account and record:
//   READY → RUNNING → COMPLETED → DOWNLOADED → QC_PASS
//
// Clicking RUN creates the tasks but does not automatically start all Tasks.
// ============================================================================
