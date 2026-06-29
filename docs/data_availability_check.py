"""
data_availability_check.py
===========================
Run this FIRST after GEE authentication.
Checks all 4 data sources over our exact AOI and Kharif 2024 date range.
Prints a full data availability report with image counts, band lists,
cloud statistics, and resolution details.

Usage:
    python docs/data_availability_check.py --project YOUR_GEE_PROJECT_ID

Expected runtime: ~2-3 minutes (GEE server-side computation)
"""

import ee
import argparse
import json
from datetime import datetime


# ── ANSI colours for terminal output ─────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{msg}{RESET}\n{'─'*55}")


def get_aoi() -> ee.Geometry:
    """Nagarjunasagar command area from FAO GAUL Level-2."""
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    districts = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "India"),
            ee.Filter.inList("ADM2_NAME",
                ["Nalgonda", "Guntur", "Krishna", "Suryapet"])
        )
    )
    return districts.geometry().dissolve()


# ============================================================
# CHECK 1: SENTINEL-2 SR
# ============================================================
def check_sentinel2(aoi: ee.Geometry):
    header("1. SENTINEL-2 SR (COPERNICUS/S2_SR_HARMONIZED)")

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi)
           .filterDate("2024-06-01", "2024-11-30"))

    count = col.size().getInfo()
    print(f"  Total images (Kharif 2024): {count}")

    if count == 0:
        fail("No images found — check AOI or GEE access")
        return

    ok(f"{count} images available")

    # Get one sample image to inspect bands and metadata
    sample = col.first()
    bands  = sample.bandNames().getInfo()
    print(f"  Available bands ({len(bands)} total):")
    key_bands = {
        "B2": "Blue (490nm)",
        "B3": "Green (560nm)",
        "B4": "Red (665nm)",
        "B8": "NIR (842nm)  ← NDVI numerator",
        "B11":"SWIR-1 (1610nm)",
        "B12":"SWIR-2 (2190nm)",
        "SCL":"Scene Classification Layer ← cloud mask"
    }
    for b, desc in key_bands.items():
        if b in bands:
            ok(f"  {b}: {desc}")
        else:
            fail(f"  {b}: MISSING — {desc}")

    # Cloud statistics per epoch
    print("\n  Cloud fraction per 16-day epoch:")
    epochs = [
        ("E1", "2024-06-01", "2024-06-16"),
        ("E2", "2024-06-17", "2024-07-02"),
        ("E3", "2024-07-03", "2024-07-18"),
        ("E4", "2024-07-19", "2024-08-03"),
        ("E5", "2024-08-04", "2024-08-19"),
        ("E6", "2024-08-20", "2024-09-04"),
    ]
    for name, start, end in epochs:
        epoch_col = col.filterDate(start, end)
        n = epoch_col.size().getInfo()

        if n == 0:
            warn(f"  {name} ({start}→{end}): 0 images → SAR fallback will trigger")
            continue

        # Compute mean cloud fraction using SCL
        def add_cloud_frac(img):
            scl = img.select("SCL")
            cloudy = scl.eq(8).Or(scl.eq(9)).Or(scl.eq(10))
            frac = cloudy.rename("cloud_frac")
            return img.addBands(frac)

        cloud_mean = (epoch_col
                      .map(add_cloud_frac)
                      .select("cloud_frac")
                      .mean()
                      .reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e8)
                      .get("cloud_frac")
                      .getInfo())

        if cloud_mean is None:
            warn(f"  {name}: could not compute cloud fraction")
            continue

        pct = round(cloud_mean * 100, 1)
        flag = " ← SAR FALLBACK" if cloud_mean > 0.80 else ""
        bar = "█" * int(pct / 5)
        if cloud_mean > 0.80:
            warn(f"  {name}: {pct:5.1f}% cloudy [{bar:<20}]{flag}")
        elif cloud_mean > 0.40:
            print(f"  {name}: {pct:5.1f}% cloudy [{bar:<20}] ← moderate cloud")
        else:
            ok(f"  {name}: {pct:5.1f}% cloudy [{bar:<20}] ← clear")

    print(f"\n  Resolution: 10m (B2/B3/B4/B8), 20m (B11/B12), 60m (B1/B9)")
    print(f"  Revisit: ~5 days (combined Sentinel-2A + 2B)")
    print(f"  Surface reflectance: yes (atmospherically corrected)")


