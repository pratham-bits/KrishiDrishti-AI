"""
docs/verify_gee.py
==================
Run this after earthengine authenticate to confirm everything works.

Usage:
    python docs/verify_gee.py --project YOUR_PROJECT_ID

Example:
    python docs/verify_gee.py --project ee-pratham123
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        required=True,
        help="Your GEE Cloud Project ID, e.g. ee-pratham123"
    )
    args = parser.parse_args()

    # ── Step 1: Check import ──────────────────────────────────
    try:
        import ee
        print(f"✓ earthengine-api imported | version: {ee.__version__}")
    except ImportError:
        print("✗ earthengine-api not installed")
        print("  Fix: pip install earthengine-api")
        sys.exit(1)

    # ── Step 2: Initialize ────────────────────────────────────
    try:
        ee.Initialize(project=args.project)
        print(f"✓ GEE initialized | project: {args.project}")
    except Exception as e:
        print(f"✗ GEE initialization failed: {e}")
        print("  Possible fixes:")
        print("  1. Run:  earthengine authenticate  (in your terminal)")
        print("  2. Check your Project ID at console.cloud.google.com")
        print("  3. Make sure Earth Engine API is enabled for that project")
        sys.exit(1)

    # ── Step 3: Test Sentinel-2 data access ──────────────────
    print("\nChecking data access over Nagarjunasagar...")
    try:
        aoi = ee.Geometry.Point([79.8, 16.5])
        count = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate("2024-06-01", "2024-11-30")
            .size()
            .getInfo()
        )
        print(f"✓ Sentinel-2 images found (Kharif 2024): {count}")
        if count == 0:
            print("  ⚠ Zero images — AOI or date may be wrong, but auth is working")
        else:
            print("  → Data confirmed. You are ready to run the pipeline.")
    except Exception as e:
        print(f"✗ Data query failed: {e}")
        sys.exit(1)

    # ── Step 4: Test Sentinel-1 ───────────────────────────────
    try:
        s1_count = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi)
            .filterDate("2024-06-01", "2024-11-30")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .size()
            .getInfo()
        )
        print(f"✓ Sentinel-1 SAR images found: {s1_count}")
    except Exception as e:
        print(f"✗ Sentinel-1 query failed: {e}")

    print("\n─────────────────────────────────────────")
    print("All checks passed. Next step:")
    print("  python docs/data_availability_check.py --project", args.project)
    print("─────────────────────────────────────────")


if __name__ == "__main__":
    main()