/**** DATA 07 FORMAL EXPORT — ALL YEARS IN ONE SCRIPT
 * Dataset: MODIS/061/MOD17A3HGF
 * Years: 2001–2024
 * Output: 24 global 0.05-degree GeoTIFF files, one per year.
 * Grid: EPSG:4326, [-180,-60,180,85], 7200 x 2900.
 * Bands: support fraction, GPP, NPP, NPP_QC.
 * Version: v04
 */

var CONFIG = {
  source: 'MODIS/061/MOD17A3HGF',
  startYear: 2001,
  endYear: 2024,
  targetCrs: 'EPSG:4326',
  lonMin: -180,
  lonMax: 180,
  latMin: -60,
  latMax: 85,
  widthPixels: 7200,
  heightPixels: 2900,
  maxPixelsReduce: 2048,
  maxPixelsExport: 1e13,
  noData: -9999,
  version: 'v04',
  driveFolder: 'GlobalForestResilience_Data07_MOD17A3HGF_GPP_NPP_g005_global_2001_2024_v04'
};

var GLOBAL_REGION = ee.Geometry.Rectangle(
  [CONFIG.lonMin, CONFIG.latMin, CONFIG.lonMax, CONFIG.latMax],
  null,
  false
);

var DIMENSIONS_TEXT = String(CONFIG.widthPixels) + 'x' + String(CONFIG.heightPixels);

function createOneYearExport(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var collection = ee.ImageCollection(CONFIG.source)
    .filterDate(start, end)
    .sort('system:time_start');
  var source = ee.Image(collection.first());
  var nativeProjection = source.select('Gpp').projection();

  var gpp = source.select('Gpp').multiply(0.0001).toFloat();
  var npp = source.select('Npp').multiply(0.0001).toFloat();
  var qc = source.select('Npp_QC').toFloat();

  var support = gpp.mask()
    .and(npp.mask())
    .and(qc.mask())
    .unmask(0, false)
    .toFloat()
    .rename('source_support_area_frac_' + year);

  var stack = ee.Image.cat([
    support,
    gpp.updateMask(support.eq(1)).rename('gpp_mean_valid_kgC_m2_yr_' + year),
    npp.updateMask(support.eq(1)).rename('npp_mean_valid_kgC_m2_yr_' + year),
    qc.updateMask(support.eq(1)).rename('npp_qc_mean_valid_pct_' + year)
  ]).toFloat().setDefaultProjection(nativeProjection);

  var output = stack
    .clip(GLOBAL_REGION)
    .setDefaultProjection(nativeProjection)
    .reduceResolution({
      reducer: ee.Reducer.mean(),
      bestEffort: false,
      maxPixels: CONFIG.maxPixelsReduce
    })
    .toFloat()
    .set({
      dataset: CONFIG.source,
      year: year,
      spatial_domain: '[-180,-60,180,85]',
      target_grid: 'g005',
      target_crs: CONFIG.targetCrs,
      target_resolution_degree: 0.05,
      output_dimensions: DIMENSIONS_TEXT,
      gpp_npp_scale_factor: 0.0001,
      units_gpp_npp: 'kg C m-2 yr-1',
      version: CONFIG.version
    });

  var prefix = 'MOD17A3HGF_GPP_NPP_g005_global_' + year + '_' + CONFIG.version;

  print('Year:', year,
        'source images:', collection.size(),
        'bands:', stack.bandNames().size(),
        'file:', prefix + '.tif');

  Export.image.toDrive({
    image: output.clip(GLOBAL_REGION).unmask(CONFIG.noData).toFloat(),
    description: prefix,
    folder: CONFIG.driveFolder,
    fileNamePrefix: prefix,
    region: GLOBAL_REGION,
    crs: CONFIG.targetCrs,
    dimensions: DIMENSIONS_TEXT,
    maxPixels: CONFIG.maxPixelsExport,
    fileFormat: 'GeoTIFF',
    formatOptions: {cloudOptimized: true, noData: CONFIG.noData}
  });
}

print('DATA 07 all-years export v04');
print('Years:', CONFIG.startYear, 'to', CONFIG.endYear);
print('Expected tasks: 24');
print('Common Drive folder:', CONFIG.driveFolder);

for (var year = CONFIG.startYear; year <= CONFIG.endYear; year++) {
  createOneYearExport(year);
}

print('All 24 tasks created.');
