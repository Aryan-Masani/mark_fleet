"""
Quantum-inspired fuel-consumption predictor.

Two quantum-inspired components, kept separate so each can be
evaluated/benchmarked independently against the classical baseline:

1. QuantumFeatureMap
   A rotation-gate-inspired feature encoding. Each normalized numeric
   feature x in [0,1] is mapped to a qubit-rotation angle
   theta = x * pi/2, expanded into cos(theta)/sin(theta) components,
   plus pairwise product terms cos(theta_i)*cos(theta_j) (a lightweight
   stand-in for two-qubit entanglement correlations). This gives the
   downstream regressor a richer feature space than the raw inputs.

2. QIEAHyperparameterOptimizer
   A Quantum-Inspired Evolutionary Algorithm (Q-bit individuals +
   rotation-gate update rule, in the style of Han & Kim, 2002) used to
   search the regressor's hyperparameter space, replacing grid/random
   search with a quantum-inspired search operator.

Both are combined into QuantumInspiredFuelModel, which mirrors the
FuelConsumptionXGBBaseline interface (fit/predict/save/load) so the
two models are drop-in comparable in a benchmarking suite.
"""

from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
import joblib
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


# ---------------------------------------------------------------------
# 1. Quantum-inspired feature map
# ---------------------------------------------------------------------

