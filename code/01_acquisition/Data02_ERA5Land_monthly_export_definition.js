/**** GEE SCRIPT 02A FULL 2001-2024 v03
 * Data 02A: ERA5-Land monthly core climate variables
 *
 * FORMAL FULL EXPORT:
 *   2001-2024
 *
 * Dataset:
 *   ECMWF/ERA5_LAND/MONTHLY_AGGR
 *
 * Exported variables per month:
 *   1. tempC
 *   2. precip_mm_raw
 *   3. aet_mm_raw
 *   4. waterBalance_mm_raw = precip_mm_raw - aet_mm_raw
 *   5. srad_Wm2
 *
 * Expected output per year:
 *   12 months × 5 variables = 60 bands
 *
 * Total export tasks:
 *   24 years × 1 file/year = 24 tasks
 *
 * v03 rules confirmed by the 2020 single-year test:
 *   - Common source-support mask for all five variables.
 *   - Correct fixed 0.5-degree global grid.
 *   - Explicit NoData = -9999.
 *   - No clipping of precipitation, AET or radiation.
 *   - Actual evapotranspiration:
 *       aet_mm_raw = -1000 * total_evaporation_sum
 *   - Climatic water balance:
 *       waterBalance_mm_raw = precip_mm_raw - aet_mm_raw
 *
 * Grid:
 *   CRS        = EPSG:4326
 *   Resolution = 0.5 degree
 *   Width      = 720
 *   Height     = 290
 *   Bounds     = [-180, -60, 180, 85]
 *   Transform  = [0.5, 0, -180, 0, -0.5, 85]
 *   NoData     = -9999
 */


// ============================================================
// 0. CONFIG
// ============================================================

var CONFIG = {
  source: 'ECMWF/ERA5_LAND/MONTHLY_AGGR',

  startYear: 2001,
  endYear: 2024,

  resDeg: 0.5,
  crs: 'EPSG:4326',

  version: 'v03',
  noData: -9999,
  maxPixels: 1e13,

  outputFolder:
    'GlobalForestResilience_Data02A_ERA5Land_coreClimate_g050_2001_2024_v03',

  // Tiny contraction prevents an extra boundary row or column.
  region: ee.Geometry.Rectangle(
    [-180, -59.999999, 179.999999, 84.999999],
    null,
    false
  )
};

var TARGET_TRANSFORM = [
  CONFIG.resDeg, 0, -180,
  0, -CONFIG.resDeg, 85
];

print('============================================================');
print('Data 02A ERA5-Land core climate FULL EXPORT');
print('Version:', CONFIG.version);
print('Source:', CONFIG.source);
print('Period:', CONFIG.startYear + '-' + CONFIG.endYear);
print('Output folder:', CONFIG.outputFolder);
print('CRS:', CONFIG.crs);
print('Transform:', TARGET_TRANSFORM);
print('Expected raster:', '720 x 290');
print('Expected bounds:', '[-180, -60, 180, 85]');
print('Expected months per year:', 12);
print('Expected bands per year:', 60);
print(
  'Expected number of export tasks:',
  CONFIG.endYear - CONFIG.startYear + 1
);
print('NoData:', CONFIG.noData);
print('============================================================');


// ============================================================
// 1. PREPARE ONE MONTH WITH A COMMON SUPPORT MASK
// ============================================================

function prepareMonthlyClimate(img) {
  var date = ee.Date(img.get('system:time_start'));
  var nextMonth = date.advance(1, 'month');
  var secondsInMonth = nextMonth.difference(date, 'second');

  // Source bands required by the core climate product.
  var sourceRequired = img.select([
    'temperature_2m',
    'total_precipitation_sum',
    'total_evaporation_sum',
    'surface_solar_radiation_downwards_sum'
  ]);

  // Common source support:
  // valid only where every required source band is valid.
  var commonMask = sourceRequired
    .mask()
    .reduce(ee.Reducer.min())
    .gt(0);

  // Monthly mean 2-m temperature: K -> degree C.
  var tempC = img
    .select('temperature_2m')
    .subtract(273.15)
    .rename('tempC')
    .toFloat();

  // Monthly accumulated precipitation: m -> mm.
  // Raw signed values are retained for later local QC.
  var precipMmRaw = img
    .select('total_precipitation_sum')
    .multiply(1000)
    .rename('precip_mm_raw')
    .toFloat();

  // ECMWF evaporation convention is downward-positive.
  // Source evaporation is usually negative.
  //
  // After multiplication by -1000:
  //   positive value = evaporation / evapotranspiration
  //   negative value = net condensation
  var aetMmRaw = img
    .select('total_evaporation_sum')
    .multiply(-1000)
    .rename('aet_mm_raw')
    .toFloat();

  // Climatic water balance:
  // positive = precipitation exceeds AET
  // negative = AET exceeds precipitation
  var waterBalanceMmRaw = precipMmRaw
    .subtract(aetMmRaw)
    .rename('waterBalance_mm_raw')
    .toFloat();

  // Monthly accumulated downward shortwave radiation:
  // J m-2 -> monthly mean W m-2.
  var sradWm2 = img
    .select('surface_solar_radiation_downwards_sum')
    .divide(secondsInMonth)
    .rename('srad_Wm2')
    .toFloat();

  return ee.Image.cat([
      tempC,
      precipMmRaw,
      aetMmRaw,
      waterBalanceMmRaw,
      sradWm2
    ])
    .updateMask(commonMask)
    .copyProperties(
      img,
      ['system:time_start', 'system:index']
    );
}


