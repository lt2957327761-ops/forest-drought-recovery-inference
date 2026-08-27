/**** 03D_EXPORT_MOD44B_native1km_g010_2001_BATCH01of08_v01
 * Data 03: MOD44B annual tree cover
 *
 * FORMAL EXPORT BATCH
 *   Year: 2001
 *   Batch: 01 of 08
 *   Tasks in this script: 46
 *   First tile: W180_W170_S50_S40
 *   Last tile: W120_W110_N30_N40
 *
 * Global 10-degree screen:
 *   Total tiles: 540
 *   Export-required LAND_OR_ISLAND tiles: 368
 *   PURE_OCEAN tiles excluded from GEE export: 172
 *
 * Annual workflow:
 *   MOD44B Percent_Tree_Cover (native 250 m)
 *   -> native MODIS Sinusoidal 1 km intermediate
 *   -> 10-degree buffered GeoTIFF tiles
 *
 * Output bands:
 *   1. treecover_pct_native1km_2001
 *   2. support_frac_native1km_2001
 *
 * IMPORTANT:
 *   - Keep native MODIS Sinusoidal projection.
 *   - Do not set EPSG:4326 in this GEE export.
 *   - Local Python processing will later reproject and crop to
 *     exact EPSG:4326 0.05-degree standard tiles.
 *   - bestEffort is false.
 *   - NoData is -9999 for tree cover.
 *   - support is 0 where MOD44B has no valid source support.
 */


// ============================================================
// 0. CONFIG
// ============================================================

var TARGET_YEAR = 2001;
var BATCH_ID = 'B01';
var VERSION = 'v01';

var CONFIG = {
  source: 'MODIS/061/MOD44B',

  targetYear: TARGET_YEAR,
  batchId: BATCH_ID,
  version: VERSION,

  nativeScaleM: 1000,
  bufferDeg: 0.2,

  noData: -9999,
  maxPixels: 1e13,

  folderProd:
    'GlobalForestResilience_Data03_MOD44B_native1km_g010_2001_v01'
};

