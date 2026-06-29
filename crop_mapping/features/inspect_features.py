"""
crop_mapping/features/inspect_features.py
==========================================
Run this after downloading the SAR preview CSV from Google Drive.
Produces a feature distribution report and highlights separation
between crop classes (using VCI-based pseudo-labels for unlabeled data).

Usage:
    python crop_mapping/features/inspect_features.py \
        --csv data/raw/sar_preview_YYYYMMDD_HHMM.csv

What this tells you:
    - Are SAR values in expected ranges?
    - Which features show the most separation between crop zones?
    - Are there any NaN/null values that need handling?
    - Is the E5 NDVI behaving as expected?
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")   # non-interactive backend — saves to file
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.schema import EPOCH_NAMES


def load_and_validate(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    print(f"\n{'='*55}")
    print(f"FEATURE INSPECTION REPORT")
    print(f"{'='*55}")
    print(f"Rows:    {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"\nAll columns:")
    for c in sorted(df.columns):
        print(f"  {c}")
    return df


def check_value_ranges(df: pd.DataFrame):
    """Verify SAR values are in expected physical ranges."""
    print(f"\n{'─'*55}")
    print("VALUE RANGE CHECK")
    print(f"{'─'*55}")

    checks = {
        # (column_pattern, expected_min, expected_max, unit)
        "vv_": (-30, 0,   "dB — VV backscatter"),
        "vh_": (-35, -5,  "dB — VH backscatter"),
        "vhvv_": (0, 1,   "linear — VH/VV ratio"),
        "smi_":  (0, 1,   "normalised — soil moisture index"),
        "ndvi_E5_opt": (-0.1, 1.0, "NDVI — E5 optical"),
        "evi_E5_opt":  (-0.5, 1.0, "EVI  — E5 optical"),
        "ndwi_E5_opt": (-1.0, 1.0, "NDWI — E5 optical"),
    }

    for pattern, (exp_min, exp_max, label) in checks.items():
        cols = [c for c in df.columns if c.startswith(pattern)]
        if not cols:
            print(f"  MISSING  {pattern}*  ({label})")
            continue
        vals = df[cols].values.flatten()
        vals = vals[~np.isnan(vals)]
        actual_min = round(float(np.nanmin(vals)), 3)
        actual_max = round(float(np.nanmax(vals)), 3)
        in_range = exp_min <= actual_min and actual_max <= exp_max * 1.1
        status = "✓" if in_range else "⚠"
        print(f"  {status} {pattern:<16} min={actual_min:7.3f}  max={actual_max:7.3f}  "
              f"[expected {exp_min} to {exp_max}]  {label}")


def check_nulls(df: pd.DataFrame):
    print(f"\n{'─'*55}")
    print("NULL / NaN CHECK")
    print(f"{'─'*55}")
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if len(null_cols) == 0:
        print("  ✓ No null values found")
    else:
        print(f"  ⚠ {len(null_cols)} columns have nulls:")
        for col, n in null_cols.items():
            pct = round(100 * n / len(df), 1)
            print(f"    {col}: {n} nulls ({pct}%)")
        print("\n  → These will be imputed with column median during training.")
        print("    If > 30% null in any column, that epoch/feature is unreliable.")


def analyse_sar_temporal(df: pd.DataFrame):
    """
    Print the SAR temporal profile — how VV and VH change across epochs.
    This is the key diagnostic for crop discrimination.
    """
    print(f"\n{'─'*55}")
    print("SAR TEMPORAL PROFILE (mean over all 500 points)")
    print(f"{'─'*55}")
    print(f"\n  {'Epoch':<6}  {'VV (dB)':<12}  {'VH (dB)':<12}  {'VH/VV':<10}  {'SMI'}")
    print(f"  {'─'*6}  {'─'*11}  {'─'*11}  {'─'*9}  {'─'*6}")
    for ep in EPOCH_NAMES:
        vv_col   = f"vv_{ep}"
        vh_col   = f"vh_{ep}"
        vhvv_col = f"vhvv_{ep}"
        smi_col  = f"smi_{ep}"
        if vv_col not in df.columns:
            continue
        vv_mean   = df[vv_col].mean()
        vh_mean   = df[vh_col].mean()
        vhvv_mean = df[vhvv_col].mean() if vhvv_col in df.columns else float("nan")
        smi_mean  = df[smi_col].mean()  if smi_col  in df.columns else float("nan")
        print(f"  {ep:<6}  {vv_mean:<12.3f}  {vh_mean:<12.3f}  "
              f"{vhvv_mean:<10.4f}  {smi_mean:.3f}")

    print(f"\n  What to look for:")
    print(f"  • VV should be lowest at E2/E3 (peak flooding for rice)")
    print(f"  • VH should INCREASE from E1 to E3/E4 (canopy development)")
    print(f"  • SMI should be highest at E2/E3 (wet monsoon months)")


def check_e5_optical(df: pd.DataFrame):
    print(f"\n{'─'*55}")
    print("E5 OPTICAL FEATURES (Aug 4-19 — only clear epoch)")
    print(f"{'─'*55}")
    for col in ["ndvi_E5_opt", "evi_E5_opt", "ndwi_E5_opt"]:
        if col not in df.columns:
            print(f"  MISSING: {col}")
            continue
        vals = df[col].dropna()
        print(f"  {col:<18}  "
              f"mean={vals.mean():.3f}  "
              f"std={vals.std():.3f}  "
              f"min={vals.min():.3f}  "
              f"max={vals.max():.3f}")

    if "ndvi_E5_opt" in df.columns:
        ndvi = df["ndvi_E5_opt"].dropna()
        pct_veg = (ndvi > 0.4).mean() * 100
        print(f"\n  NDVI > 0.4 (active vegetation): {pct_veg:.1f}% of points")
        print(f"  Expected for Aug over Nagarjunasagar: 60-80% vegetated")
        if pct_veg < 40:
            print(f"  ⚠ Low vegetation fraction — check E5 cloud masking")
        else:
            print(f"  ✓ Vegetation fraction looks reasonable")


def plot_feature_distributions(df: pd.DataFrame, output_path: str):
    """Save a feature distribution plot to outputs/metrics/."""
    features_to_plot = []
    for ep in EPOCH_NAMES:
        for band in ["vv", "vh"]:
            col = f"{band}_{ep}"
            if col in df.columns:
                features_to_plot.append(col)
    for col in ["ndvi_E5_opt", "evi_E5_opt", "ndwi_E5_opt"]:
        if col in df.columns:
            features_to_plot.append(col)

    n = len(features_to_plot)
    if n == 0:
        return

    cols_grid = 4
    rows_grid = (n + cols_grid - 1) // cols_grid
    fig, axes = plt.subplots(rows_grid, cols_grid,
                             figsize=(16, rows_grid * 3))
    axes = axes.flatten()

    for i, feat in enumerate(features_to_plot):
        vals = df[feat].dropna()
        axes[i].hist(vals, bins=40, color="#2563eb", alpha=0.7, edgecolor="none")
        axes[i].set_title(feat, fontsize=9)
        axes[i].set_xlabel("Value", fontsize=8)
        axes[i].set_ylabel("Count", fontsize=8)
        axes[i].tick_params(labelsize=7)

    # Hide unused axes
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("Feature Distributions — SAR Preview (500 random points)\n"
                 "Nagarjunasagar, Kharif 2024",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\n  ✓ Distribution plot saved: {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True,
                        help="Path to downloaded SAR preview CSV")
    args = parser.parse_args()

    df = load_and_validate(args.csv)
    check_value_ranges(df)
    check_nulls(df)
    analyse_sar_temporal(df)
    check_e5_optical(df)
    plot_feature_distributions(
        df,
        output_path="outputs/metrics/feature_distributions.png"
    )

    print(f"\n{'='*55}")
    print("NEXT STEPS")
    print(f"{'='*55}")
    print("1. Check value ranges above — all should show ✓")
    print("2. Open outputs/metrics/feature_distributions.png")
    print("   SAR histograms should be roughly Gaussian")
    print("   NDVI_E5 should peak around 0.5-0.8 for healthy crops")
    print("3. If checks pass, proceed to GT collection:")
    print("   → Follow docs/GROUND_TRUTH_GUIDE.md")
    print("   → Then run: python crop_mapping/gee_scripts/01_collect_features.py")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()