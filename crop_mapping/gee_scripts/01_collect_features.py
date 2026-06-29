"""
crop_mapping/gee_scripts/01_collect_features.py
================================================
STEP 1 of 3 in crop_mapping module.

What this script does (in order):
  1. Loads Nagarjunasagar AOI from FAO GAUL boundaries
  2. For each of 6 epochs (16-day windows, Kharif 2024):
     a. Loads Sentinel-2 SR -> masks clouds -> computes NDVI/EVI/NDWI
     b. Loads Sentinel-1 GRD -> computes VV/VH/ratio
     c. Checks cloud fraction -> flags SAR-only epochs automatically
     d. Builds a median composite for the epoch
  3. Stacks all epoch composites into one multi-band image
  4. Computes phenological features from the NDVI time series
  5. Samples values at labeled ground truth points
  6. Exports as CSV to your Google Drive

Usage:
    python crop_mapping/gee_scripts/01_collect_features.py \
        --project YOUR_GEE_PROJECT_ID \
        --config  config/kharif2024.yaml \
        --gt_asset users/YOUR_USERNAME/nagarjunasagar_gt_points
"""

import ee
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.config_loader import load_config
from shared.gee_helpers import init_gee, get_aoi, get_s2_collection, get_s1_collection, get_cloud_fraction
from shared.schema import EPOCH_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def compute_optical_indices(image):
    """
    NDVI = (B8-B4)/(B8+B4)  range -1 to 1. Healthy veg: 0.5-0.9
    EVI  = 2.5*(NIR-RED)/(NIR+6*RED-7.5*BLUE+1)  better in dense canopies
    NDWI = (B3-B8)/(B3+B8)  flooded rice paddies: 0.2-0.5
    """
    ndvi = image.normalizedDifference(["B8","B4"]).rename("ndvi")
    evi  = image.expression(
        "2.5*((NIR-RED)/(NIR+6.0*RED-7.5*BLUE+1.0))",
        {"NIR":image.select("B8"),"RED":image.select("B4"),"BLUE":image.select("B2")}
    ).rename("evi")
    ndwi = image.normalizedDifference(["B3","B8"]).rename("ndwi")
    return image.addBands([ndvi, evi, ndwi])


def compute_sar_features(image):
    """
    VV and VH remain in dB. VH/VV ratio computed in LINEAR scale.
    Converting to linear: linear = 10^(dB/10)
    High ratio = complex structure (maize/cotton). Low = specular (flooded rice).
    """
    vv = image.select("VV").rename("vv")
    vh = image.select("VH").rename("vh")
    vv_lin = ee.Image(10).pow(image.select("VV").divide(10))
    vh_lin = ee.Image(10).pow(image.select("VH").divide(10))
    vhvv   = vh_lin.divide(vv_lin).rename("vhvv")
    return image.addBands([vv, vh, vhvv])


def build_epoch_composite(aoi, epoch, cloud_threshold):
    """
    Build one epoch composite with optical+SAR features.
    If cloud fraction > threshold, uses SAR-derived proxies for optical bands.
    Returns: (composite_image, sar_fallback_bool, cloud_frac_float)
    """
    name, start, end = epoch["name"], epoch["start"], epoch["end"]

    # -- Compute cloud fraction for this epoch
    s2_col    = get_s2_collection(aoi, start, end)
    cloud_val = (get_cloud_fraction(s2_col)
                 .reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e8)
                 .get("cloud_flag").getInfo())
    cloud_frac  = float(cloud_val) if cloud_val is not None else 1.0
    sar_fallback = cloud_frac > cloud_threshold

    status = "SAR-ONLY FALLBACK" if sar_fallback else "optical+SAR fusion"
    log_fn = logger.warning if sar_fallback else logger.info
    log_fn(f"  Epoch {name}: cloud={cloud_frac:.0%} -> {status}")

    # -- Sentinel-1 (always available, cloud-independent)
    s1_median = get_s1_collection(aoi, start, end).map(compute_sar_features).median()
    s1_epoch  = s1_median.select(["vv","vh","vhvv"]).rename(
        [f"vv_{name}", f"vh_{name}", f"vhvv_{name}"])

    if sar_fallback:
        # Substitute optical indices with SAR-derived proxies
        # so tensor shape stays identical to non-fallback epochs.
        # VV normalised to [0,1] from [-25,0] dB range as vegetation proxy.
        vv_norm     = s1_median.select("vv").add(25).divide(25).clamp(0,1)
        ndvi_proxy  = vv_norm.rename(f"ndvi_{name}")
        evi_proxy   = vv_norm.rename(f"evi_{name}")
        ndwi_proxy  = vv_norm.multiply(-1).add(1).rename(f"ndwi_{name}")
        optical_epoch = ndvi_proxy.addBands([evi_proxy, ndwi_proxy])
        cloud_band    = ee.Image(1.0).rename(f"cloud_frac_{name}")
    else:
        s2_median = s2_col.map(compute_optical_indices).median()
        optical_epoch = s2_median.select(["ndvi","evi","ndwi"]).rename(
            [f"ndvi_{name}", f"evi_{name}", f"ndwi_{name}"])
        cloud_band = ee.Image(cloud_frac).rename(f"cloud_frac_{name}")

    composite = optical_epoch.addBands(s1_epoch).addBands(cloud_band)
    return composite, sar_fallback, cloud_frac


