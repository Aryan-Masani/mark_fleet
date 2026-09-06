"""
Synthetic vessel fuel-consumption data generator.

Physics-based synthetic data generator for the SIH26138 Green Fleet
Optimization project (supports Deliverable 1 — Fuel Consumption
Prediction Model).

The generator produces synthetic voyage-leg records using a
simplified Admiralty-formula-based propulsion power model, adjusted
for cargo load, weather resistance, and fuel-type-specific mass and
emission factors.

IMPORTANT: all physical constants below (hull-efficiency constants,
SFOC baseline, fuel mass multipliers, emission factors) are
ILLUSTRATIVE PLACEHOLDERS suitable for prototyping a prediction
pipeline. They are NOT validated engineering data. Replace them with
class-society / manufacturer / IMO figures before any real-world use.

Exports
-------
generate_synthetic_fleet_data(n_samples, seed) -> pd.DataFrame
    Synthetic voyage records with fuel consumption and CO2-equivalent
    emissions computed per record.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

# --- Vessel type hull-efficiency constants (illustrative placeholders) ---
VESSEL_TYPES = {
    "container":     {"k_hull": 0.00450, "base_displacement_range": (15000, 150000)},
    "bulk_carrier":  {"k_hull": 0.00390, "base_displacement_range": (20000, 200000)},
    "tanker":        {"k_hull": 0.00410, "base_displacement_range": (25000, 300000)},
    "general_cargo": {"k_hull": 0.00470, "base_displacement_range": (5000, 40000)},
}

# --- Fuel-type mass multiplier (relative to HFO, for equal energy delivered)
# and well-to-wake emission factor (kg CO2-equivalent per kg fuel burned).
# Illustrative placeholders — swap in validated LCA figures for production.
FUEL_TYPES = {
    "HFO":      {"mass_multiplier": 1.00, "co2_factor": 3.114, "availability_weight": 1.0},
    "LNG":      {"mass_multiplier": 0.90, "co2_factor": 2.750, "availability_weight": 0.6},
    "Methanol": {"mass_multiplier": 1.90, "co2_factor": 1.375, "availability_weight": 0.4},
    "Hydrogen": {"mass_multiplier": 0.33, "co2_factor": 0.000, "availability_weight": 0.15},
    "Ammonia":  {"mass_multiplier": 1.80, "co2_factor": 0.000, "availability_weight": 0.2},
}

BASELINE_SFOC_G_PER_KWH = 180.0  # baseline specific fuel oil consumption, HFO reference


def _sample_vessel(rng: np.random.Generator) -> dict:
    vtype = rng.choice(list(VESSEL_TYPES.keys()))
    lo, hi = VESSEL_TYPES[vtype]["base_displacement_range"]
    displacement = rng.uniform(lo, hi)
    return {"vessel_type": vtype, "displacement_tons": displacement}


def _sample_fuel(rng: np.random.Generator) -> str:
    fuels = list(FUEL_TYPES.keys())
    weights = np.array([FUEL_TYPES[f]["availability_weight"] for f in fuels])
    weights = weights / weights.sum()
    return rng.choice(fuels, p=weights)


def generate_synthetic_fleet_data(n_samples: int = 15000, seed: int = 42) -> pd.DataFrame:
    """
    Generate a synthetic fleet fuel-consumption dataset.

    Parameters
    ----------
    n_samples : int
        Number of voyage-leg records to generate.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    pd.DataFrame with columns:
        vessel_type, displacement_tons, cargo_load_fraction,
        speed_knots, wind_speed_knots, wave_height_m, fuel_type,
        distance_nm, fuel_consumption_tons, co2_emissions_tons
    """
    rng = np.random.default_rng(seed)
    records = []

    for _ in range(n_samples):
        vessel = _sample_vessel(rng)
        load_fraction = float(np.clip(rng.beta(2, 2), 0.05, 1.0))
        speed = float(rng.uniform(10, 24))                       # knots
        wind_speed = float(rng.gamma(2.0, 4.0))                  # knots, right-skewed
        wave_height = float(np.clip(rng.gamma(1.5, 0.8), 0, 8))  # meters
        fuel_type = _sample_fuel(rng)
        distance = float(rng.uniform(200, 8000))                 # nautical miles

        effective_displacement = vessel["displacement_tons"] * (1 + 0.15 * load_fraction)
        weather_multiplier = 1 + 0.015 * wind_speed + 0.05 * wave_height
        k_hull = VESSEL_TYPES[vessel["vessel_type"]]["k_hull"]

        # Simplified Admiralty-formula-based propulsion power (kW)
        base_power_kw = k_hull * (effective_displacement ** (2 / 3)) * (speed ** 3) * weather_multiplier

        fuel_props = FUEL_TYPES[fuel_type]
        sfoc_effective = BASELINE_SFOC_G_PER_KWH * fuel_props["mass_multiplier"]

        voyage_hours = distance / max(speed, 1e-6)
        fuel_kg = base_power_kw * sfoc_effective * voyage_hours / 1000.0
        fuel_tons = fuel_kg / 1000.0

        # Measurement / operational noise
        fuel_tons *= float(np.clip(rng.normal(1.0, 0.04), 0.85, 1.15))

        co2_tons = fuel_tons * fuel_props["co2_factor"]

        records.append({
            "vessel_type": vessel["vessel_type"],
            "displacement_tons": round(vessel["displacement_tons"], 1),
            "cargo_load_fraction": round(load_fraction, 3),
            "speed_knots": round(speed, 2),
            "wind_speed_knots": round(wind_speed, 2),
            "wave_height_m": round(wave_height, 2),
            "fuel_type": fuel_type,
            "distance_nm": round(distance, 1),
            "fuel_consumption_tons": round(fuel_tons, 4),
            "co2_emissions_tons": round(co2_tons, 4),
        })

    return pd.DataFrame.from_records(records)


if __name__ == "__main__":
    df = generate_synthetic_fleet_data(15000, seed=42)
    df.to_csv("synthetic_fleet_data.csv", index=False)
    print(f"Generated {len(df)} rows -> synthetic_fleet_data.csv")
    print(df.describe(include="all").T)
