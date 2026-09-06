# fuel_prediction — Deliverable 1 (SIH26138)

Fuel consumption prediction module: a physics-based synthetic data
generator, a classical XGBoost baseline, and a quantum-inspired
variant (rotation-gate feature encoding + QIEA-tuned hyperparameters).
**Both models are pre-trained** — the `models/` folder ships with
this package, so no training is required to use it.

## Contents

```
fuel_prediction/
├── __init__.py               # package exports
├── data_generator.py         # synthetic voyage-data generator (physics-based)
├── baseline_model.py         # FuelConsumptionXGBBaseline (classical)
├── quantum_inspired_model.py # QuantumFeatureMap + QIEA + QuantumInspiredFuelModel
├── train.py                  # run ONCE to (re)generate data + retrain + export
├── predict.py                # inference-only interface — import this downstream
├── requirements.txt
├── models/
│   ├── baseline_xgb.joblib        # pre-trained, ready to load
│   ├── quantum_inspired.joblib    # pre-trained, ready to load
│   └── training_report.json       # metrics from the training run below
└── synthetic_fleet_data.csv  # the dataset used to train the shipped models
```

## Install

```bash
pip install -r requirements.txt
```

## Use immediately (no training) — this is the integration point

```python
from fuel_prediction.predict import FuelPredictor

predictor = FuelPredictor(model_type="quantum")  # or "baseline"

fuel_tons = predictor.predict_one(
    vessel_type="container",      # container | bulk_carrier | tanker | general_cargo
    fuel_type="LNG",              # HFO | LNG | Methanol | Hydrogen | Ammonia
    displacement_tons=80000,
    cargo_load_fraction=0.7,      # 0-1
    speed_knots=18,
    wind_speed_knots=12,
    wave_height_m=1.5,
    distance_nm=3000,
)
```

Or for a batch of rows (a pandas DataFrame with the same columns):

```python
preds = predictor.predict_batch(df)  # returns a numpy array, tons per row
```

**This `predict_one` / `predict_batch` call is exactly what should sit
inside the QPSO/MOQPSO fitness function from Deliverable 3** — it is
the $\hat{FC}(v, s, l, w, f)$ term in the Deliverable 2 mathematical
formulation. The optimizer should never recompute fuel consumption
analytically; it should call this predictor.

## Retraining (only if you need to)

Only run this if you want to regenerate the synthetic dataset or
retrain on new/real data — the shipped `models/` artifacts already
work out of the box.

```bash
python train.py
```

This regenerates `synthetic_fleet_data.csv`, retrains both models,
overwrites the two `.joblib` files, and rewrites `training_report.json`.

To train on your own real data instead of synthetic data: build a
DataFrame with columns `vessel_type, fuel_type, displacement_tons,
cargo_load_fraction, speed_knots, wind_speed_knots, wave_height_m,
distance_nm, fuel_consumption_tons`, then call
`FuelConsumptionXGBBaseline().fit(df)` or
`QuantumInspiredFuelModel().fit(df)` directly and `.save(path)` the
result — no need to go through `train.py`.

## Current benchmark (from the shipped `training_report.json`)

| Model | MAE (tons) | RMSE (tons) | R² |
|---|---|---|---|
| Classical XGBoost baseline | 161.1 | 302.6 | 0.9892 |
| Quantum-inspired (QIEA-tuned) | 155.3 | 288.3 | 0.9902 |

The quantum-inspired model's QIEA hyperparameter search history
(`training_report.json` → `quantum_inspired.qiea_convergence`) shows
monotonic improvement in validation RMSE across generations — useful
directly for the Deliverable 5 benchmarking write-up (convergence
speed comparison).

## Important caveats for whoever integrates this next

- **The physical constants in `data_generator.py`** (hull-efficiency
  constants, baseline SFOC, fuel mass multipliers, emission factors)
  are **illustrative placeholders** for prototyping, not validated
  engineering data. Replace `VESSEL_TYPES` / `FUEL_TYPES` /
  `BASELINE_SFOC_G_PER_KWH` with class-society or manufacturer figures
  before using this for anything beyond a hackathon demo.
- Input feature order/names must match exactly:
  `vessel_type, fuel_type, displacement_tons, cargo_load_fraction,
  speed_knots, wind_speed_knots, wave_height_m, distance_nm`.
- Both models raise `RuntimeError` if you call `.predict()` before
  `.fit()`/`.load()` — always go through `FuelPredictor`, which loads
  on construction.
- `QuantumInspiredFuelModel.fit()` re-runs the QIEA search (~2–3 min
  on the shipped dataset size); this only matters if you retrain —
  normal inference via `predict.py` is instant.
