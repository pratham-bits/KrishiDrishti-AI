"""
shared/gee_helpers.py
=====================
Reusable GEE utility functions used across crop_mapping and stress_detection.
Import pattern:
    from shared.gee_helpers import get_aoi, mask_s2_clouds, preprocess_sar
"""

import ee
import logging

logger = logging.getLogger(__name__)


def init_gee(project: str = None):
    """
    Initialise GEE. Call once at the top of any script that uses GEE.
    Args:
        project: GEE Cloud Project ID (e.g. 'ee-yourname').
                 If None, uses the default authenticated project.
    """
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        logger.info("GEE initialised successfully.")
    except Exception as e:
        logger.error(f"GEE init failed: {e}")
        raise


def get_aoi(config: dict) -> ee.Geometry:
    """
    Returns the Nagarjunasagar canal command area geometry
    by filtering FAO/GAUL Level-2 district boundaries.
    """
    gaul = ee.FeatureCollection(config["aoi"]["gee_source"])
    districts = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "India"),
            ee.Filter.inList("ADM2_NAME", config["aoi"]["districts"])
        )
    )
    return districts.geometry().dissolve()


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Mask clouds in Sentinel-2 SR using the Scene Classification Layer (SCL).
    SCL values masked: 8 (cloud medium), 9 (cloud high), 10 (cirrus).
    Also adds a 'cloud_flag' band (1=cloud, 0=clear) for fallback detection.
    """
    scl = image.select("SCL")
    cloud_mask = scl.neq(8).And(scl.neq(9)).And(scl.neq(10))
    cloud_flag = cloud_mask.Not().rename("cloud_flag")
    return image.updateMask(cloud_mask).addBands(cloud_flag)


def compute_optical_indices(image: ee.Image) -> ee.Image:
    """Compute NDVI, EVI, NDWI from Sentinel-2 SR bands."""
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("ndvi")
    evi = image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1))",
        {"NIR": image.select("B8"),
         "RED": image.select("B4"),
         "BLUE": image.select("B2")}
    ).rename("evi")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("ndwi")
    return image.addBands([ndvi, evi, ndwi])


def preprocess_sar(image: ee.Image) -> ee.Image:
    """
    Extract VV, VH from Sentinel-1 GRD and compute linear VH/VV ratio.
    VV and VH remain in dB (log scale). Ratio is in linear scale [0,1].
    """
    vv = image.select("VV").rename("vv")
    vh = image.select("VH").rename("vh")
    vv_lin = ee.Image(10).pow(image.select("VV").divide(10))
    vh_lin = ee.Image(10).pow(image.select("VH").divide(10))
    ratio = vh_lin.divide(vv_lin).rename("vhvv_ratio")
    return image.addBands([vv, vh, ratio])


def get_s2_collection(aoi: ee.Geometry, start: str, end: str) -> ee.ImageCollection:
    """Return cloud-masked, index-computed Sentinel-2 SR collection for an epoch."""
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .map(mask_s2_clouds)
        .map(compute_optical_indices)
    )


def get_s1_collection(aoi: ee.Geometry, start: str, end: str) -> ee.ImageCollection:
    """Return preprocessed Sentinel-1 GRD IW collection for an epoch."""
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .map(preprocess_sar)
    )


def get_cloud_fraction(s2_collection: ee.ImageCollection) -> ee.Image:
    """Returns a single-band image with the mean cloud fraction for an epoch."""
    return s2_collection.select("cloud_flag").mean()


def is_sar_fallback_epoch(cloud_frac_image: ee.Image,
                           aoi: ee.Geometry,
                           threshold: float = 0.80) -> bool:
    """
    Check if an epoch should use SAR-only features (cloud fraction > threshold).
    Returns a Python bool by pulling a single value from GEE.
    Use sparingly — each .getInfo() call is a GEE round-trip.
    """
    mean_cloud = cloud_frac_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=1000,
        maxPixels=1e8
    ).get("cloud_flag").getInfo()
    return mean_cloud is not None and mean_cloud > threshold