def add_phenology_features(stacked):
    """
    ndvi_peak: max NDVI across epochs  -> peak biomass
    ndvi_sos:  NDVI at E1              -> start-of-season greenness
    ndvi_lgp:  count of epochs with NDVI>0.3 -> length of growing period
    These separate crops with similar single-date signatures but
    different temporal trajectories (e.g. Rice vs Cotton at E3).
    """
    ndvi_names = [f"ndvi_{n}" for n in EPOCH_NAMES]
    ndvi_stack = stacked.select(ndvi_names)
    ndvi_peak  = ndvi_stack.reduce(ee.Reducer.max()).rename("ndvi_peak")
    ndvi_sos   = stacked.select(f"ndvi_{EPOCH_NAMES[0]}").rename("ndvi_sos")
    ndvi_lgp   = ndvi_stack.gt(0.3).reduce(ee.Reducer.sum()).rename("ndvi_lgp")
    return stacked.addBands([ndvi_peak, ndvi_sos, ndvi_lgp])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project",  required=True, help="GEE Cloud Project ID")
    parser.add_argument("--config",   default="config/kharif2024.yaml")
    parser.add_argument("--gt_asset", required=True,
                        help="GEE asset path for ground truth points "
                             "e.g. users/YOUR_USERNAME/nagarjunasagar_gt_points")
    args = parser.parse_args()

    config = load_config(args.config)
    init_gee(args.project)
    aoi = get_aoi(config)
    logger.info("AOI loaded: Nagarjunasagar command area")

    cloud_threshold = config["cloud_fallback"]["threshold"]
    stacked = None
    fallback_log = {}

    logger.info(f"Building {len(config['epochs'])} epoch composites...")
    for epoch in config["epochs"]:
        composite, sar_fallback, cloud_frac = build_epoch_composite(
            aoi, epoch, cloud_threshold)
        fallback_log[epoch["name"]] = {"sar_fallback": sar_fallback, "cloud_frac": round(cloud_frac,3)}
        stacked = composite if stacked is None else stacked.addBands(composite)

    stacked = add_phenology_features(stacked)
    logger.info(f"Feature stack complete. Fallback summary: {fallback_log}")

    gt_points = ee.FeatureCollection(args.gt_asset)
    gt_count  = gt_points.size().getInfo()
    logger.info(f"Ground truth points loaded: {gt_count}")
    if gt_count == 0:
        logger.error("No GT points found. Check GEE asset path.")
        return

    sampled = stacked.sampleRegions(
        collection=gt_points,
        properties=["crop_label"],
        scale=30,
        tileScale=4,
        geometries=True
    )

    export_name = f"kharif2024_features_{datetime.now().strftime('%Y%m%d_%H%M')}"
    task = ee.batch.Export.table.toDrive(
        collection=sampled,
        description=export_name,
        folder="BAH2026_exports",
        fileNamePrefix=export_name,
        fileFormat="CSV"
    )
    task.start()
    logger.info("=" * 55)
    logger.info(f"Export task started | ID: {task.id}")
    logger.info("Monitor: https://code.earthengine.google.com/tasks")
    logger.info(f"Output: Google Drive/BAH2026_exports/{export_name}.csv")
    logger.info("Download to data/raw/ when complete.")
    logger.info("Next: python crop_mapping/gee_scripts/02_preprocess_csv.py")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