// ============================================================
// 2. AGGREGATE TO FIXED GLOBAL 0.5-DEGREE GRID
// ============================================================

function aggregateToG050(img) {
  return img
    .reduceResolution({
      reducer: ee.Reducer.mean(),
      bestEffort: false,

      // ERA5-Land is approximately 0.1 degree.
      // A 0.5-degree target cell normally receives about 25 source cells.
      maxPixels: 256
    })
    .reproject({
      crs: CONFIG.crs,
      crsTransform: TARGET_TRANSFORM
    })
    .copyProperties(
      img,
      ['system:time_start', 'system:index']
    );
}


// ============================================================
// 3. RENAME MONTHLY BANDS
// ============================================================

function renameMonthlyBands(img) {
  var dateText = ee.Date(
    img.get('system:time_start')
  ).format('YYYYMM');

  return img
    .rename([
      ee.String('tempC_').cat(dateText),
      ee.String('precip_mm_raw_').cat(dateText),
      ee.String('aet_mm_raw_').cat(dateText),
      ee.String('waterBalance_mm_raw_').cat(dateText),
      ee.String('srad_Wm2_').cat(dateText)
    ])
    .copyProperties(
      img,
      ['system:time_start', 'system:index']
    );
}


// ============================================================
// 4. BUILD ONE ANNUAL 60-BAND STACK
// ============================================================

function buildAnnualStack(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');

  var rawCollection = ee.ImageCollection(CONFIG.source)
    .filterDate(start, end)
    .sort('system:time_start');

  var processedCollection = rawCollection
    .map(prepareMonthlyClimate)
    .map(aggregateToG050)
    .sort('system:time_start');

  var renamedCollection = processedCollection
    .map(renameMonthlyBands);

  var cleanBandNames = processedCollection
    .aggregate_array('system:time_start')
    .map(function(timeValue) {
      var dateText = ee.Date(timeValue).format('YYYYMM');

      return [
        ee.String('tempC_').cat(dateText),
        ee.String('precip_mm_raw_').cat(dateText),
        ee.String('aet_mm_raw_').cat(dateText),
        ee.String('waterBalance_mm_raw_').cat(dateText),
        ee.String('srad_Wm2_').cat(dateText)
      ];
    })
    .flatten();

  var annualStack = ee.ImageCollection(renamedCollection)
    .toBands()
    .rename(cleanBandNames)
    .toFloat()
    .set({
      dataset: CONFIG.source,
      product: 'ERA5Land_core_monthly_climate',
      year: year,
      resolution_degree: CONFIG.resDeg,
      common_mask:
        'intersection_of_required_source_band_masks',
      evaporation_conversion:
        'aet_mm_raw=-1000*total_evaporation_sum',
      water_balance_definition:
        'waterBalance_mm_raw=precip_mm_raw-aet_mm_raw',
      radiation_conversion:
        'monthly_sum_Jm2/exact_month_seconds',
      noData: CONFIG.noData,
      version: CONFIG.version
    });

  return {
    rawCollection: rawCollection,
    processedCollection: processedCollection,
    image: annualStack,
    bandNames: cleanBandNames
  };
}


// ============================================================
// 5. EXPORT ONE YEAR
// ============================================================

function exportOneYear(year) {
  var result = buildAnnualStack(year);

  var prefix =
    'ERA5Land_coreClimate_monthly_g050_global_' +
    year +
    '_' +
    CONFIG.version;

  var exportImage = result.image
    .unmask(CONFIG.noData, false)
    .toFloat();

  print('------------------------------------------------------------');
  print('Preparing year:', year);
  print('Task name:', prefix);
  print('Raw monthly image count:', result.rawCollection.size());
  print(
    'Processed monthly image count:',
    result.processedCollection.size()
  );
  print('Expected monthly image count:', 12);
  print('Output band count:', exportImage.bandNames().length());
  print('Expected output band count:', 60);
  print('Output file:', prefix + '.tif');
  print('------------------------------------------------------------');

  Export.image.toDrive({
    image: exportImage,
    description: prefix,
    folder: CONFIG.outputFolder,
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
// 6. CREATE 24 EXPORT TASKS
// ============================================================

for (
  var year = CONFIG.startYear;
  year <= CONFIG.endYear;
  year++
) {
  exportOneYear(year);
}

print('============================================================');
print('All annual export tasks have been created.');
print(
  'Expected task count:',
  CONFIG.endYear - CONFIG.startYear + 1
);
print('Run all tasks in the Tasks panel.');
print('============================================================');
