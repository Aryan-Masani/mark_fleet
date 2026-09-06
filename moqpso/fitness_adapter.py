"""
fitness_adapter.py — Interface contract bridge between Deliverable 1 (Fuel Prediction)
and Deliverable 3 (MOQPSO Optimizer).

Per Section 9 of SIH26138_D2_Mathematical_Formulation.md:
"The prediction model FC_hat(v, s, l, w, f) is called as a black-box function inside J1, J2,
and every fitness evaluation. D3 never computes fuel consumption analytically."

Actual FuelPredictor signature in fuel_prediction/fuel_prediction/predict.py:
    predictor.predict_one(
        vessel_type: str,
        fuel_type: str,
        displacement_tons: float,
        cargo_load_fraction: float,
        speed_knots: float,
        wind_speed_knots: float,
        wave_height_m: float,
        distance_nm: float
    ) -> float
"""

from __future__ import annotations
import os
import sys
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# Ensure fuel_prediction directory is on sys.path so joblib unpickler resolves
# 'quantum_inspired_model' correctly without touching fuel_prediction internals.
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
_FUEL_PRED_DIR = os.path.join(_WORKSPACE_ROOT, "fuel_prediction", "fuel_prediction")

if _FUEL_PRED_DIR not in sys.path:
    sys.path.insert(0, _FUEL_PRED_DIR)

try:
    from predict import FuelPredictor
except ImportError:
    # Direct relative fallback if predict is found in current path
    from fuel_prediction.fuel_prediction.predict import FuelPredictor


class FitnessAdapter:
    """Singleton/wrapper around FuelPredictor guaranteeing black-box evaluation."""

    def __init__(self, model_type: str = "quantum", clamp_non_negative: bool = True):
        self.model_type = model_type
        self.clamp_non_negative = clamp_non_negative
        models_dir = os.path.join(_FUEL_PRED_DIR, "models")
        self.predictor = FuelPredictor(model_type=model_type, models_dir=models_dir)
        self.eval_count = 0

    def predict_fuel(
        self,
        vessel_type: str,
        fuel_type: str,
        displacement_tons: float,
        cargo_load_fraction: float,
        speed_knots: float,
        wind_speed_knots: float,
        wave_height_m: float,
        distance_nm: float,
    ) -> float:
        """
        Calls D1 FuelPredictor.predict_one.
        Returns predicted fuel consumption in metric tons.
        """
        self.eval_count += 1
        raw_pred = self.predictor.predict_one(
            vessel_type=vessel_type,
            fuel_type=fuel_type,
            displacement_tons=float(displacement_tons),
            cargo_load_fraction=float(cargo_load_fraction),
            speed_knots=float(speed_knots),
            wind_speed_knots=float(wind_speed_knots),
            wave_height_m=float(wave_height_m),
            distance_nm=float(distance_nm),
        )
        if self.clamp_non_negative:
            # Physically, voyage fuel consumption cannot be negative
            return max(0.0, float(raw_pred))
        return float(raw_pred)

    def predict_batch(self, df: pd.DataFrame) -> np.ndarray:
        """Calls D1 FuelPredictor.predict_batch on a DataFrame of features."""
        preds = self.predictor.predict_batch(df)
        if self.clamp_non_negative:
            return np.maximum(0.0, preds)
        return preds
