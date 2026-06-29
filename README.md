# BAH 2026 — PS6: AI-Driven Crop Monitoring & Irrigation Advisory

**Bharatiya Antariksh Hackathon 2026 | Problem Statement 6**

AI-driven crop type mapping, moisture stress detection, and irrigation advisory
for canal command areas using Sentinel-2, Sentinel-1, CHIRPS, and ERA5.

**Pilot area:** Nagarjunasagar Left Canal Command Area, Telangana/AP  
**Season:** Kharif 2024 (June – November 2024)  
**Crops:** Rice · Maize · Cotton  

---

## Repository Structure

```
bah2026-ps6/
├── crop_mapping/          # Module 1 — GEE ingestion + RF/XGBoost classification
├── stress_detection/      # Module 2 — LSTM moisture stress detection
├── advisory_engine/       # Module 3 — FAO-56 water balance + Streamlit dashboard
├── shared/                # Common utilities used across all three modules
├── config/                # Single YAML config controlling the full pipeline
├── data/                  # Raw GEE exports, processed CSVs (gitignored)
├── outputs/               # Trained models, maps, metric JSONs (gitignored)
├── notebooks/             # EDA and result visualization
├── docs/                  # Architecture docs, data schema, system design
└── app.py                 # Streamlit dashboard entry point
```

---

## Team & Module Ownership

| Module | Owner | Responsibility |
|---|---|---|
| `crop_mapping/` | Member 1 | GEE scripts, feature engineering, RF training |
| `stress_detection/` | Member 2 | Tensor prep, LSTM model, stress evaluation |
| `advisory_engine/` | Member 3 | Water balance, dashboard components |
| `shared/`, `config/`, `app.py` | Team Lead (Pratham) | Integration, merges, deployment |

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/bah2026-ps6.git
cd bah2026-ps6

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Authenticate GEE
earthengine authenticate

# 5. Run the full pipeline (in order)
python crop_mapping/gee_scripts/01_collect_features.py --config config/kharif2024.yaml
python crop_mapping/models/train_rf.py                 --config config/kharif2024.yaml
python stress_detection/models/train_lstm.py           --config config/kharif2024.yaml
python advisory_engine/processors/water_balance.py     --config config/kharif2024.yaml

# 6. Launch dashboard
streamlit run app.py
```

---

## Data Pipeline Flow

```
GEE (Sentinel-2 + Sentinel-1 + CHIRPS + ERA5)
        │
        ▼
crop_mapping/gee_scripts/    →   data/processed/kharif2024_features.csv
        │
        ▼
crop_mapping/models/         →   outputs/models/rf_kharif2024.joblib
                                 outputs/maps/crop_map_kharif2024.tif
        │
        ▼
stress_detection/models/     →   outputs/metrics/stress_labels.csv
        │
        ▼
advisory_engine/processors/  →   outputs/metrics/water_balance.csv
        │
        ▼
app.py  →  Streamlit dashboard (localhost:8501)
```

---

## Core Dependencies

```
earthengine-api>=0.1.390
geemap>=0.30.0
scikit-learn>=1.4.0
xgboost>=2.0.0
torch>=2.2.0
pandas>=2.1.0
numpy>=1.26.0
geopandas>=0.14.0
rasterio>=1.3.0
streamlit>=1.32.0
folium>=0.16.0
streamlit-folium>=0.18.0
plotly>=5.19.0
pyyaml>=6.0.0
```

---

## Branching Strategy

```
main              ← 
├── feature/crop-mapping    ← Member 1
├── feature/stress-lstm     ← Member 2
└── feature/advisory-dash   ← Member 3
```

Never commit directly to `main`. Open a PR, get it reviewed, then merge.
