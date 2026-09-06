"""
Inference-only interface — load pre-trained model artifacts and
predict fuel consumption WITHOUT retraining. This is the file a
downstream integration (e.g. the QPSO fitness function or the
dashboard) should import from.

Usage
-----
    from predict import FuelPredictor

    predictor = FuelPredictor(model_type="quantum")  # or "baseline"
    fuel_tons = predictor.predict_one(
        vessel_type="container", fuel_type="LNG",
        displacement_tons=80000, cargo_load_fraction=0.7,
        speed_knots=18, wind_speed_knots=12, wave_height_m=1.5,
        distance_nm=3000,
    )

This corresponds to FC-hat(v, s, l, w, f) in the Deliverable 2
mathematical formulation — call this function inside the QPSO/MOQPSO
fitness evaluator; never recompute fuel consumption analytically there.
"""

from __future__ import annotations
import os
import pandas as pd

try:
    from .baseline_model import FuelConsumptionXGBBaseline
    from .quantum_inspired_model import QuantumInspiredFuelModel
except ImportError:  # allows running as a standalone script
    from baseline_model import FuelConsumptionXGBBaseline
    from quantum_inspired_model import QuantumInspiredFuelModel

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


class FuelPredictor:
    """Loads a saved model once at construction; serves predictions with no retraining."""

    def __init__(self, model_type: str = "quantum", models_dir: str = MODELS_DIR):
        if model_type == "quantum":
            path = os.path.join(models_dir, "quantum_inspired.joblib")
            self.model = QuantumInspiredFuelModel.load(path)
        elif model_type == "baseline":
            path = os.path.join(models_dir, "baseline_xgb.joblib")
            self.model = FuelConsumptionXGBBaseline.load(path)
        else:
            raise ValueError("model_type must be 'quantum' or 'baseline'")
        self.model_type = model_type

    def predict_one(self, vessel_type: str, fuel_type: str, displacement_tons: float,
                     cargo_load_fraction: float, speed_knots: float,
                     wind_speed_knots: float, wave_height_m: float,
                     distance_nm: float) -> float:
        """Returns predicted fuel consumption in tons for one voyage leg."""
        return self.model.predict_one(
            vessel_type, fuel_type, displacement_tons, cargo_load_fraction,
            speed_knots, wind_speed_knots, wave_height_m, distance_nm,
        )

    def predict_batch(self, df: pd.DataFrame):
        """Returns an array of predicted fuel consumption (tons) for a batch of rows."""
        return self.model.predict(df)


if __name__ == "__main__":
    predictor = FuelPredictor(model_type="quantum")
    example = predictor.predict_one(
        vessel_type="container", fuel_type="LNG", displacement_tons=80000,
        cargo_load_fraction=0.7, speed_knots=18, wind_speed_knots=12,
        wave_height_m=1.5, distance_nm=3000,
    )
    print(f"Predicted fuel consumption: {example:.2f} tons")