# ============================================================
# CHECK 2: SENTINEL-1 GRD (SAR)
# ============================================================
def check_sentinel1(aoi: ee.Geometry):
    header("2. SENTINEL-1 GRD (COPERNICUS/S1_GRD)")

    col = (ee.ImageCollection("COPERNICUS/S1_GRD")
           .filterBounds(aoi)
           .filterDate("2024-06-01", "2024-11-30")
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
           .filter(ee.Filter.eq("instrumentMode", "IW")))

    count = col.size().getInfo()
    print(f"  Total IW VV+VH images (Kharif 2024): {count}")

    if count == 0:
        fail("No images found")
        return
    ok(f"{count} SAR images available — cloud-independent data confirmed")

    sample = col.first()
    bands  = sample.bandNames().getInfo()
    print(f"  Bands: {bands}")

    # Check per-epoch availability
    print("\n  SAR image count per 16-day epoch:")
    epochs = [
        ("E1","2024-06-01","2024-06-16"),
        ("E2","2024-06-17","2024-07-02"),
        ("E3","2024-07-03","2024-07-18"),
        ("E4","2024-07-19","2024-08-03"),
        ("E5","2024-08-04","2024-08-19"),
        ("E6","2024-08-20","2024-09-04"),
    ]
    for name, start, end in epochs:
        n = col.filterDate(start, end).size().getInfo()
        bar = "█" * min(n, 20)
        if n > 0:
            ok(f"  {name}: {n} images [{bar}]")
        else:
            fail(f"  {name}: 0 images")

    # Sample VV/VH stats over AOI for reference
    sample_img = col.first()
    stats = sample_img.select(["VV","VH"]).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=100,
        maxPixels=1e8
    ).getInfo()
    print(f"\n  Sample backscatter (first image, mean over AOI):")
    print(f"  VV: {round(stats.get('VV', 0), 2)} dB  |  VH: {round(stats.get('VH', 0), 2)} dB")
    print(f"  Expected for rice paddy: VV ~ -15 to -18 dB at flooding")
    print(f"\n  Resolution: 10m (IW mode)")
    print(f"  Revisit: ~6 days")
    print(f"  Unit: dB (log scale, typically -25 to 0)")
    print(f"  Key insight: Rice VV drops 3-5 dB at transplanting — our primary signal")


# ============================================================
# CHECK 3: CHIRPS DAILY RAINFALL
# ============================================================
def check_chirps(aoi: ee.Geometry):
    header("3. CHIRPS DAILY RAINFALL (UCSB-CHG/CHIRPS/DAILY)")

    col = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
           .filterBounds(aoi)
           .filterDate("2024-06-01", "2024-11-30"))

    count = col.size().getInfo()
    print(f"  Daily images (Kharif 2024): {count}")

    if count == 0:
        fail("No CHIRPS data found")
        return
    ok(f"{count} daily rainfall images (expected ~184 days)")

    # Compute seasonal total and monthly breakdown
    sample = col.first()
    bands  = sample.bandNames().getInfo()
    print(f"  Band: {bands}  (precipitation in mm/day)")

    # Seasonal total rainfall over AOI
    seasonal_total = col.sum().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=5000,
        maxPixels=1e8
    ).getInfo()
    total_mm = round(seasonal_total.get("precipitation", 0), 1)
    print(f"\n  Seasonal total rainfall over AOI: {total_mm} mm")
    print(f"  Expected for Telangana Kharif: 600–900 mm")

    if total_mm < 300:
        warn("  Low rainfall — check if data is complete")
    else:
        ok(f"  Rainfall within expected range")

    print(f"\n  Resolution: ~5.5 km (0.05°)")
    print(f"  Coverage: global land")
    print(f"  Latency: ~2 days")
    print(f"  Note: We aggregate to 8-day sums for FAO-56 water balance")


