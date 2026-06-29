"""
Crop Water Balance Processor — FAO-56 Method
Computes 8-day ETc, water deficit, and irrigation advisory per pixel/field.

Schema for output meteorological tracking table:
    See DATA_SCHEMA below for exact column definitions.
"""

import pandas as pd
import numpy as np
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Kc VALUES BY CROP AND GROWTH STAGE (FAO-56 Table 12) ───
# (Kc_ini, Kc_mid, Kc_end)
KC_TABLE = {
    "Rice":   {"Sowing": 1.05, "Vegetative": 1.20, "Reproductive": 1.20, "Maturity": 0.90},
    "Maize":  {"Sowing": 0.40, "Vegetative": 1.15, "Reproductive": 1.20, "Maturity": 0.60},
    "Cotton": {"Sowing": 0.45, "Vegetative": 0.95, "Reproductive": 1.15, "Maturity": 0.70},
}

# ─── PHENOLOGICAL STAGE CALENDAR for Kharif 2024 ───
# (start_doy, end_doy, stage_name)
STAGE_CALENDAR = {
    "Rice": [
        (152, 167, "Sowing"),        # June 1–16
        (168, 213, "Vegetative"),    # June 17 – Aug 1
        (214, 244, "Reproductive"),  # Aug 2 – Sep 1
        (245, 305, "Maturity"),      # Sep 2 – Nov 1
    ],
    "Maize": [
        (152, 167, "Sowing"),
        (168, 198, "Vegetative"),
        (199, 228, "Reproductive"),
        (229, 275, "Maturity"),
    ],
    "Cotton": [
        (152, 182, "Sowing"),
        (183, 228, "Vegetative"),
        (229, 274, "Reproductive"),
        (275, 335, "Maturity"),
    ],
}


def get_growth_stage(doy: int, crop: str) -> str:
    """Return phenological stage name for a given day-of-year and crop."""
    for start, end, stage in STAGE_CALENDAR.get(crop, []):
        if start <= doy <= end:
            return stage
    return "Maturity"


def compute_water_balance(
    et0_series: pd.Series,
    rainfall_series: pd.Series,
    crop: str,
    dates: pd.DatetimeIndex
) -> pd.DataFrame:
    """
    FAO-56 water balance for a pixel/field over the season.
    
    Args:
        et0_series:     8-day reference ET (mm) from ERA5
        rainfall_series: 8-day rainfall (mm) from CHIRPS
        crop:           Crop name (Rice / Maize / Cotton)
        dates:          DatetimeIndex for each 8-day period
    
    Returns:
        DataFrame with meteorological tracking schema (see DATA_SCHEMA below)
    """
    records = []
    for i, (date, et0, rain) in enumerate(zip(dates, et0_series, rainfall_series)):
        doy = date.timetuple().tm_yday
        stage = get_growth_stage(doy, crop)
        kc = KC_TABLE[crop][stage]
        etc = et0 * kc                      # Crop evapotranspiration (mm)
        deficit = max(0.0, etc - rain)      # Water deficit (mm)

        # Advisory rule (FAO-56 guideline adapted for 8-day period)
        if deficit <= 0:
            advisory = "No irrigation needed"
            advisory_code = 0
        elif deficit <= 20:
            advisory = "Irrigate soon"
            advisory_code = 1
        else:
            advisory = "Irrigate now"
            advisory_code = 2

        records.append({
            # TRACKING SCHEMA COLUMNS
            "date":           date.strftime("%Y-%m-%d"),
            "doy":            doy,
            "epoch":          i + 1,
            "crop":           crop,
            "growth_stage":   stage,
            "et0_mm":         round(et0, 2),
            "kc":             round(kc, 3),
            "etc_mm":         round(etc, 2),
            "rainfall_mm":    round(rain, 2),
            "deficit_mm":     round(deficit, 2),
            "advisory":       advisory,
            "advisory_code":  advisory_code,   # 0, 1, 2
        })

    return pd.DataFrame(records)


# ─── DATA SCHEMA ────────────────────────────────────────────────────────────
"""
METEOROLOGICAL TRACKING TABLE SCHEMA
File: data/water_balance/water_balance_{field_id}.csv

Columns:
  date            str      ISO date of 8-day period start (YYYY-MM-DD)
  doy             int      Day of year (1–365)
  epoch           int      Epoch number (1–6 for Kharif 2024)
  crop            str      Crop type: Rice / Maize / Cotton
  growth_stage    str      Sowing / Vegetative / Reproductive / Maturity
  et0_mm          float    ERA5 reference evapotranspiration (mm/8-day)
  kc              float    FAO-56 crop coefficient for this stage
  etc_mm          float    Crop evapotranspiration = ET0 × Kc (mm/8-day)
  rainfall_mm     float    CHIRPS effective rainfall (mm/8-day)
  deficit_mm      float    Water deficit = max(0, ETc - P) (mm/8-day)
  advisory        str      Human-readable irrigation advisory
  advisory_code   int      0=No irrigation, 1=Irrigate soon, 2=Irrigate now

Pixel-level aggregation (for raster output):
  pixel_id        int      Unique pixel ID (matches crop-type-mapping schema)
  longitude       float    Pixel centroid longitude
  latitude        float    Pixel centroid latitude
  field_id        str      Optional field polygon ID from command area shapefile
"""


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/advisory_config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)

    # Load met data (output of fetch_met_data.py)
    met_df = pd.read_csv("data/met/met_8day_kharif2024.csv", parse_dates=["date"])
    # Load crop map output (from Repo 1)
    crop_map = pd.read_csv("data/crop_maps/pixel_crop_labels.csv")

    output_dir = Path("data/water_balance")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for crop in ["Rice", "Maize", "Cotton"]:
        crop_pixels = crop_map[crop_map["crop_label_str"] == crop]
        logger.info(f"Processing {crop}: {len(crop_pixels)} pixels")

        result = compute_water_balance(
            et0_series=met_df["et0_mm"],
            rainfall_series=met_df["rainfall_mm"],
            crop=crop,
            dates=pd.to_datetime(met_df["date"])
        )
        result["crop"] = crop
        all_results.append(result)

    final_df = pd.concat(all_results, ignore_index=True)
    out_path = output_dir / "water_balance_kharif2024.csv"
    final_df.to_csv(out_path, index=False)
    logger.info(f"Water balance saved to {out_path}")


if __name__ == "__main__":
    main()
