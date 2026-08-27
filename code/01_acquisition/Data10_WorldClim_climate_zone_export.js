/**** DATA 10B GLOBAL TEST v04
 *
 * GEE-DERIVED BROAD KÖPPEN-LIKE CLIMATE ZONES
 *
 * Source:
 *   WORLDCLIM/V1/MONTHLY
 *
 * Source climatology:
 *   1960–1990 monthly normals
 *
 * Purpose:
 *   Replace the original paper's climate-zone grouping with a fully
 *   GEE-based and reproducible broad climate classification.
 *
 * Broad classes:
 *   1 Tropical
 *   2 Arid
 *   3 Temperate
 *   4 Boreal / continental
 *   5 Polar
 *
 * Classification logic:
 *   - Arid class is evaluated first using the Köppen precipitation
 *     threshold based on annual temperature and seasonal rainfall.
 *   - Non-arid pixels are separated using coldest- and warmest-month
 *     mean temperatures.
 *
 * Test tiles:
 *   1 W090_W060_S30_N00_AMAZON
 *   2 E000_E030_N00_N30_WEST_AFRICA_SAHARA
 *   3 E000_E030_N30_N60_EUROPE_MEDITERRANEAN
 *   4 E060_E090_N60_N85_SIBERIA_ARCTIC
 *
 * Target:
 *   EPSG:4326
 *   0.05 degree
 *
 * Output:
 *   4 tasks
 *   14 float32 bands per tile
 *
 * Important:
 *   - Temperature uses the official 0.1 scale factor.
 *   - Precipitation is in mm.
 *   - Climate fractions are conditional on valid WorldClim support.
 *   - No forest mask is applied during export.
 *   - The polar class is retained for completeness; the later forest
 *     mask will remove most polar cells from forest analyses.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  source:
    'WORLDCLIM/V1/MONTHLY',

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
    2048,

  maxPixelsExport:
    1e13,

  noData:
    -9999,

  version:
    'v04',

  driveFolder:
    'GlobalForestResilience_Data10_WorldClim_' +
    'broad_climate_zones_g005_global_test_v04'
};


var GLOBAL_TILE = {
  name:
    'GLOBAL_W180_E180_S60_N85',

  lonMin:
    -180,

  lonMax:
    180,

  latMin:
    -60,

  latMax:
    85
};


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


function getMonthImage(
  collection,
  month,
  region
) {
  return ee.Image(
      collection
        .filter(
          ee.Filter.eq(
            'month',
            month
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


// ============================================================
// 2. SOURCE COLLECTION
// ============================================================

var monthlyCollection = ee.ImageCollection(
  CONFIG.source
);


print('============================================================');
print('DATA 10A WORLDCLIM BROAD CLIMATE-ZONE GLOBAL TEST v04');
print('Source:', CONFIG.source);
print(
  'Monthly source image count, expected 12:',
  monthlyCollection.size()
);
print('Global task count, expected 1: 1');
print('Target resolution: 0.05 degree');
print('Global bounds: [-180, -60, 180, 85]');
print('Expected output dimensions: 7200x2900');
print('Output bands per tile: 14');
print('============================================================');


// ============================================================
// 3. BUILD ONE TILE'S NATIVE CLIMATE STACK
// ============================================================

function buildNativeClimateStack(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var temperatureImages = [];

  var precipitationImages = [];

  var supportObservations = [];


  for (
    var month = 1;
    month <= 12;
    month++
  ) {
    var monthlyImage = getMonthImage(
      monthlyCollection,
      month,
      bufferedRegion
    );


    // All images entering one ImageCollection must have a
    // compatible band schema. Keep the month as an image property,
    // but give every temperature image the same band name.
    var temperatureC = monthlyImage
      .select(
        'tavg'
      )
      .multiply(
        0.1
      )
      .toFloat()
      .rename(
        'temperature_c'
      )
      .set(
        'month',
        month
      );


    // Use one common band name for all monthly precipitation
    // images so mean(), min(), max() and sum() can reduce the
    // collection by matching bands.
    var precipitationMm = monthlyImage
      .select(
        'prec'
      )
      .toFloat()
      .rename(
        'precipitation_mm'
      )
      .set(
        'month',
        month
      );


    temperatureImages.push(
      temperatureC
    );


    precipitationImages.push(
      precipitationMm
    );


    supportObservations.push(
      makeSupportObservation(
        monthlyImage,
        'tavg'
      )
    );


    supportObservations.push(
      makeSupportObservation(
        monthlyImage,
        'prec'
      )
    );
  }


  var referenceImage = getMonthImage(
    monthlyCollection,
    1,
    bufferedRegion
  );


  var nativeProjection = referenceImage
    .select(
      'tavg'
    )
    .projection();


  var requiredSupportCount =
    supportObservations.length;


  var validSupportCount = ee.ImageCollection
    .fromImages(
      supportObservations
    )
    .count();


  var commonSupport = validSupportCount
    .eq(
      requiredSupportCount
    )
    .unmask(0)
    .toFloat()
    .rename(
      'worldclim_support_area_frac'
    );


  var temperatureCollection = ee.ImageCollection
    .fromImages(
      temperatureImages
    );


  var precipitationCollection = ee.ImageCollection
    .fromImages(
      precipitationImages
    );


  print(
    tile.name + ' temperature collection first bands, expected [temperature_c]:',
    ee.Image(
      temperatureCollection.first()
    ).bandNames()
  );


  print(
    tile.name + ' precipitation collection first bands, expected [precipitation_mm]:',
    ee.Image(
      precipitationCollection.first()
    ).bandNames()
  );


  var annualMeanTemperature = temperatureCollection
    .mean()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'annual_mean_temperature_c'
    );


  var coldestMonthTemperature = temperatureCollection
    .min()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'coldest_month_mean_temperature_c'
    );


  var warmestMonthTemperature = temperatureCollection
    .max()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'warmest_month_mean_temperature_c'
    );


  var annualPrecipitation = precipitationCollection
    .sum()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'annual_precipitation_mm'
    );


  var northernSummerImages = [];

  var southernSummerImages = [];


  for (
    var summerMonth = 1;
    summerMonth <= 12;
    summerMonth++
  ) {
    var precipitationImage =
      precipitationImages[
        summerMonth - 1
      ];


    if (
      summerMonth >= 4 &&
      summerMonth <= 9
    ) {
      northernSummerImages.push(
        precipitationImage
      );
    }


    if (
      summerMonth >= 10 ||
      summerMonth <= 3
    ) {
      southernSummerImages.push(
        precipitationImage
      );
    }
  }


  var northernSummerPrecipitation =
    ee.ImageCollection
      .fromImages(
        northernSummerImages
      )
      .sum();


  var southernSummerPrecipitation =
    ee.ImageCollection
      .fromImages(
        southernSummerImages
      )
      .sum();


  var latitude = ee.Image
    .pixelLonLat()
    .select(
      'latitude'
    );


  var summerPrecipitation =
    northernSummerPrecipitation
      .where(
        latitude.lt(0),
        southernSummerPrecipitation
      )
      .updateMask(
        commonSupport.eq(1)
      );


  // Keep one common valid mask across all 14 output bands.
  // When annual precipitation is exactly zero, the seasonal fraction
  // is mathematically undefined. For this broad climate classification,
  // assign 0 rather than masking the pixel. Those pixels are still
  // classified from annual precipitation, temperature and the aridity
  // threshold, and the export remains internally mask-consistent.
  var summerPrecipitationFraction =
    summerPrecipitation
      .divide(
        annualPrecipitation.max(1e-6)
      )
      .where(
        annualPrecipitation.eq(0),
        0
      )
      .updateMask(
        commonSupport.eq(1)
      )
      .clamp(
        0,
        1
      )
      .rename(
        'summer_halfyear_precipitation_fraction'
      );


  // Köppen aridity-threshold adjustment:
  // +280 mm when >=70% of precipitation falls in summer,
  // +0 mm when <=30% falls in summer,
  // +140 mm otherwise.
  var aridityAdjustment = annualMeanTemperature
    .multiply(0)
    .add(140)
    .where(
      summerPrecipitationFraction.gte(0.70),
      280
    )
    .where(
      summerPrecipitationFraction.lte(0.30),
      0
    );


  var aridityThreshold = annualMeanTemperature
    .multiply(20)
    .add(
      aridityAdjustment
    )
    .max(0)
    .rename(
      'koppen_aridity_threshold_mm'
    );


  var arid = annualPrecipitation
    .lt(
      aridityThreshold
    )
    .and(
      commonSupport.eq(1)
    );


  var tropical = arid
    .not()
    .and(
      coldestMonthTemperature.gte(18)
    )
    .and(
      commonSupport.eq(1)
    );


  var polar = arid
    .not()
    .and(
      warmestMonthTemperature.lt(10)
    )
    .and(
      commonSupport.eq(1)
    );


  var temperate = arid
    .not()
    .and(
      coldestMonthTemperature.gt(0)
    )
    .and(
      coldestMonthTemperature.lt(18)
    )
    .and(
      warmestMonthTemperature.gte(10)
    )
    .and(
      commonSupport.eq(1)
    );


  var boreal = arid
    .not()
    .and(
      coldestMonthTemperature.lte(0)
    )
    .and(
      warmestMonthTemperature.gte(10)
    )
    .and(
      commonSupport.eq(1)
    );


  var tropicalShare = tropical
    .toFloat()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'tropical_climate_share_valid'
    );


  var aridShare = arid
    .toFloat()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'arid_climate_share_valid'
    );


  var temperateShare = temperate
    .toFloat()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'temperate_climate_share_valid'
    );


  var borealShare = boreal
    .toFloat()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'boreal_climate_share_valid'
    );


  var polarShare = polar
    .toFloat()
    .updateMask(
      commonSupport.eq(1)
    )
    .rename(
      'polar_climate_share_valid'
    );


  var classClosure = tropicalShare
    .add(
      aridShare
    )
    .add(
      temperateShare
    )
    .add(
      borealShare
    )
    .add(
      polarShare
    )
    .rename(
      'climate_class_closure_valid'
    );


  return ee.Image.cat([
      commonSupport,

      annualMeanTemperature,

      coldestMonthTemperature,

      warmestMonthTemperature,

      annualPrecipitation,

      summerPrecipitationFraction,

      aridityThreshold,

      tropicalShare,

      aridShare,

      temperateShare,

      borealShare,

      polarShare,

      classClosure
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
// 4. AGGREGATE AND EXPORT ONE TEST TILE
// ============================================================

function exportOneGlobalTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );


  var nativeStack = buildNativeClimateStack(
    tile
  );


  var outputCoreG005 = nativeStack
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
    );


  var climateShares = outputCoreG005
    .select([
      'tropical_climate_share_valid',
      'arid_climate_share_valid',
      'temperate_climate_share_valid',
      'boreal_climate_share_valid',
      'polar_climate_share_valid'
    ]);


  var dominantClimateCode = climateShares
    .toArray()
    .arrayArgmax()
    .arrayGet([0])
    .add(1)
    .toFloat()
    .updateMask(
      outputCoreG005
        .select(
          'worldclim_support_area_frac'
        )
        .gt(0)
    )
    .rename(
      'dominant_climate_zone_code'
    );


  var outputG005 = ee.Image.cat([
      outputCoreG005,
      dominantClimateCode
    ])
    .toFloat()
    .set({
      dataset:
        CONFIG.source,

      climatology_period:
        '1960-1990 monthly normals',

      tile_name:
        tile.name,

      target_grid:
        'g005',

      target_crs:
        CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      class_codes:
        '1 tropical; 2 arid; 3 temperate; 4 boreal; 5 polar',

      classification:
        'broad Koppen-like classes derived from monthly temperature and precipitation',

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
    'WorldClim_broad_climate_zones_g005_global_' +
    CONFIG.version;


  print('------------------------------------------------------------');
  print('Preparing tile:', tile.name);
  print(
    'Expected dimensions:',
    dimensionsText
  );

  print(
    'Expected global dimensions, should be 7200x2900:',
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
// 5. CREATE ONE GLOBAL TEST TASK
// ============================================================

exportOneGlobalTile(
  GLOBAL_TILE
);


print('============================================================');
print('DATA 10B GLOBAL TEST TASK CREATION COMPLETED');
print('Expected task count: 1');
print('Expected output dimensions: 7200x2900');
print('Expected output bands: 14');
print('Output resolution: 0.05 degree');
print('============================================================');


// No Map.addLayer(), reduceRegion(), chart, or global diagnostics.
