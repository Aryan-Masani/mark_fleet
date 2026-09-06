"""
Baseline classical fuel-consumption predictor (XGBoost).

Wraps categorical preprocessing + XGBRegressor behind a simple
fit/predict/save/load interface so the entire fitted model serializes
to ONE joblib artifact — train once, export, and load anywhere later
without retraining.
"""

from __future__ import annotations
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

NUMERIC_FEATURES = [
    "displacement_tons", "cargo_load_fraction", "speed_knots",
    "wind_speed_knots", "wave_height_m", "distance_nm",
]
CATEGORICAL_FEATURES = ["vessel_type", "fuel_type"]
TARGET = "fuel_consumption_tons"


def _build_pipeline(xgb_params: dict | None = None) -> Pipeline:
    xgb_params = xgb_params or dict(
        n_estimators=400, max_depth=6, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, random_state=42,
        n_jobs=-1, tree_method="hist", objective="reg:squarederror",
    )
    preprocessor = ColumnTransformer(
        transformers=[("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
        remainder="passthrough",  # numeric features pass through unchanged
    )
    model = XGBRegressor(**xgb_params)
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


class FuelConsumptionXGBBaseline:
    """Classical baseline fuel-consumption predictor. Interface mirrors
    QuantumInspiredFuelModel so the two are drop-in comparable."""

    FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

    def __init__(self, xgb_params: dict | None = None):
        self.pipeline = _build_pipeline(xgb_params)
        self.is_fitted = False
        self.metrics_: dict = {}

    def fit(self, df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42) -> dict:
        X = df[self.FEATURE_COLUMNS]
        y = df[TARGET]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        self.pipeline.fit(X_train, y_train)
        preds = self.pipeline.predict(X_test)
        self.metrics_ = {
            "mae": float(mean_absolute_error(y_test, preds)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
            "r2": float(r2_score(y_test, preds)),
            "n_test": int(len(y_test)),
        }
        self.is_fitted = True
        return self.metrics_

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted or loaded yet.")
        return self.pipeline.predict(df[self.FEATURE_COLUMNS])

    def predict_one(self, vessel_type, fuel_type, displacement_tons,
                     cargo_load_fraction, speed_knots, wind_speed_knots,
                     wave_height_m, distance_nm) -> float:
        row = pd.DataFrame([{
            "vessel_type": vessel_type, "fuel_type": fuel_type,
            "displacement_tons": displacement_tons,
            "cargo_load_fraction": cargo_load_fraction,
            "speed_knots": speed_knots, "wind_speed_knots": wind_speed_knots,
            "wave_height_m": wave_height_m, "distance_nm": distance_nm,
        }])
        return float(self.predict(row)[0])

    def save(self, path: str) -> None:
        joblib.dump({
            "pipeline": self.pipeline,
            "is_fitted": self.is_fitted,
            "metrics": self.metrics_,
        }, path)

    @classmethod
    def load(cls, path: str) -> "FuelConsumptionXGBBaseline":
        payload = joblib.load(path)
        obj = cls()
        obj.pipeline = payload["pipeline"]
        obj.is_fitted = payload["is_fitted"]
        obj.metrics_ = payload["metrics"]
        return obj
