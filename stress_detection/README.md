# stress_detection/ — Module 2

**Owner:** Member 2  
**Depends on:** `data/processed/kharif2024_features.csv` (output of Module 1), `shared/`, `config/`  
**Produces:** `outputs/metrics/stress_labels.csv`, `outputs/models/lstm_best.pt`

## Your job
1. Run `data/prepare_tensors.py` to convert the feature CSV into (B, T, F) tensors
2. Run `models/train_lstm.py` to train the Bidirectional LSTM
3. Run `models/predict_stress.py` to generate per-pixel stress labels

## Tensor shape
```
Input:  X     → (Batch=256, Time=6, Features=8)
Stage:  stage → (Batch=256, Time=6)   — growth stage index 0-3
Output: logits → (Batch=256, Time=6, Classes=3)

Features (in order — DO NOT reorder):
  [0] ndvi  [1] evi   [2] ndwi
  [3] vv    [4] vh    [5] vhvv_ratio
  [6] vci   [7] smi
```

## Run order
```bash
# From repo root
python stress_detection/data/prepare_tensors.py  --config config/kharif2024.yaml
python stress_detection/models/train_lstm.py     --config config/kharif2024.yaml
python stress_detection/models/predict_stress.py --config config/kharif2024.yaml
```

## Key files
- `data/prepare_tensors.py` — reshape feature CSV into PyTorch tensors
- `data/dataset.py` — PyTorch Dataset class for the stress task
- `models/lstm_model.py` — BiLSTM architecture with stage embedding
- `models/train_lstm.py` — training loop with early stopping
- `models/predict_stress.py` — inference on all pixels
- `utils/vci_computer.py` — VCI computation (used for pseudo-labels)
- `utils/stage_labels.py` — assign growth stage per epoch per crop

## Important
- Module 1's CSV must exist before you run anything here
- Check `shared/schema.LSTM_FEATURE_ORDER` — your feature order must match exactly
- Stress pseudo-labels are generated from VCI thresholds in config if no ground truth exists