class QuantumFeatureMap:
    """Rotation-gate-inspired feature expansion for numeric features."""

    def __init__(self, feature_names: list[str] | None = None):
        self.feature_names = feature_names or list(NUMERIC_FEATURES)
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit(self, X: pd.DataFrame) -> "QuantumFeatureMap":
        arr = X[self.feature_names].to_numpy(dtype=float)
        self.min_ = arr.min(axis=0)
        self.max_ = arr.max(axis=0)
        self.max_ = np.where(self.max_ == self.min_, self.min_ + 1.0, self.max_)  # guard constants
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if self.min_ is None:
            raise RuntimeError("QuantumFeatureMap must be fit before transform.")
        arr = X[self.feature_names].to_numpy(dtype=float)
        norm = np.clip((arr - self.min_) / (self.max_ - self.min_), 0.0, 1.0)
        theta = norm * (np.pi / 2)

        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        n_features = theta.shape[1]
        pair_idx = list(itertools.combinations(range(n_features), 2))
        pair_terms = (
            np.stack([cos_t[:, i] * cos_t[:, j] for i, j in pair_idx], axis=1)
            if pair_idx else np.zeros((theta.shape[0], 0))
        )
        return np.concatenate([cos_t, sin_t, pair_terms], axis=1)

    def fit_transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.fit(X).transform(X)

    @property
    def output_dim(self) -> int:
        n = len(self.feature_names)
        return 2 * n + (n * (n - 1) // 2)


# ---------------------------------------------------------------------
# 2. Quantum-Inspired Evolutionary Algorithm for hyperparameter search
# ---------------------------------------------------------------------

N_BITS_PER_PARAM = 6  # 64 discrete levels per hyperparameter

HYPERPARAM_RANGES = {
    "max_depth":     (3, 8),      # int
    "learning_rate": (0.01, 0.30),  # float
    "n_estimators":  (100, 400),  # int
}
PARAM_ORDER = list(HYPERPARAM_RANGES.keys())


def _bits_to_real(bits: np.ndarray, lo: float, hi: float) -> float:
    """Decode a binary vector to a real value in [lo, hi]."""
    as_int = int("".join(str(int(b)) for b in bits), 2)
    max_int = 2 ** len(bits) - 1
    return lo + (as_int / max_int) * (hi - lo)


class QIEAHyperparameterOptimizer:
    """
    Quantum-Inspired Evolutionary Algorithm for hyperparameter tuning.

    Each individual is a set of qubits (one per bit of each encoded
    hyperparameter), represented by amplitude alpha (probability of
    collapsing to bit '0'; beta = sqrt(1-alpha^2) for bit '1').
    Individuals are observed (collapsed to binary strings), decoded
    into real hyperparameter values, evaluated via a user-supplied
    fitness function, and the qubit population is rotated toward the
    best solution found so far each generation.
    """

    def __init__(self, population_size: int = 10, generations: int = 10,
                 rotation_angle: float = 0.05 * np.pi, random_state: int = 42):
        self.population_size = population_size
        self.generations = generations
        self.rotation_angle = rotation_angle
        self.rng = np.random.default_rng(random_state)
        self.n_bits_total = N_BITS_PER_PARAM * len(PARAM_ORDER)
        self.best_params_: dict | None = None
        self.best_fitness_: float | None = None
        self.history_: list[float] = []

    def _init_qubits(self) -> np.ndarray:
        return np.full((self.population_size, self.n_bits_total), 1 / np.sqrt(2))

    def _observe(self, alphas: np.ndarray) -> np.ndarray:
        probs_zero = alphas ** 2
        r = self.rng.random(alphas.shape)
        return (r >= probs_zero).astype(int)  # bit=0 w.p. probs_zero, else bit=1

    def _decode(self, bits_row: np.ndarray) -> dict:
        params = {}
        for i, name in enumerate(PARAM_ORDER):
            chunk = bits_row[i * N_BITS_PER_PARAM:(i + 1) * N_BITS_PER_PARAM]
            lo, hi = HYPERPARAM_RANGES[name]
            val = _bits_to_real(chunk, lo, hi)
            params[name] = int(round(val)) if name in ("max_depth", "n_estimators") else float(val)
        return params

    def _rotate_toward_best(self, alphas: np.ndarray, bits: np.ndarray,
                             best_bits: np.ndarray) -> np.ndarray:
        new_alphas = alphas.copy()
        for i in range(alphas.shape[0]):
            for j in range(alphas.shape[1]):
                if bits[i, j] != best_bits[j]:
                    theta = self.rotation_angle if best_bits[j] == 1 else -self.rotation_angle
                    a = alphas[i, j]
                    b = np.sqrt(max(0.0, 1 - a ** 2))
                    new_a = a * np.cos(theta) - b * np.sin(theta)
                    new_alphas[i, j] = float(np.clip(new_a, 0.0, 1.0))
        return new_alphas

    def optimize(self, fitness_fn) -> dict:
        """fitness_fn: callable(params: dict) -> float, LOWER is better (e.g. validation RMSE)."""
        alphas = self._init_qubits()
        best_bits = None
        best_fitness = np.inf
        best_params = None

        for _ in range(self.generations):
            bits = self._observe(alphas)
            fitnesses = np.array([fitness_fn(self._decode(bits[i])) for i in range(self.population_size)])

            gen_best_idx = int(np.argmin(fitnesses))
            if fitnesses[gen_best_idx] < best_fitness:
                best_fitness = float(fitnesses[gen_best_idx])
                best_bits = bits[gen_best_idx].copy()
                best_params = self._decode(best_bits)

            self.history_.append(best_fitness)
            alphas = self._rotate_toward_best(alphas, bits, best_bits)

        self.best_params_ = best_params
        self.best_fitness_ = best_fitness
        return best_params


# ---------------------------------------------------------------------
# 3. Combined quantum-inspired fuel model
# ---------------------------------------------------------------------

class QuantumInspiredFuelModel:
    """
    Quantum-inspired fuel-consumption predictor:
    QuantumFeatureMap (numeric) + OneHotEncoder (categorical) feeding
    an XGBRegressor whose hyperparameters are tuned by
    QIEAHyperparameterOptimizer instead of grid/random search.
    Interface mirrors FuelConsumptionXGBBaseline for drop-in comparison.
    """

    def __init__(self, qiea_population: int = 10, qiea_generations: int = 10,
                 random_state: int = 42):
        self.qfm = QuantumFeatureMap(NUMERIC_FEATURES)
        self.ohe = OneHotEncoder(handle_unknown="ignore")
        self.qiea = QIEAHyperparameterOptimizer(
            population_size=qiea_population, generations=qiea_generations,
            random_state=random_state,
        )
        self.model: XGBRegressor | None = None
        self.is_fitted = False
        self.metrics_: dict = {}
        self.best_hyperparams_: dict | None = None
        self.random_state = random_state

    def _build_matrix(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        if fit:
            q_feats = self.qfm.fit_transform(df)
            cat_feats = self.ohe.fit_transform(df[CATEGORICAL_FEATURES]).toarray()
        else:
            q_feats = self.qfm.transform(df)
            cat_feats = self.ohe.transform(df[CATEGORICAL_FEATURES]).toarray()
        return np.concatenate([q_feats, cat_feats], axis=1)

    def fit(self, df: pd.DataFrame, test_size: float = 0.2, qiea_cv_fraction: float = 0.3) -> dict:
        train_df, test_df = train_test_split(df, test_size=test_size, random_state=self.random_state)
        X_train = self._build_matrix(train_df, fit=True)
        y_train = train_df[TARGET].to_numpy()
        X_test = self._build_matrix(test_df, fit=False)
        y_test = test_df[TARGET].to_numpy()

        # Inner split for QIEA fitness evaluation (held-out test set stays untouched)
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=qiea_cv_fraction, random_state=self.random_state
        )

        def fitness_fn(params: dict) -> float:
            m = XGBRegressor(
                max_depth=params["max_depth"], learning_rate=params["learning_rate"],
                n_estimators=params["n_estimators"], subsample=0.9, colsample_bytree=0.9,
                random_state=self.random_state, n_jobs=-1, tree_method="hist",
                objective="reg:squarederror",
            )
            m.fit(X_tr, y_tr)
            preds = m.predict(X_val)
            return float(np.sqrt(mean_squared_error(y_val, preds)))

        best_params = self.qiea.optimize(fitness_fn)
        self.best_hyperparams_ = best_params

        self.model = XGBRegressor(
            max_depth=best_params["max_depth"], learning_rate=best_params["learning_rate"],
            n_estimators=best_params["n_estimators"], subsample=0.9, colsample_bytree=0.9,
            random_state=self.random_state, n_jobs=-1, tree_method="hist",
            objective="reg:squarederror",
        )
        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        self.metrics_ = {
            "mae": float(mean_absolute_error(y_test, preds)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
            "r2": float(r2_score(y_test, preds)),
            "n_test": int(len(y_test)),
            "best_hyperparams": best_params,
            "qiea_convergence": self.qiea.history_,
        }
        self.is_fitted = True
        return self.metrics_

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model not fitted or loaded yet.")
        X = self._build_matrix(df, fit=False)
        return self.model.predict(X)

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
            "qfm": self.qfm, "ohe": self.ohe, "model": self.model,
            "is_fitted": self.is_fitted, "metrics": self.metrics_,
            "best_hyperparams": self.best_hyperparams_,
        }, path)

    @classmethod
    def load(cls, path: str) -> "QuantumInspiredFuelModel":
        payload = joblib.load(path)
        obj = cls()
        obj.qfm = payload["qfm"]
        obj.ohe = payload["ohe"]
        obj.model = payload["model"]
        obj.is_fitted = payload["is_fitted"]
        obj.metrics_ = payload["metrics"]
        obj.best_hyperparams_ = payload["best_hyperparams"]
        return obj
