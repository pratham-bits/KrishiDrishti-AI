"""
shared/schema.py
================
Single source of truth for column names, data types, and label mappings
shared across all three modules. If you rename a column, rename it HERE
and it propagates everywhere automatically.

Import pattern:
    from shared.schema import FEATURE_COLS, CROP_LABELS, STRESS_LABELS
"""

# ── Crop label mapping ────────────────────────────────────────
CROP_LABELS = {
    "Rice":    0,
    "Maize":   1,
    "Cotton":  2,
    "Unknown": -1,
}
CROP_NAMES = {v: k for k, v in CROP_LABELS.items()}

# ── Stress label mapping ──────────────────────────────────────
STRESS_LABELS = {
    "No Stress": 0,
    "Mild":      1,
    "Severe":    2,
}
STRESS_NAMES = {v: k for k, v in STRESS_LABELS.items()}

# ── Growth stage mapping ──────────────────────────────────────
STAGE_LABELS = {
    "Sowing":       0,
    "Vegetative":   1,
    "Reproductive": 2,
    "Maturity":     3,
}
STAGE_NAMES = {v: k for k, v in STAGE_LABELS.items()}

# ── Epoch names (16-day composites, Kharif 2024) ─────────────
EPOCH_NAMES = ["E1", "E2", "E3", "E4", "E5", "E6"]

# ── Feature columns per epoch ────────────────────────────────
OPTICAL_BANDS  = ["ndvi", "evi", "ndwi"]
SAR_BANDS      = ["vv", "vh", "vhvv"]
TEXTURE_BANDS  = ["glcm_contrast", "glcm_entropy"]
PHENOLOGY_COLS = ["ndvi_peak", "ndvi_sos", "ndvi_lgp"]

# Multi-temporal feature columns (band × epoch combinations)
OPTICAL_COLS = [f"{b}_{e}" for e in EPOCH_NAMES for b in OPTICAL_BANDS]
SAR_COLS     = [f"{b}_{e}" for e in EPOCH_NAMES for b in SAR_BANDS]

# All feature columns used as model input (Module 1 RF)
FEATURE_COLS = OPTICAL_COLS + SAR_COLS + TEXTURE_BANDS + PHENOLOGY_COLS

# Cloud flag columns (dropped before training, kept for fallback logic)
CLOUD_FLAG_COLS = [f"cloud_frac_{e}" for e in EPOCH_NAMES]

# Metadata columns (not used as features)
META_COLS = ["pixel_id", "longitude", "latitude"]

# Label column
LABEL_COL = "crop_label"

# ── LSTM tensor feature order (Module 2) ─────────────────────
# Exactly 8 features per time step, in this order.
# Changing this order breaks saved model weights — do not reorder.
LSTM_FEATURE_ORDER = ["ndvi", "evi", "ndwi", "vv", "vh", "vhvv_ratio", "vci", "smi"]
N_FEATURES = len(LSTM_FEATURE_ORDER)   # 8
N_TIMESTEPS = len(EPOCH_NAMES)         # 6

# ── Water balance schema (Module 3) ──────────────────────────
WATER_BALANCE_COLS = [
    "pixel_id", "longitude", "latitude",
    "date", "doy", "epoch",
    "crop", "growth_stage",
    "et0_mm", "kc", "etc_mm",
    "rainfall_mm", "deficit_mm",
    "advisory", "advisory_code",
]
