# crop_mapping/ — Module 1

**Owner:** Member 1  
**Depends on:** `shared/`, `config/kharif2024.yaml`  
**Produces:** `data/processed/kharif2024_features.csv`, `outputs/models/rf_kharif2024.joblib`, `outputs/maps/crop_map_kharif2024.tif`

## Your job
1. Run `gee_scripts/01_collect_features.py` to export the feature CSV from GEE
2. Run `models/train_rf.py` to train the Random Forest and save metrics
3. Run `models/predict_map.py` to generate the crop classification raster

## Run order
```bash
# From repo root
python crop_mapping/gee_scripts/01_collect_features.py --config config/kharif2024.yaml
python crop_mapping/models/train_rf.py                 --config config/kharif2024.yaml
python crop_mapping/models/predict_map.py              --config config/kharif2024.yaml
```

## Key files
- `gee_scripts/01_collect_features.py` — GEE data collection and export
- `features/indices.py` — NDVI, EVI, NDWI, VCI computation
- `features/phenology.py` — peak NDVI, SOS, LGP extraction
- `features/sar_fallback.py` — SAR-only feature path when clouds > 80%
- `models/train_rf.py` — Random Forest training and evaluation
- `models/predict_map.py` — Apply trained model to full AOI raster
- `evaluation/metrics.py` — OA, Kappa, F1, confusion matrix

## Important
- Never rename output columns without updating `shared/schema.py`
- The feature CSV column order must match `shared/schema.FEATURE_COLS`
- Target: OA > 85%, Kappa > 0.80
