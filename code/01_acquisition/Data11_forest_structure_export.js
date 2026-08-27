/**** DATA 11B GLOBAL TEST v02
 *
 * GLOBAL FOREST STRUCTURE BASELINE
 *
 * GEE sources:
 *   1. NASA/JPL/global_forest_canopy_height_2005
 *   2. NASA/ORNL/biomass_carbon_density/v1
 *
 * Purpose:
 *   Add static forest structural controls for later resilience analysis:
 *   canopy height, aboveground carbon, belowground carbon, total living
 *   biomass carbon, and uncertainty.
 *
 * Source characteristics:
 *   - Canopy height: 2005, approximately 927.67 m, meters.
 *   - Biomass carbon: 2010, 300 m, Mg C/ha.
 *
 * Test tiles:
 *   1. W090_W060_S30_N00_AMAZON
 *   2. E060_E090_N60_N85_BOREAL
 *
 * Target:
 *   EPSG:4326
 *   0.05 degree
 *
 * Output:
 *   2 tasks
 *   8 float32 bands per tile
 *
 * Bands:
 *   1 canopy_height_support_area_frac_2005
 *   2 canopy_height_mean_valid_m_2005
 *   3 biomass_support_area_frac_2010
 *   4 aboveground_biomass_carbon_mean_valid_Mg_ha_2010
 *   5 aboveground_biomass_uncertainty_mean_valid_Mg_ha_2010
 *   6 belowground_biomass_carbon_mean_valid_Mg_ha_2010
 *   7 belowground_biomass_uncertainty_mean_valid_Mg_ha_2010
 *   8 total_living_biomass_carbon_mean_valid_Mg_ha_2010
 *
 * Important:
 *   - Canopy and biomass supports are kept separately.
 *   - Zero canopy height and zero biomass are retained as valid values
 *     wherever the source products regard them as valid.
 *   - Source images are clipped before reduceResolution().
 *   - No explicit reproject() is used.
 *   - Later 0.05° -> 0.5° aggregation must use the matching support band.
 */


// ============================================================
// 0. CONFIGURATION
// ============================================================

