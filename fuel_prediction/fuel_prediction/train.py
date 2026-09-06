"""
Train once, export forever.

Generates synthetic fleet data, trains both the classical XGBoost
baseline and the quantum-inspired model, saves both as joblib
artifacts under ./models/, and writes a metrics comparison report.

Run this once. Downstream code should load the saved .joblib files
(see predict.py) instead of retraining.
"""

from __future__ import annotations
import json
import os
import time

try:
    from .data_generator import generate_synthetic_fleet_data
    from .baseline_model import FuelConsumptionXGBBaseline
    from .quantum_inspired_model import QuantumInspiredFuelModel
except ImportError:  # allows running as a standalone script: `python train.py`
    from data_generator import generate_synthetic_fleet_data
    from baseline_model import FuelConsumptionXGBBaseline
    from quantum_inspired_model import QuantumInspiredFuelModel

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetic_fleet_data.csv")


def main(n_samples: int = 15000, seed: int = 42) -> dict:
    os.makedirs(MODELS_DIR, exist_ok=True)

    print(f"[1/4] Generating {n_samples} synthetic voyage records...")
    df = generate_synthetic_fleet_data(n_samples=n_samples, seed=seed)
    df.to_csv(DATA_PATH, index=False)

    print("[2/4] Training classical XGBoost baseline...")
    t0 = time.time()
    baseline = FuelConsumptionXGBBaseline()
    baseline_metrics = baseline.fit(df)
    baseline_metrics["train_time_sec"] = round(time.time() - t0, 2)
    baseline.save(os.path.join(MODELS_DIR, "baseline_xgb.joblib"))
    print(f"   baseline metrics: {baseline_metrics}")

    print("[3/4] Training quantum-inspired model (QIEA-tuned)...")
    t0 = time.time()
    quantum_model = QuantumInspiredFuelModel()
    quantum_metrics = quantum_model.fit(df)
    quantum_metrics["train_time_sec"] = round(time.time() - t0, 2)
    quantum_model.save(os.path.join(MODELS_DIR, "quantum_inspired.joblib"))
    print(f"   quantum-inspired metrics: {quantum_metrics}")

    print("[4/4] Writing comparison report...")
    report = {"baseline_xgb": baseline_metrics, "quantum_inspired": quantum_metrics}
    with open(os.path.join(MODELS_DIR, "training_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print("\nDone. Saved artifacts in ./models/:")
    print("  - baseline_xgb.joblib")
    print("  - quantum_inspired.joblib")
    print("  - training_report.json")
    print("\nNo retraining needed downstream — load these with")
    print("FuelConsumptionXGBBaseline.load(...) or QuantumInspiredFuelModel.load(...)")
    print("(see predict.py for a ready-made wrapper).")
    return report


if __name__ == "__main__":
    main()
