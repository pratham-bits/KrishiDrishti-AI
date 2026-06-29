# advisory_engine/ — Module 3

**Owner:** Member 3  
**Depends on:** `outputs/maps/crop_map_kharif2024.tif` (Module 1), `outputs/metrics/stress_labels.csv` (Module 2), `shared/`, `config/`  
**Produces:** `outputs/metrics/water_balance_kharif2024.csv`, `outputs/maps/advisory_map_kharif2024.tif`  
**Also owns:** The Streamlit dashboard components in `dashboard/components/`

## Your job
1. Run `processors/fetch_met_data.py` to pull CHIRPS + ERA5 data from GEE
2. Run `processors/water_balance.py` to compute ETc, deficit, and advisory class per pixel
3. Build out each dashboard component in `dashboard/components/`

## FAO-56 water balance logic
```
ETc  = ET0 × Kc(crop, growth_stage)    # Crop evapotranspiration
P    = CHIRPS 8-day rainfall            # Effective precipitation
D    = ETc - P                          # Water deficit (mm/8-day)

Advisory:
  D <= 0      →  advisory_code = 0  "No irrigation needed"
  0 < D <= 20 →  advisory_code = 1  "Irrigate soon"
  D > 20      →  advisory_code = 2  "Irrigate now"
```

## Run order
```bash
# From repo root
python advisory_engine/processors/fetch_met_data.py  --config config/kharif2024.yaml
python advisory_engine/processors/water_balance.py   --config config/kharif2024.yaml
python advisory_engine/processors/advisory_gen.py    --config config/kharif2024.yaml

# Then launch the dashboard
streamlit run app.py
```

## Key files
- `processors/fetch_met_data.py` — pull CHIRPS rainfall + ERA5 ET₀ from GEE
- `processors/water_balance.py` — FAO-56 ETc and deficit computation
- `processors/advisory_gen.py` — classify deficit into 3-class advisory
- `dashboard/components/crop_map.py` — Tab 1: crop type map (Folium)
- `dashboard/components/stress_map.py` — Tab 2: stress level map
- `dashboard/components/advisory_map.py` — Tab 3: irrigation advisory map
- `dashboard/components/time_series.py` — Tab 4: NDVI/VCI time series

## Important
- Kc values are in `config/kharif2024.yaml` under `advisory_engine.kc_values`
- The crop type from Module 1 determines which Kc row to use
- Water balance output column names must match `shared/schema.WATER_BALANCE_COLS`