# ============================================================
# CHECK 4: ERA5-LAND (Reference ET₀)
# ============================================================
def check_era5(aoi: ee.Geometry):
    header("4. ERA5-LAND (ECMWF/ERA5_LAND/DAILY_AGGR)")

    col = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
           .filterBounds(aoi)
           .filterDate("2024-06-01", "2024-11-30"))

    count = col.size().getInfo()
    print(f"  Daily images (Kharif 2024): {count}")

    if count == 0:
        fail("No ERA5 data — this is unexpected")
        return
    ok(f"{count} daily ERA5 images")

    sample = col.first()
    all_bands = sample.bandNames().getInfo()

    # The bands we actually need for ET₀
    needed = {
        "temperature_2m":             "Air temp at 2m (K) ← for ET₀",
        "dewpoint_temperature_2m":    "Dewpoint temp (K)  ← humidity",
        "u_component_of_wind_10m":    "Wind U component   ← wind speed",
        "v_component_of_wind_10m":    "Wind V component   ← wind speed",
        "surface_solar_radiation_downwards_sum": "Solar radiation ← ET₀"
    }
    print(f"\n  Bands needed for FAO-56 Penman-Monteith ET₀:")
    for band, desc in needed.items():
        if band in all_bands:
            ok(f"  {band[:35]:<35}: {desc}")
        else:
            warn(f"  {band[:35]:<35}: not found — check band name in GEE catalog")

    # Sample temperature to verify data
    temp_stats = col.first().select("temperature_2m").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=10000,
        maxPixels=1e8
    ).getInfo()
    temp_k = temp_stats.get("temperature_2m", 0)
    temp_c = round(temp_k - 273.15, 1) if temp_k else None
    if temp_c:
        print(f"\n  Sample temp (first day, mean over AOI): {temp_c}°C")
        print(f"  Expected for Telangana June: 28–38°C")
        if 25 <= temp_c <= 45:
            ok("  Temperature in expected range")
        else:
            warn(f"  Temperature {temp_c}°C outside expected range — verify units")

    print(f"\n  Resolution: ~9 km (0.1°)")
    print(f"  Note: We will compute ET₀ from these met variables using FAO-56")
    print(f"        ET₀ = f(temp, humidity, wind, solar radiation)")


# ============================================================
# CHECK 5: AOI BOUNDARY
# ============================================================
def check_aoi():
    header("5. AOI BOUNDARY (FAO/GAUL/2015/level2)")

    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    districts = gaul.filter(
        ee.Filter.And(
            ee.Filter.eq("ADM0_NAME", "India"),
            ee.Filter.inList("ADM2_NAME",
                ["Nalgonda", "Guntur", "Krishna", "Suryapet"])
        )
    )
    count = districts.size().getInfo()
    print(f"  Districts found: {count}")

    if count == 0:
        fail("No districts found — district names may have changed in GAUL")
        warn("  → Try: Nalgonda, Guntur, Krishna, Suryapet")
        return

    names = districts.aggregate_array("ADM2_NAME").getInfo()
    for n in names:
        ok(f"  {n}")

    aoi = districts.geometry().dissolve()
    area_sqkm = aoi.area(maxError=100).divide(1e6).getInfo()
    print(f"\n  Total AOI area: {round(area_sqkm, 0):,.0f} km²")
    print(f"  Expected: ~10,000–25,000 km² for 4 districts")

    if area_sqkm < 1000:
        warn("  Area seems small — verify district names are correct")
    else:
        ok(f"  AOI area looks reasonable")


# ============================================================
# SUMMARY REPORT
# ============================================================
def print_summary():
    header("SUMMARY — DATA READINESS FOR PS6 PIPELINE")
    print("""
  Dataset          Source              Resolution  Use in pipeline
  ─────────────────────────────────────────────────────────────────
  Sentinel-2 SR    COPERNICUS/S2_SR    10m         NDVI, EVI, NDWI features
  Sentinel-1 GRD   COPERNICUS/S1_GRD  10m         VV, VH, SAR fallback
  CHIRPS Daily     UCSB-CHG/CHIRPS    5.5km        8-day rainfall for deficit
  ERA5-Land        ECMWF/ERA5_LAND    9km          ET₀ for water balance
  FAO GAUL L2      FAO/GAUL/2015      Vector       AOI boundary polygon
  ─────────────────────────────────────────────────────────────────

  Next step: Run crop_mapping/gee_scripts/01_collect_features.py
    """)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Verify GEE data availability for KrishiDrishti AI"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Your GEE Cloud Project ID"
    )
    args = parser.parse_args()

    print(f"\n{BOLD}KrishiDrishti AI — GEE Data Availability Check{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project:   {args.project}")

    # Initialise GEE
    try:
        ee.Initialize(project=args.project)
        ok("GEE initialized")
    except Exception as e:
        fail(f"GEE init failed: {e}")
        return

    # Get AOI first — needed for all checks
    aoi = get_aoi()

    # Run all checks
    check_aoi()
    check_sentinel2(aoi)
    check_sentinel1(aoi)
    check_chirps(aoi)
    check_era5(aoi)
    print_summary()


if __name__ == "__main__":
    main()
