"""
models.py — Pydantic request/response schemas for Maritime Q FastAPI backend.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────────────────

class PortFuelAvailability(BaseModel):
    HFO: float = 1.0
    LNG: float = 1.0
    Methanol: float = 1.0
    Hydrogen: float = 0.0
    Ammonia: float = 0.0


class OptimizationRequest(BaseModel):
    fleet_size: int = Field(5, ge=3, le=8)
    n_routes: int = Field(3, ge=2, le=5)
    swarm_size: int = Field(30, ge=15, le=60)
    max_evaluations: int = Field(900, ge=300, le=2000)
    model_type: str = Field("quantum", pattern="^(quantum|baseline)$")
    seed: int = 42
    run_nsga2: bool = True
    cii_stringency: float = Field(1.0, ge=0.7, le=1.3)
    fuel_override_mode: str = "Pareto Multi-Fuel Free Choice (Optimizer Selects)"
    port_fuel_avail: Dict[str, PortFuelAvailability] = {}
    shore_power: Dict[str, bool] = {}


# ── Response Models ─────────────────────────────────────────────────────────

class VoyageAssignmentOut(BaseModel):
    vessel_id: str
    vessel_type: str
    route_id: str
    origin_port: str
    destination_port: str
    speed_knots: float
    fuel_type: str
    cargo_load_tons: float
    cargo_load_fraction: float
    transit_time_hours: float
    on_time: bool
    fuel_consumption_tons: float
    fuel_cost: float
    ghg_emissions_tons: float
    cii_actual: float


class ParetoSolutionOut(BaseModel):
    index: int
    cost_usd: float
    ghg_tons: float
    on_time_legs: float
    reliability_pct: float
    unmet_demand: float
    cii_violations: int
    fuel_violations: int
    assignments: List[VoyageAssignmentOut]
    # Derived KPIs
    raw_j1_cost: float
    raw_j2_emissions: float
    raw_j3_reliability: float
    green_share_pct: float
    green_cargo_tons: float


class Nsga2PointOut(BaseModel):
    cost_usd: float
    ghg_tons: float


class OptimizationResult(BaseModel):
    run_id: str
    moqpso_time_s: float
    pareto_solutions: List[ParetoSolutionOut]
    nsga2_points: Optional[List[Nsga2PointOut]] = None
    nsga2_min_cost: Optional[float] = None
    nsga2_min_ghg: Optional[float] = None
    nsga2_count: Optional[int] = None
    scenario_params: Dict[str, str] = {}
    vessels: List[Dict] = []
    routes: List[Dict] = []


class RunStarted(BaseModel):
    run_id: str
    message: str = "Optimization started"


class HealthResponse(BaseModel):
    status: str = "ok"
    streamlit_port: int = 8502
    api_port: int = 8000
