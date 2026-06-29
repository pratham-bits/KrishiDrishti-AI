"""
crop_mapping/gee_scripts/02_sar_preprocessing.py
=================================================
SAR-first preprocessing pipeline for Kharif 2024.

Given that 5 of 6 epochs exceed 80% cloud cover over Nagarjunasagar,
SAR (Sentinel-1) is our PRIMARY signal. This script:

  1. Loads Sentinel-1 GRD for all 6 epochs
  2. Applies speckle filtering (median composite — simple but effective)
  3. Computes VV, VH, VH/VV ratio per epoch
  4. Computes SAR-derived Soil Moisture Index (SMI)
  5. For E5 only: fuses with Sentinel-2 optical (NDVI, EVI, NDWI)
  6. Exports a preview RGB composite to verify visually
  7. Exports the full feature stack as CSV (sampled at 500 random points)
     so you can inspect the data BEFORE running the full GT export

This script runs in ~5-10 minutes and gives you immediate output.
The full GT-sampled export (01_collect_features.py) takes 30+ minutes.

Usage:
    python crop_mapping/gee_scripts/02_sar_preprocessing.py \
        --project bah-pragyancoder \
        --config  config/kharif2024.yaml

Output:
    Google Drive/BAH2026_exports/sar_preview_kharif2024.csv  (~500 rows)
    Google Drive/BAH2026_exports/sar_rgb_E3.tif              (visual check)
"""

import ee
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config_loader import load_config
from shared.gee_helpers import init_gee, get_aoi
from shared.schema import EPOCH_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# STEP 1: SAR SPECKLE FILTERING
# ─────────────────────────────────────────────────────────────

def load_s1_epoch(aoi: ee.Geometry, start: str, end: str) -> ee.Image:
    """
    Load Sentinel-1 GRD for one epoch and apply speckle reduction.

    WHY SPECKLE MATTERS:
    SAR images have "salt and pepper" noise called speckle — random
    constructive/destructive interference of radar waves. A single
    SAR image looks grainy. Taking the MEDIAN of multiple images
    from the same epoch dramatically reduces speckle.

    We use median compositing (not Refined Lee filter) because:
    - We have 3-7 images per epoch → median is very effective
    - No additional library dependencies
    - GEE handles it server-side efficiently

    For the HACKATHON: median compositing is sufficient and defensible.
    For production: implement Refined Lee or Gamma-MAP filter.
    """
    col = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )

    n_images = col.size().getInfo()
    logger.info(f"    {start}: {n_images} SAR images → median composite")

    # Median composite — reduces speckle across overlapping passes
    median = col.select(["VV", "VH"]).median()
    return median


# ─────────────────────────────────────────────────────────────
# STEP 2: SAR FEATURE COMPUTATION
# ─────────────────────────────────────────────────────────────

def compute_sar_features(image: ee.Image, epoch_name: str) -> ee.Image:
    """
    Compute three SAR features per epoch:

    VV  (dB): Co-polarisation backscatter.
              Sensitive to surface roughness and soil moisture.
              Rice paddies: very low (-15 to -18 dB) when flooded.
              Dry fields: higher (-8 to -12 dB).

    VH  (dB): Cross-polarisation backscatter.
              Sensitive to vegetation VOLUME (random scattering).
              Increases as crop canopy develops through season.
              Good discriminator between short (rice) and tall (maize) crops.

    VH/VV ratio (linear, NOT dB):
              Crop structure index. Computed in linear scale because
              ratios of logarithms are not meaningful.
              High ratio → complex structure (maize, cotton with many leaves)
              Low ratio  → specular / flat surface (flooded paddy)

    SAR Soil Moisture Index (SMI):
              Derived from VV. Wetter soil = higher VV backscatter.
              SMI = (VV - VV_dry) / (VV_wet - VV_dry)
              Approximated here using clamp-normalisation:
              SMI = (VV + 25) / 25   clamped to [0, 1]
              VV_dry ≈ -25 dB (dry bare soil), VV_wet ≈ 0 dB (open water)
    """
    vv = image.select("VV").rename(f"vv_{epoch_name}")
    vh = image.select("VH").rename(f"vh_{epoch_name}")

    # VH/VV in LINEAR scale — critical: do NOT divide in dB
    vv_lin = ee.Image(10).pow(image.select("VV").divide(10))
    vh_lin = ee.Image(10).pow(image.select("VH").divide(10))
    vhvv   = vh_lin.divide(vv_lin).rename(f"vhvv_{epoch_name}")

    # SAR-derived Soil Moisture Index
    smi = (image.select("VV").add(25)).divide(25).clamp(0, 1).rename(f"smi_{epoch_name}")

    return vv.addBands([vh, vhvv, smi])


# ─────────────────────────────────────────────────────────────
# STEP 3: OPTICAL FEATURES (E5 ONLY — THE ONE CLEAR EPOCH)
# ─────────────────────────────────────────────────────────────

