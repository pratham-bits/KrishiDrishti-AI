# Ground Truth Points Guide
# BAH 2026 PS6 — How to create training labels for the crop classifier

# ============================================================
# THE PROBLEM
# ============================================================
# Our Random Forest needs labeled training samples:
# pixels where we KNOW the crop type (Rice=0, Maize=1, Cotton=2).
# This is called ground truth. Without it, we cannot train.

# ============================================================
# OPTION A: USE PUBLISHED CROP SURVEY DATA (RECOMMENDED)
# ============================================================
# Telangana's Department of Agriculture publishes Kharif crop
# sowing reports with village-level crop area data.
#
# Source: https://agri.telangana.gov.in/cropstatistics.do
# Also:   https://aps.dac.gov.in (national crop statistics)
#
# These give you district + mandal-level crop distributions.
# Use them to guide WHERE to place your GT points.

# ============================================================
# OPTION B: VISUAL INTERPRETATION IN GEE CODE EDITOR
# ============================================================
# This is what we will do for the hackathon — it's fast and
# doesn't require field visits.
#
# Steps:
# 1. Open: https://code.earthengine.google.com
# 2. Load a Sentinel-2 false-colour composite:

# Paste this in the GEE Code Editor:
"""
var aoi = ee.FeatureCollection("FAO/GAUL/2015/level2")
  .filter(ee.Filter.inList("ADM2_NAME",
    ["Nalgonda","Guntur","Krishna","Suryapet"]));

var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(aoi)
  .filterDate("2024-08-01","2024-08-20")
  .median();

// False colour: NIR=Red, Red=Green, Green=Blue
// Rice appears BRIGHT RED (high NIR, flooded)
// Cotton appears PINK/MAGENTA
// Maize appears ORANGE-RED
Map.addLayer(s2, {bands:["B8","B4","B3"], min:500, max:4000}, "S2 False Colour Aug");
Map.centerObject(aoi, 9);
Map.addLayer(aoi, {color:"yellow"}, "AOI");
"""

# 3. Visually identify areas with confident crop type
#    - Rice:   bright red, often in regular grid patterns near canals
#    - Maize:  orange-red, more irregular patches
#    - Cotton: pink/magenta, on elevated areas away from water bodies
#
# 4. Use the "Draw a point" tool (toolbar) to place ~50 points per class
#    - Minimum: 150 points total (50 per crop)
#    - Better:  300 points (100 per crop)
#    - Target:  500+ points for robust validation
#
# 5. In the Geometry Imports panel:
#    - Name the layer "gt_points"
#    - Set geometry type to "FeatureCollection"
#    - Add property: "crop_label" (0=Rice, 1=Maize, 2=Cotton)

# ============================================================
# OPTION C: USE EXISTING OPEN DATASETS (FASTEST FOR DEMO)
# ============================================================
# ICAR and ICRISAT have published crop field boundary datasets
# for parts of AP/Telangana. Check:
#   - https://icrisat.org/                  (VDSA micro-level data)
#   - BHUVAN portal: https://bhuvan.nrsc.gov.in
#   - GEOGLAM crop monitor reports

# ============================================================
# UPLOADING GT POINTS TO GEE ASSETS
# ============================================================
# Once you have a CSV with columns: longitude, latitude, crop_label

# Option 1: Upload via GEE Code Editor
# Assets tab → New → Table upload → select your CSV
# Set the asset ID to: users/YOUR_USERNAME/nagarjunasagar_gt_points
# Wait ~5 minutes for ingestion

# Option 2: Upload via Python
"""
import ee
import geemap

# Load your CSV
gdf = gpd.read_file("data/raw/ground_truth_points.csv")
gdf = gdf.rename(columns={"lon":"longitude","lat":"latitude"})

# Upload to GEE
geemap.geopandas_to_ee(gdf).getInfo()
# Then export to asset via ee.batch.Export.table.toAsset()
"""

# ============================================================
# MINIMUM VIABLE GT FOR THE HACKATHON
# ============================================================
# If you're truly stuck getting GT points, here is the fallback:
#
# Use VCI-based PSEUDO-LABELS:
# - Pixels with NDVI_peak > 0.7 AND NDWI_E3 > 0.15 → Rice (0)
# - Pixels with NDVI_peak 0.5-0.7 AND near-zero NDWI → Maize (1)
# - Pixels with NDVI_peak 0.4-0.6 AND dryland location → Cotton (2)
#
# This is NOT as accurate as real GT but is sufficient for a
# proof-of-concept demo at the hackathon.
# See: crop_mapping/features/pseudolabels.py (to be created)
