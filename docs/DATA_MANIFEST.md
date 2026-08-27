# Data manifest

## Related data release

- Title: Data supporting “Analytical choices reshape global forest drought-recovery inference”
- Reserved DOI: https://doi.org/10.5281/zenodo.22119617
- Expected version: 1.0.0
- Licence: CC BY 4.0 for author-generated deposited data/documentation
- Status: the DOI becomes active when the Zenodo record is published

The data release contains the global forest eligibility domain, corrected D1/D3/D6 event records, P1/P2 recovery and censoring fields, frozen validation/calibration summaries, three enrichment estimands, functional GPP/NPP contrasts, group evidence/status and Source Data for all final figures. Raw MODIS, ERA5-Land, SPEI, forest-structure and other upstream products are not redistributed.

## Code-to-data relationship

| Code stage | Zenodo folders / inputs | Main products |
|---|---|---|
| `02_harmonization` | upstream products (optional full reconstruction) | forest domain and monthly/static state |
| `03_event_detection` | `01_DOMAIN`, monthly state | `02_DROUGHT_EVENTS`, corrected R2 events |
| `04_recovery` | `02_DROUGHT_EVENTS` | `03_RECOVERY_P1_P2` |
| `05_models`, `06_validation` | events/recovery tables | `04_MODEL_VALIDATION` |
| `07_estimands`, `08_functional` | events, cells, validation | `05_ENRICHMENT`, `06_FUNCTIONAL_LEGACY`, `07_GROUP_EVIDENCE` |
| `09_figures` | `08_SOURCE_DATA` or archived renderer-input CSV/MAT files | final figures and Source Data workbooks |

## Upstream products

| Dataset | Product / asset | Variables used | Used period | Acquisition route | Redistributed? |
|---|---|---|---|---|---|
| MODIS Terra Vegetation Indices Collection 6.1 | MODIS/061/MOD13C1 | monthly kNDVI; standardized kNDVI anomaly | 2001–2024; anomaly baseline 2001–2020 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| MODIS Vegetation Continuous Fields Percent Tree Cover Collection 6.1 | MODIS/061/MOD44B | forest cover; valid years; eligibility | 2001–2020 used | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| MODIS annual land cover Collection 6.1 | MODIS/061/MCD12C1 | IGBP forest type | 2001–2020 used | Google Earth Engine export, archived locally, categorical mode to 0.5° | NO |
| MODIS burned area Collection 6.1 | MODIS/061/MCD64A1 | burned fraction and fire-overlap support | 2001–2024 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| MODIS annual GPP/NPP Collection 6.1 | MODIS/061/MOD17A3HGF | Gpp; Npp; GPP/NPP legacy contrasts | 2001–2024; eligible event years 2004–2018 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| ERA5-Land monthly aggregated | ECMWF/ERA5_LAND/MONTHLY_AGGR | temperature and precipitation | 2001–2024 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| ERA5-Land daily aggregated | ECMWF/ERA5_LAND/DAILY_AGGR | daily-derived VPD mean; 0–100 cm soil moisture | 2001–2024 | Google Earth Engine export, archived locally, exact 10×10 aggregation to 0.5° | NO |
| SPEIbase v2.11 | CSIC/SPEI/2_11 | SPEI-1, SPEI-3, SPEI-6; event severity, deficit and duration | 2000–2024; final events start 2001 | Google Earth Engine/local archived acquisition | NO |
| Global Forest Canopy Height 2005 | NASA/JPL/global_forest_canopy_height_2005 | canopy height | nominal 2005 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| Global biomass carbon density 2010 | NASA/ORNL/biomass_carbon_density/v1 | biomass carbon density | nominal 2010 | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| Global Human Modification v3 | TNC/HM/v3/300m_c | human modification | 2020 layer used | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| Intact Forest Landscapes | Official GeoPackage distribution; IFL_2020 layer | IFL 2020 cell fraction | 2020 layer used | Official GeoPackage files archived locally and rasterized by the frozen pipeline | NO |
| WorldClim monthly climate v1 | WORLDCLIM/V1/MONTHLY | broad climate-zone classification | static climatology | Google Earth Engine export, archived locally, derived categorical mode to 0.5° | NO |
| OpenLandMap soil baseline | OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02 \| OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02 \| OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01 | clay, sand and water content at 33 kPa summarized for the 100-cm baseline | static | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |
| MERIT DEM v1.0.3 | MERIT/DEM/v1_0_3 | elevation and derived slope | static | Google Earth Engine export, archived locally, aggregated to 0.5° | NO |

## Provenance boundary

Use the official product identifiers above to reacquire upstream data under provider terms. The repository does not contain raw MODIS, ERA5-Land or SPEI files. `01_acquisition` preserves available product-level definitions, but the raw-acquisition archive was batch-oriented and is not required when starting from the Zenodo derived release.