def compute_e5_optical(aoi: ee.Geometry, config: dict) -> ee.Image:
    """
    E5 (Aug 4-19) is the ONLY epoch below 77.2% cloud cover.
    August corresponds to peak vegetative stage for Rice and Maize
    in Kharif — this is actually the MOST INFORMATIVE single epoch
    for optical indices because canopy closure is maximum.

    We extract three indices:
    NDVI: standard vegetation index — highest values at peak biomass
    EVI:  corrected for atmospheric effects and soil background —
          better than NDVI in dense rice canopies where NDVI saturates
    NDWI: water content index — flooded rice paddies show 0.2-0.5,
          rainfed maize shows near-zero, cotton shows negative values

    Note: We label these with suffix _E5_opt to distinguish from
    SAR-proxy optical features used in other epochs.
    """
    def mask_s2_clouds(img):
        scl = img.select("SCL")
        mask = scl.neq(8).And(scl.neq(9)).And(scl.neq(10))
        return img.updateMask(mask)

    e5_epoch = [e for e in config["epochs"] if e["name"] == "E5"][0]

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(e5_epoch["start"], e5_epoch["end"])
        .map(mask_s2_clouds)
    )

    n = s2.size().getInfo()
    logger.info(f"    E5 optical: {n} cloud-masked Sentinel-2 images")

    median = s2.median()
    ndvi = median.normalizedDifference(["B8", "B4"]).rename("ndvi_E5_opt")
    evi  = median.expression(
        "2.5*((NIR-RED)/(NIR+6.0*RED-7.5*BLUE+1.0))",
        {"NIR": median.select("B8"),
         "RED": median.select("B4"),
         "BLUE": median.select("B2")}
    ).rename("evi_E5_opt")
    ndwi = median.normalizedDifference(["B3", "B8"]).rename("ndwi_E5_opt")

    return ndvi.addBands([evi, ndwi])


# ─────────────────────────────────────────────────────────────
# STEP 4: PHENOLOGICAL FEATURES FROM SAR TIME SERIES
# ─────────────────────────────────────────────────────────────

def compute_sar_phenology(stacked: ee.Image) -> ee.Image:
    """
    Derive crop phenology metrics from the SAR time series.

    When optical NDVI is unavailable, SAR VH trajectory captures
    the crop growth cycle:
    - VH is low at sowing (bare soil)
    - VH increases as canopy develops (volume scattering increases)
    - VH peaks at maximum biomass
    - VH decreases at maturity/senescence

    This is the SAR analogue of the optical phenological features.

    vh_peak:   Maximum VH across all epochs — proxy for peak biomass
    vh_sos:    VH at E1 — start-of-season SAR backscatter
    vh_range:  VH_max - VH_min — range of temporal variation
               High range = active crop growth (rice/maize)
               Low range  = slow-growing or perennial (sugarcane, orchard)
    vv_slope:  VV at E4 minus VV at E1 — captures flooding signal for rice
               Rice shows sharp VV decrease at transplanting (E1→E2)
    """
    vh_names = [f"vh_{n}" for n in EPOCH_NAMES]
    vv_names = [f"vv_{n}" for n in EPOCH_NAMES]

    vh_stack = stacked.select(vh_names)
    vv_stack = stacked.select(vv_names)

    vh_peak  = vh_stack.reduce(ee.Reducer.max()).rename("vh_peak")
    vh_min   = vh_stack.reduce(ee.Reducer.min()).rename("vh_min")
    vh_sos   = stacked.select(f"vh_{EPOCH_NAMES[0]}").rename("vh_sos")
    vh_range = vh_peak.subtract(vh_min).rename("vh_range")

    # VV slope E1→E4: captures rice transplanting flood signal
    # Sharp drop in VV between E1 (pre-transplant) and E2/E3 (flooded paddy)
    vv_slope = (stacked.select(f"vv_{EPOCH_NAMES[3]}")
                .subtract(stacked.select(f"vv_{EPOCH_NAMES[0]}"))
                .rename("vv_slope_E1E4"))

    return stacked.addBands([vh_peak, vh_sos, vh_range, vv_slope])


# ─────────────────────────────────────────────────────────────
# STEP 5: QUICK PREVIEW EXPORT (500 random points)
# ─────────────────────────────────────────────────────────────

def export_preview_csv(stacked: ee.Image, aoi: ee.Geometry):
    """
    Sample 500 random points over the AOI to inspect feature distributions.
    This is NOT the training export — it's a quick sanity check.
    Takes ~5 minutes vs 30+ minutes for full GT export.

    After downloading, check:
    - vv_E1 should be around -10 to -15 dB over agricultural areas
    - vhvv_E3 should be higher than vhvv_E1 (canopy has developed)
    - smi values should be between 0 and 1
    - ndvi_E5_opt should show clear separation (rice ~0.7, cotton ~0.5)
    """
    random_points = ee.FeatureCollection.randomPoints(
        region=aoi,
        points=500,
        seed=42
    )
    sampled = stacked.sampleRegions(
        collection=random_points,
        scale=30,
        tileScale=4,
        geometries=True
    )
    name = f"sar_preview_{datetime.now().strftime('%Y%m%d_%H%M')}"
    task = ee.batch.Export.table.toDrive(
        collection=sampled,
        description=name,
        folder="BAH2026_exports",
        fileNamePrefix=name,
        fileFormat="CSV"
    )
    task.start()
    logger.info(f"Preview CSV export started | ID: {task.id}")
    return task