var TILES = [
  {name: 'W180_W170_S50_S40', lonMin: -180, lonMax: -170, latMin: -50, latMax: -40},
  {name: 'W180_W170_S30_S20', lonMin: -180, lonMax: -170, latMin: -30, latMax: -20},
  {name: 'W180_W170_S20_S10', lonMin: -180, lonMax: -170, latMin: -20, latMax: -10},
  {name: 'W180_W170_S10_N00', lonMin: -180, lonMax: -170, latMin: -10, latMax: 0},
  {name: 'W180_W170_N00_N10', lonMin: -180, lonMax: -170, latMin: 0, latMax: 10},
  {name: 'W180_W170_N20_N30', lonMin: -180, lonMax: -170, latMin: 20, latMax: 30},
  {name: 'W180_W170_N50_N60', lonMin: -180, lonMax: -170, latMin: 50, latMax: 60},
  {name: 'W180_W170_N60_N70', lonMin: -180, lonMax: -170, latMin: 60, latMax: 70},
  {name: 'W180_W170_N70_N80', lonMin: -180, lonMax: -170, latMin: 70, latMax: 80},
  {name: 'W170_W160_S20_S10', lonMin: -170, lonMax: -160, latMin: -20, latMax: -10},
  {name: 'W170_W160_S10_N00', lonMin: -170, lonMax: -160, latMin: -10, latMax: 0},
  {name: 'W170_W160_N00_N10', lonMin: -170, lonMax: -160, latMin: 0, latMax: 10},
  {name: 'W170_W160_N20_N30', lonMin: -170, lonMax: -160, latMin: 20, latMax: 30},
  {name: 'W170_W160_N50_N60', lonMin: -170, lonMax: -160, latMin: 50, latMax: 60},
  {name: 'W170_W160_N60_N70', lonMin: -170, lonMax: -160, latMin: 60, latMax: 70},
  {name: 'W170_W160_N70_N80', lonMin: -170, lonMax: -160, latMin: 70, latMax: 80},
  {name: 'W160_W150_S30_S20', lonMin: -160, lonMax: -150, latMin: -30, latMax: -20},
  {name: 'W160_W150_S20_S10', lonMin: -160, lonMax: -150, latMin: -20, latMax: -10},
  {name: 'W160_W150_S10_N00', lonMin: -160, lonMax: -150, latMin: -10, latMax: 0},
  {name: 'W160_W150_N00_N10', lonMin: -160, lonMax: -150, latMin: 0, latMax: 10},
  {name: 'W160_W150_N10_N20', lonMin: -160, lonMax: -150, latMin: 10, latMax: 20},
  {name: 'W160_W150_N20_N30', lonMin: -160, lonMax: -150, latMin: 20, latMax: 30},
  {name: 'W160_W150_N50_N60', lonMin: -160, lonMax: -150, latMin: 50, latMax: 60},
  {name: 'W160_W150_N60_N70', lonMin: -160, lonMax: -150, latMin: 60, latMax: 70},
  {name: 'W160_W150_N70_N80', lonMin: -160, lonMax: -150, latMin: 70, latMax: 80},
  {name: 'W150_W140_S30_S20', lonMin: -150, lonMax: -140, latMin: -30, latMax: -20},
  {name: 'W150_W140_S20_S10', lonMin: -150, lonMax: -140, latMin: -20, latMax: -10},
  {name: 'W150_W140_S10_N00', lonMin: -150, lonMax: -140, latMin: -10, latMax: 0},
  {name: 'W150_W140_N50_N60', lonMin: -150, lonMax: -140, latMin: 50, latMax: 60},
  {name: 'W150_W140_N60_N70', lonMin: -150, lonMax: -140, latMin: 60, latMax: 70},
  {name: 'W150_W140_N70_N80', lonMin: -150, lonMax: -140, latMin: 70, latMax: 80},
  {name: 'W140_W130_S30_S20', lonMin: -140, lonMax: -130, latMin: -30, latMax: -20},
  {name: 'W140_W130_S20_S10', lonMin: -140, lonMax: -130, latMin: -20, latMax: -10},
  {name: 'W140_W130_S10_N00', lonMin: -140, lonMax: -130, latMin: -10, latMax: 0},
  {name: 'W140_W130_N50_N60', lonMin: -140, lonMax: -130, latMin: 50, latMax: 60},
  {name: 'W140_W130_N60_N70', lonMin: -140, lonMax: -130, latMin: 60, latMax: 70},
  {name: 'W140_W130_N70_N80', lonMin: -140, lonMax: -130, latMin: 70, latMax: 80},
  {name: 'W130_W120_S30_S20', lonMin: -130, lonMax: -120, latMin: -30, latMax: -20},
  {name: 'W130_W120_N30_N40', lonMin: -130, lonMax: -120, latMin: 30, latMax: 40},
  {name: 'W130_W120_N40_N50', lonMin: -130, lonMax: -120, latMin: 40, latMax: 50},
  {name: 'W130_W120_N50_N60', lonMin: -130, lonMax: -120, latMin: 50, latMax: 60},
  {name: 'W130_W120_N60_N70', lonMin: -130, lonMax: -120, latMin: 60, latMax: 70},
  {name: 'W130_W120_N70_N80', lonMin: -130, lonMax: -120, latMin: 70, latMax: 80},
  {name: 'W120_W110_N10_N20', lonMin: -120, lonMax: -110, latMin: 10, latMax: 20},
  {name: 'W120_W110_N20_N30', lonMin: -120, lonMax: -110, latMin: 20, latMax: 30},
  {name: 'W120_W110_N30_N40', lonMin: -120, lonMax: -110, latMin: 30, latMax: 40}
];

print('============================================================');
print('Data 03 MOD44B formal native 1 km export');
print('Year:', CONFIG.targetYear);
print('Batch:', CONFIG.batchId);
print('Tasks in this script:', TILES.length);
print('Expected tasks in this script:', 46);
print('Drive folder:', CONFIG.folderProd);
print('Native scale:', CONFIG.nativeScaleM, 'm');
print('NoData:', CONFIG.noData);
print('First tile:', TILES[0]);
print('Last tile:', TILES[TILES.length - 1]);
print('============================================================');


// ============================================================
// 1. REGION FUNCTIONS
// ============================================================

function clampLon(value) {
  return Math.max(-180, Math.min(180, value));
}

function clampLat(value) {
  return Math.max(-60, Math.min(85, value));
}

function bufferedRegion(tile) {
  var eps = 1e-6;
  var buffer = CONFIG.bufferDeg;

  return ee.Geometry.Rectangle(
    [
      clampLon(tile.lonMin - buffer) + eps,
      clampLat(tile.latMin - buffer) + eps,
      clampLon(tile.lonMax + buffer) - eps,
      clampLat(tile.latMax + buffer) - eps
    ],
    null,
    false
  );
}


// ============================================================
// 2. LOAD ANNUAL MOD44B IMAGE
// ============================================================

