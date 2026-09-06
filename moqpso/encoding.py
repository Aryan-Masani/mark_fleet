"""
encoding.py — Particle encoding and greedy demand-matching decoder.
Implements Section 8 of SIH26138_D2_Mathematical_Formulation.md.

Particle Vector per vessel-route pair (v, r) in the candidate universe:
    [s_1,1, phi_1,1, s_1,2, phi_1,2, ..., s_v,r, phi_v,r, pi_1, ..., pi_Nv]

Where:
    - s_v,r in [s_min, s_max] (continuous cruising speed)
    - phi_v,r in [0, N_f] (continuous fuel relaxation, discretized as f* = floor(phi) clipped to [0, N_f - 1])
    - pi_v in [0, 1] (continuous priority scalar per vessel for greedy permutation decode)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Standard candidate fuel ordering matching Deliverable 1 and Deliverable 2
FUEL_TYPES: List[str] = ["HFO", "LNG", "Methanol", "Hydrogen", "Ammonia"]
N_FUELS: int = len(FUEL_TYPES)

# Default Well-to-Wake GHG Emission Factors (kg CO2eq per ton fuel burned)
DEFAULT_EMISSION_FACTORS: Dict[str, float] = {
    "HFO": 3114.0,
    "LNG": 2750.0,
    "Methanol": 1375.0,
    "Hydrogen": 0.0,
    "Ammonia": 0.0,
}

# Default Fuel Unit Costs (USD per ton)
DEFAULT_FUEL_COSTS: Dict[str, float] = {
    "HFO": 620.0,
    "LNG": 850.0,
    "Methanol": 1150.0,
    "Hydrogen": 2600.0,
    "Ammonia": 1850.0,
}


@dataclass
class VesselInfo:
    vessel_id: str
    vessel_type: str  # container, bulk_carrier, tanker, general_cargo
    displacement_tons: float
    capacity_tons: float  # Cap_v
    s_min: float = 10.0
    s_max: float = 24.0
    cii_target: float = 0.015  # kg CO2eq per (ton * nm), regulatory threshold
    fixed_fuel_override: Optional[str] = None  # for scenario testing


@dataclass
class RouteInfo:
    route_id: str
    origin_port: str
    destination_port: str
    distance_nm: float  # Dist_r
    demand_tons: float  # D_r
    eta_target_hours: float  # ETA_r^target
    wind_speed_knots: float = 10.0  # exogenous weather w_v,r
    wave_height_m: float = 1.2      # exogenous weather w_v,r


@dataclass
class VoyageAssignment:
    vessel_idx: int
    vessel_id: str
    vessel_type: str
    displacement_tons: float
    capacity_tons: float
    route_idx: int
    route_id: str
    origin_port: str
    destination_port: str
    distance_nm: float
    speed_knots: float
    fuel_idx: int
    fuel_type: str
    cargo_load_tons: float
    cargo_load_fraction: float
    transit_time_hours: float
    on_time: bool
    fuel_consumption_tons: float = 0.0
    fuel_cost: float = 0.0
    ghg_emissions_tons: float = 0.0
    cii_actual: float = 0.0


@dataclass
class DecodedPlan:
    assignments: List[VoyageAssignment] = field(default_factory=list)
    unassigned_vessel_indices: List[int] = field(default_factory=list)
    unmet_demand_per_route: Dict[str, float] = field(default_factory=dict)
    total_unmet_demand: float = 0.0
    fuel_availability_violations: int = 0
    cii_violations: int = 0
    raw_j1_cost: float = 0.0
    raw_j2_emissions: float = 0.0
    raw_j3_reliability: float = 0.0  # count of on-time voyages


class FleetEncoding:
    """Manages mapping between continuous particle vectors and fleet deployment plans."""

    def __init__(
        self,
        vessels: List[VesselInfo],
        routes: List[RouteInfo],
        port_fuel_avail: Optional[Dict[str, Dict[str, float]]] = None,
        fuel_costs: Optional[Dict[str, float]] = None,
        emission_factors: Optional[Dict[str, float]] = None,
    ):
        self.vessels = vessels
        self.routes = routes
        self.n_vessels = len(vessels)
        self.n_routes = len(routes)
        self.n_fuels = N_FUELS

        self.fuel_costs = fuel_costs or DEFAULT_FUEL_COSTS
        self.emission_factors = emission_factors or DEFAULT_EMISSION_FACTORS
        self.port_fuel_avail = port_fuel_avail or {}

        # Vector layout:
        # For each pair (v, r), 2 variables: [speed, continuous_fuel] -> 2 * n_vessels * n_routes
        # Followed by 1 priority variable per vessel: [pi_1, ..., pi_Nv] -> n_vessels
        self.pair_vars_count = 2 * self.n_vessels * self.n_routes
        self.total_dim = self.pair_vars_count + self.n_vessels

        # Precompute bounds
        self.lower_bounds: List[float] = []
        self.upper_bounds: List[float] = []
        self._build_bounds()

    def _build_bounds(self) -> None:
        self.lower_bounds = []
        self.upper_bounds = []

        # (v, r) pairs
        for v in range(self.n_vessels):
            vessel = self.vessels[v]
            for r in range(self.n_routes):
                # Speed variable s_v,r
                self.lower_bounds.append(float(vessel.s_min))
                self.upper_bounds.append(float(vessel.s_max))
                # Fuel relaxation phi_v,r in [0, N_f]
                self.lower_bounds.append(0.0)
                self.upper_bounds.append(float(self.n_fuels))

        # Priority variables pi_v in [0, 1]
        for v in range(self.n_vessels):
            self.lower_bounds.append(0.0)
            self.upper_bounds.append(1.0)

    def decode_assignments(self, vector: List[float] | np.ndarray) -> Tuple[List[VoyageAssignment], List[int], Dict[str, float]]:
        """
        Decodes continuous particle vector into vessel-to-route assignments using
        the greedy demand-matching rule from Section 8:
        1. Routes sorted in descending order of cargo demand D_r.
        2. For each route, unassigned vessels sorted by pi_v descending.
        3. Greedily assigned until route demand is satisfied or no vessels remain.
        4. Each vessel assigned to at most 1 route (single assignment by construction).
        """
        vec = np.asarray(vector, dtype=float)

        # Extract speeds and fuels: shape (n_vessels, n_routes, 2)
        pair_data = vec[:self.pair_vars_count].reshape(self.n_vessels, self.n_routes, 2)
        speeds = pair_data[:, :, 0]
        phis = pair_data[:, :, 1]

        # Discretize fuel: f* = floor(phi) clipped to [0, N_f - 1]
        fuel_indices = np.clip(np.floor(phis).astype(int), 0, self.n_fuels - 1)

        # Extract priorities: shape (n_vessels,)
        priorities = vec[self.pair_vars_count:self.pair_vars_count + self.n_vessels]

        # Greedy demand matching
        # Sort routes by demand descending
        sorted_route_indices = sorted(range(self.n_routes), key=lambda r: self.routes[r].demand_tons, reverse=True)
        unassigned_vessels = list(range(self.n_vessels))
        assignments: List[VoyageAssignment] = []
        unmet_demands: Dict[str, float] = {}

        for r_idx in sorted_route_indices:
            route = self.routes[r_idx]
            remaining_demand = float(route.demand_tons)

            # Sort available vessels by priority descending
            unassigned_vessels.sort(key=lambda v_idx: priorities[v_idx], reverse=True)

            assigned_for_route = []
            for v_idx in list(unassigned_vessels):
                if remaining_demand <= 1e-6:
                    break

                vessel = self.vessels[v_idx]
                # Single assignment: vessel assigned to this route
                cargo_carried = min(remaining_demand, float(vessel.capacity_tons))
                remaining_demand -= cargo_carried
                assigned_for_route.append(v_idx)
                unassigned_vessels.remove(v_idx)

                speed = float(np.clip(speeds[v_idx, r_idx], vessel.s_min, vessel.s_max))
                f_idx = int(fuel_indices[v_idx, r_idx])

                # Optional scenario override
                if vessel.fixed_fuel_override and vessel.fixed_fuel_override in FUEL_TYPES:
                    fuel_name = vessel.fixed_fuel_override
                    f_idx = FUEL_TYPES.index(fuel_name)
                else:
                    fuel_name = FUEL_TYPES[f_idx]

                transit_hours = float(route.distance_nm / speed) if speed > 0 else 9999.0
                on_time = bool(transit_hours <= route.eta_target_hours + 1e-6)
                load_fraction = float(cargo_carried / vessel.capacity_tons) if vessel.capacity_tons > 0 else 0.0

                assignment = VoyageAssignment(
                    vessel_idx=v_idx,
                    vessel_id=vessel.vessel_id,
                    vessel_type=vessel.vessel_type,
                    displacement_tons=float(vessel.displacement_tons),
                    capacity_tons=float(vessel.capacity_tons),
                    route_idx=r_idx,
                    route_id=route.route_id,
                    origin_port=route.origin_port,
                    destination_port=route.destination_port,
                    distance_nm=float(route.distance_nm),
                    speed_knots=speed,
                    fuel_idx=f_idx,
                    fuel_type=fuel_name,
                    cargo_load_tons=cargo_carried,
                    cargo_load_fraction=load_fraction,
                    transit_time_hours=transit_hours,
                    on_time=on_time,
                )
                assignments.append(assignment)

            unmet_demands[route.route_id] = max(0.0, remaining_demand)

        return assignments, unassigned_vessels, unmet_demands