def export_sar_rgb_visual(aoi: ee.Geometry, config: dict):
    """
    Export a false-colour SAR composite as a GeoTIFF for visual inspection.

    RGB assignment:
      R = VV at E3  (mid-season — captures crop development)
      G = VH at E3  (volume scattering — vegetation density)
      B = VH/VV at E3 (crop structure index)

    How to interpret:
      Bright RED   → high VV, low VH → bare/dry soil or sparse crop
      Bright GREEN → high VH → dense vegetation (maize, cotton)
      DARK overall → flooded surface (rice paddy absorbs radar)
      YELLOW/ORANGE → mixed vegetation + soil
    """
    e3 = [e for e in config["epochs"] if e["name"] == "E3"][0]
    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(e3["start"], e3["end"])
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .median()
    )

    vv_lin = ee.Image(10).pow(s1.select("VV").divide(10))
    vh_lin = ee.Image(10).pow(s1.select("VH").divide(10))
    ratio  = vh_lin.divide(vv_lin)

    rgb = (s1.select("VV")         # R: VV dB
             .addBands(s1.select("VH"))       # G: VH dB
             .addBands(ratio))               # B: ratio linear

    name = "sar_rgb_E3_nagarjunasagar"
    task = ee.batch.Export.image.toDrive(
        image=rgb.clip(aoi),
        description=name,
        folder="BAH2026_exports",
        fileNamePrefix=name,
        scale=30,
        region=aoi,
        maxPixels=1e9,
        fileFormat="GeoTIFF"
    )
    task.start()
    logger.info(f"SAR RGB visual export started | ID: {task.id}")
    return task


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--config",  default="config/kharif2024.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    init_gee(args.project)
    aoi = get_aoi(config)
    logger.info("AOI: Nagarjunasagar (3 districts, 33,999 km²)")
    logger.info("Strategy: SAR-primary | 5/6 epochs cloud-blocked | E5 optical only")

    # ── Build SAR feature stack across all 6 epochs ──────────
    logger.info("\nStep 1/4: Building SAR composites per epoch...")
    stacked = None
    for epoch in config["epochs"]:
        s1_median = load_s1_epoch(aoi, epoch["start"], epoch["end"])
        features  = compute_sar_features(s1_median, epoch["name"])
        stacked   = features if stacked is None else stacked.addBands(features)

    logger.info("SAR stack complete: 4 features × 6 epochs = 24 bands")

    # ── Add E5 optical (only usable optical epoch) ───────────
    logger.info("\nStep 2/4: Adding E5 optical features (NDVI, EVI, NDWI)...")
    e5_optical = compute_e5_optical(aoi, config)
    stacked    = stacked.addBands(e5_optical)
    logger.info("E5 optical added: +3 bands (ndvi_E5_opt, evi_E5_opt, ndwi_E5_opt)")

    # ── Add SAR phenological features ────────────────────────
    logger.info("\nStep 3/4: Computing SAR phenological features...")
    stacked = compute_sar_phenology(stacked)
    logger.info("SAR phenology added: vh_peak, vh_sos, vh_range, vv_slope_E1E4")

    total_bands = stacked.bandNames().size().getInfo()
    logger.info(f"\nFinal feature stack: {total_bands} bands total")
    logger.info(f"  • SAR features:      24  (vv/vh/vhvv/smi × 6 epochs)")
    logger.info(f"  • E5 optical:         3  (ndvi/evi/ndwi — E5 only)")
    logger.info(f"  • SAR phenology:      4  (vh_peak/sos/range, vv_slope)")

    # ── Export ───────────────────────────────────────────────
    logger.info("\nStep 4/4: Launching export tasks...")
    t1 = export_preview_csv(stacked, aoi)
    t2 = export_sar_rgb_visual(aoi, config)

    logger.info("\n" + "=" * 58)
    logger.info("TWO export tasks running in GEE:")
    logger.info(f"  1. SAR preview CSV  | task: {t1.id}")
    logger.info(f"  2. SAR RGB GeoTIFF  | task: {t2.id}")
    logger.info("Monitor: https://code.earthengine.google.com/tasks")
    logger.info("")
    logger.info("Expected times:")
    logger.info("  CSV preview:  ~5 minutes")
    logger.info("  RGB GeoTIFF:  ~10-15 minutes")
    logger.info("")
    logger.info("When done, download to data/raw/ and open the GeoTIFF")
    logger.info("in QGIS or geemap to visually verify the SAR composite.")
    logger.info("=" * 58)


if __name__ == "__main__":
    main()