var CONFIG = {
  canopySource:
    'NASA/JPL/global_forest_canopy_height_2005',

  biomassSource:
    'NASA/ORNL/biomass_carbon_density/v1',

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

  maxPixelsReduceCanopy:
    512,

  maxPixelsReduceBiomass:
    4096,

  maxPixelsExport:
    1e13,

  noData:
    -9999,

  version:
    'v02',

  driveFolder:
    'GlobalForestResilience_Data11_ForestStructure_' +
    'CanopyHeight2005_BiomassCarbon2010_g005_global_test_v02'
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


// ============================================================
// 2. LOAD STATIC SOURCES
// ============================================================

var canopySource = ee.Image(
  CONFIG.canopySource
);


var biomassCollection = ee.ImageCollection(
  CONFIG.biomassSource
);


var biomassSource = ee.Image(
  biomassCollection.first()
);


var canopyProjection = canopySource
  .select('1')
  .projection();


var biomassProjection = biomassSource
  .select('agb')
  .projection();


print('============================================================');
print('DATA 11A FOREST STRUCTURE GLOBAL TEST v02');
print('Canopy source:', CONFIG.canopySource);
print('Biomass source:', CONFIG.biomassSource);
print(
  'Biomass source image count, expected 1:',
  biomassCollection.size()
);
print(
  'Canopy source bands:',
  canopySource.bandNames()
);
print(
  'Biomass source bands:',
  biomassSource.bandNames()
);
print(
  'Canopy nominal scale, expected about 927.67 m:',
  canopyProjection.nominalScale()
);
print(
  'Biomass nominal scale, expected about 300 m:',
  biomassProjection.nominalScale()
);
print('Global task count, expected 1: 1');
print('Global bounds: [-180, -60, 180, 85]');
print('Expected global dimensions: 7200x2900');
print('Output resolution: 0.05 degree');
print('Output bands per tile: 8');
print('============================================================');


// ============================================================
// 3. BUILD CANOPY-HEIGHT STACK FOR ONE TILE
// ============================================================

function buildCanopyStack(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var canopyHeight = canopySource
    .select('1')
    .clip(
      bufferedRegion
    )
    .toFloat();


  var canopySupport = canopyHeight
    .mask()
    .unmask(
      0,
      false
    )
    .toFloat()
    .clip(
      bufferedRegion
    )
    .rename(
      'canopy_height_support_area_frac_2005'
    );


  var canopyHeightValid = canopyHeight
    .updateMask(
      canopySupport.eq(1)
    )
    .rename(
      'canopy_height_mean_valid_m_2005'
    );


  return ee.Image.cat([
      canopySupport,
      canopyHeightValid
    ])
    .toFloat()
    .setDefaultProjection(
      canopyProjection
    )
    .clip(
      bufferedRegion
    );
}


// ============================================================
// 4. BUILD BIOMASS-CARBON STACK FOR ONE TILE
// ============================================================

function buildBiomassStack(tile) {
  var bufferedRegion = bufferedTileRegion(
    tile
  );


  var biomassTile = biomassSource
    .select([
      'agb',
      'agb_uncertainty',
      'bgb',
      'bgb_uncertainty'
    ])
    .clip(
      bufferedRegion
    )
    .toFloat();


  var biomassSupport = biomassTile
    .mask()
    .reduce(
      ee.Reducer.min()
    )
    .unmask(
      0,
      false
    )
    .toFloat()
    .clip(
      bufferedRegion
    )
    .rename(
      'biomass_support_area_frac_2010'
    );


  var agb = biomassTile
    .select('agb')
    .updateMask(
      biomassSupport.eq(1)
    )
    .rename(
      'aboveground_biomass_carbon_mean_valid_Mg_ha_2010'
    );


  var agbUncertainty = biomassTile
    .select('agb_uncertainty')
    .updateMask(
      biomassSupport.eq(1)
    )
    .rename(
      'aboveground_biomass_uncertainty_mean_valid_Mg_ha_2010'
    );


  var bgb = biomassTile
    .select('bgb')
    .updateMask(
      biomassSupport.eq(1)
    )
    .rename(
      'belowground_biomass_carbon_mean_valid_Mg_ha_2010'
    );


  var bgbUncertainty = biomassTile
    .select('bgb_uncertainty')
    .updateMask(
      biomassSupport.eq(1)
    )
    .rename(
      'belowground_biomass_uncertainty_mean_valid_Mg_ha_2010'
    );


  var totalLivingBiomass = agb
    .add(
      bgb
    )
    .rename(
      'total_living_biomass_carbon_mean_valid_Mg_ha_2010'
    );


  return ee.Image.cat([
      biomassSupport,
      agb,
      agbUncertainty,
      bgb,
      bgbUncertainty,
      totalLivingBiomass
    ])
    .toFloat()
    .setDefaultProjection(
      biomassProjection
    )
    .clip(
      bufferedRegion
    );
}


// ============================================================
// 5. AGGREGATE AND EXPORT ONE TEST TILE
// ============================================================

function exportOneGlobalTile(tile) {
  var exactRegion = exactTileRegion(
    tile
  );


  var canopyNative = buildCanopyStack(
    tile
  );


  var biomassNative = buildBiomassStack(
    tile
  );


  var canopyG005 = canopyNative
    .reduceResolution({
      reducer:
        ee.Reducer.mean(),

      bestEffort:
        false,

      maxPixels:
        CONFIG.maxPixelsReduceCanopy
    })
    .toFloat();


  var biomassG005 = biomassNative
    .reduceResolution({
      reducer:
        ee.Reducer.mean(),

      bestEffort:
        false,

      maxPixels:
        CONFIG.maxPixelsReduceBiomass
    })
    .toFloat();


  var outputG005 = ee.Image.cat([
      canopyG005,
      biomassG005
    ])
    .toFloat()
    .clip(
      exactRegion
    )
    .set({
      canopy_dataset:
        CONFIG.canopySource,

      canopy_year:
        2005,

      biomass_dataset:
        CONFIG.biomassSource,

      biomass_year:
        2010,

      tile_name:
        tile.name,

      target_grid:
        'g005',

      target_crs:
        CONFIG.targetCrs,

      target_resolution_degree:
        CONFIG.targetResolutionDegree,

      aggregation:
        'each source clipped and reduced separately before concatenation',

      canopy_zero_note:
        'zero canopy height is retained; apply the independent forest mask in later analysis',

      support_note:
        'canopy support is source-data coverage, not forest-cover fraction',

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
    'ForestStructure_CanopyHeight2005_' +
    'BiomassCarbon2010_g005_global_' +
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
// 6. CREATE ONE GLOBAL TEST TASK
// ============================================================

exportOneGlobalTile(
  GLOBAL_TILE
);


print('============================================================');
print('DATA 11B GLOBAL TEST TASK CREATION COMPLETED');
print('Expected task count: 1');
print('Expected dimensions: 7200x2900');
print('Expected output bands: 8');
print('Output resolution: 0.05 degree');
print('============================================================');


// No Map.addLayer(), reduceRegion(), chart, or global diagnostics.