var start = ee.Date.fromYMD(
  CONFIG.targetYear,
  1,
  1
);

var end = start.advance(
  1,
  'year'
);

var rawCollection = ee.ImageCollection(
    CONFIG.source
  )
  .filterDate(start, end)
  .sort('system:time_start');

print(
  'MOD44B source image count, expected 1:',
  rawCollection.size()
);

print(
  'MOD44B source date:',
  rawCollection
    .aggregate_array('system:time_start')
    .map(function(timeValue) {
      return ee.Date(timeValue).format('YYYY-MM-dd');
    })
);

var rawImage = ee.Image(
  rawCollection.first()
);

print(
  'Source bands:',
  rawImage.bandNames()
);


// ============================================================
// 3. BUILD NATIVE 1 KM TREE COVER + SUPPORT
// ============================================================

var rawTree = rawImage
  .select('Percent_Tree_Cover')
  .rename('treecover_pct_raw')
  .toFloat();

var rawProjection = rawTree.projection();

print(
  'Raw MOD44B projection:',
  rawProjection
);

print(
  'Raw MOD44B nominal scale:',
  rawProjection.nominalScale()
);

var tree1km = rawTree
  .reduceResolution({
    reducer: ee.Reducer.mean(),
    maxPixels: 256,
    bestEffort: false
  })
  .reproject({
    crs: rawProjection,
    scale: CONFIG.nativeScaleM
  })
  .rename(
    'treecover_pct_native1km_' +
    CONFIG.targetYear
  )
  .toFloat();

var rawSupport = rawTree
  .mask()
  .unmask(0, false)
  .rename('support_raw')
  .toFloat();

var support1km = rawSupport
  .reduceResolution({
    reducer: ee.Reducer.mean(),
    maxPixels: 256,
    bestEffort: false
  })
  .reproject({
    crs: rawProjection,
    scale: CONFIG.nativeScaleM
  })
  .clamp(0, 1)
  .rename(
    'support_frac_native1km_' +
    CONFIG.targetYear
  )
  .toFloat();

var nativeOutput = ee.Image.cat([
  tree1km,
  support1km
]).set({
  dataset: CONFIG.source,
  year: CONFIG.targetYear,
  batch: CONFIG.batchId,
  native_scale_m: CONFIG.nativeScaleM,
  tree_definition:
    'mean Percent_Tree_Cover over valid source pixels',
  support_definition:
    'fraction of valid 250 m source support in native 1 km pixel',
  version: CONFIG.version
});

print(
  'Output bands:',
  nativeOutput.bandNames()
);


// ============================================================
// 4. EXPORT FUNCTION
// ============================================================

function exportTile(tile) {
  var prefix =
    'MOD44B_native1km_g010_tile_' +
    tile.name +
    '_' +
    CONFIG.targetYear +
    '_' +
    CONFIG.version;

  var exportImage = ee.Image.cat([
    tree1km.unmask(CONFIG.noData, false),
    support1km.unmask(0, false)
  ]).toFloat();

  print('------------------------------------------------------------');
  print('Preparing task:', prefix);
  print('Batch:', CONFIG.batchId);
  print('Tile:', tile.name);
  print(
    'Exact target bounds:',
    [
      tile.lonMin,
      tile.latMin,
      tile.lonMax,
      tile.latMax
    ]
  );
  print(
    'Buffered native export region:',
    bufferedRegion(tile)
  );
  print('Drive folder:', CONFIG.folderProd);
  print('------------------------------------------------------------');

  Export.image.toDrive({
    image: exportImage,
    description: prefix,
    folder: CONFIG.folderProd,
    fileNamePrefix: prefix,

    // Keep native MODIS Sinusoidal projection.
    region: bufferedRegion(tile),
    scale: CONFIG.nativeScaleM,

    maxPixels: CONFIG.maxPixels,
    fileFormat: 'GeoTIFF',
    formatOptions: {
      cloudOptimized: true,
      noData: CONFIG.noData
    }
  });
}


// ============================================================
// 5. CREATE THIS BATCH'S TASKS
// ============================================================

for (
  var index = 0;
  index < TILES.length;
  index++
) {
  exportTile(TILES[index]);
}

print('============================================================');
print('Batch task creation completed.');
print('Year:', CONFIG.targetYear);
print('Batch:', CONFIG.batchId);
print('Created tasks:', TILES.length);
print('Expected tasks:', 46);
print('Drive folder:', CONFIG.folderProd);
print('============================================================');
