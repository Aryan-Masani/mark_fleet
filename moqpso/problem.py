"""
problem.py — FleetOptimizationProblem implementing the jMetalPy FloatProblem interface.
Implements Sections 5, 6, and 7 of SIH26138_D2_Mathematical_Formulation.md.

Objectives:
    J1: Total Fuel Cost (USD)
    J2: Total Lifecycle GHG Emissions (kg CO2eq)
    J3: Negated Schedule Reliability (- count of on-time voyages, minimizing maximizes on-time arrivals)

Constraint Penalties (Section 7):
    Fitness_i = J_i + lambda * sum_k max(0, g_k)^2
    - g_r (Demand satisfaction): D_r - sum_v x_v,r * Cap_v (only fires if greedy decode under-assigns)
    - g_v,r (Fuel availability): y_v,r,f* - Avail_{f*, port(r)}
    - g_v (CII compliance): [sum FĈ * EF_f / sum Cap_v * Dist_r] - CII_v
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from jmetal.core.problem import FloatProblem
from jmetal.core.solution import FloatSolution

from .encoding import FleetEncoding, VesselInfo, RouteInfo, DecodedPlan, VoyageAssignment
from .fitness_adapter import FitnessAdapter


class FleetOptimizationProblem(FloatProblem):
    """
    Fleet Optimization Problem adhering to jMetalPy's FloatProblem interface.
    Evaluates particle solutions by decoding assignments and querying D1 FuelPredictor.
    """

    def __init__(
        self,
        vessels: List[VesselInfo],
        routes: List[RouteInfo],
        fitness_adapter: Optional[FitnessAdapter] = None,
        port_fuel_avail: Optional[Dict[str, Dict[str, float]]] = None,
        fuel_costs: Optional[Dict[str, float]] = None,
        emission_factors: Optional[Dict[str, float]] = None,
        initial_lambda: float = 1000.0,
        max_lambda: float = 50000.0,
    ):
        super().__init__()
        self.vessels = vessels
        self.routes = routes
        self.fitness_adapter = fitness_adapter or FitnessAdapter(model_type="quantum")
        self.encoding = FleetEncoding(
            vessels=vessels,
            routes=routes,
            port_fuel_avail=port_fuel_avail,
            fuel_costs=fuel_costs,
            emission_factors=emission_factors,
        )

        self.lower_bound = self.encoding.lower_bounds
        self.upper_bound = self.encoding.upper_bounds

        # Annealed penalty parameters
        self.initial_lambda = initial_lambda
        self.max_lambda = max_lambda
        self.current_lambda = initial_lambda

        # Problem metadata for jMetalPy
        self.obj_directions = [self.MINIMIZE, self.MINIMIZE, self.MINIMIZE]
        self.obj_labels = ["Total Fuel Cost ($)", "Total GHG Emissions (kg CO2eq)", "Negated Schedule Reliability"]

    def number_of_variables(self) -> int:
        return self.encoding.total_dim

    def number_of_objectives(self) -> int:
        return 3

    def number_of_constraints(self) -> int:
        # Constraints are handled via Section 7 penalty formulation
        return 0

    def name(self) -> str:
        return f"FleetOptimization_{len(self.vessels)}V_{len(self.routes)}R"

    def set_annealed_lambda(self, progress_fraction: float) -> None:
        """Dynamically anneal penalty coefficient lambda over optimization run."""
        frac = max(0.0, min(1.0, progress_fraction))
        self.current_lambda = self.initial_lambda + frac * (self.max_lambda - self.initial_lambda)

    def evaluate_vector(self, variables: List[float] | np.ndarray) -> DecodedPlan:
        """
        Decodes variables and evaluates all objectives and constraints.
        Returns a DecodedPlan containing assignments and metrics.
        """
        assignments, unassigned_vessels, unmet_demands = self.encoding.decode_assignments(variables)

        total_cost = 0.0
        total_emissions = 0.0
        on_time_count = 0.0

        fuel_avail_violations = 0
        cii_violations = 0
        total_squared_penalties = 0.0

        # Group assignments by vessel for CII calculation
        vessel_voyages: Dict[int, List[VoyageAssignment]] = {v: [] for v in range(len(self.vessels))}

        for asgn in assignments:
            route = self.routes[asgn.route_idx]
            # Exogenous weather for route
            wind = route.wind_speed_knots
            wave = route.wave_height_m

            # Call D1 FuelPredictor
            fuel_tons = self.fitness_adapter.predict_fuel(
                vessel_type=asgn.vessel_type,
                fuel_type=asgn.fuel_type,
                displacement_tons=asgn.displacement_tons,
                cargo_load_fraction=asgn.cargo_load_fraction,
                speed_knots=asgn.speed_knots,
                wind_speed_knots=wind,
                wave_height_m=wave,
                distance_nm=asgn.distance_nm,
            )
            asgn.fuel_consumption_tons = fuel_tons

            # Unit cost & emission factor
            unit_cost = self.encoding.fuel_costs.get(asgn.fuel_type, 700.0)
            ef_factor = self.encoding.emission_factors.get(asgn.fuel_type, 3000.0)

            cost = fuel_tons * unit_cost
            emissions = fuel_tons * ef_factor

            asgn.fuel_cost = cost
            asgn.ghg_emissions_tons = emissions / 1000.0  # tons CO2eq

            total_cost += cost
            total_emissions += emissions  # in kg CO2eq per D2 EF_f unit
            if asgn.on_time:
                on_time_count += 1.0

            # Constraint: Fuel Availability at origin port
            # g_v,r = y_v,r,f* - Avail_{f*, port(r)}
            port_avail = self.encoding.port_fuel_avail.get(asgn.origin_port, {})
            avail = port_avail.get(asgn.fuel_type, 1.0)  # default 1.0 if not constrained
            if avail < 1.0:
                violation = 1.0 - avail
                fuel_avail_violations += 1
                total_squared_penalties += (violation * 10.0) ** 2

            vessel_voyages[asgn.vessel_idx].append(asgn)

        # Constraint: Demand Satisfaction
        # g_r = D_r - sum_v x_v,r * Cap_v
        total_unmet = 0.0
        for r_id, unmet in unmet_demands.items():
            if unmet > 1e-4:
                total_unmet += unmet
                # Normalized penalty per route
                r_obj = next(r for r in self.routes if r.route_id == r_id)
                deficit_ratio = unmet / max(1.0, r_obj.demand_tons)
                total_squared_penalties += (deficit_ratio * 100.0) ** 2

        # Constraint: CII Compliance per vessel
        for v_idx, asgns in vessel_voyages.items():
            if not asgns:
                continue
            vessel = self.vessels[v_idx]
            total_v_emissions = sum(a.fuel_consumption_tons * self.encoding.emission_factors.get(a.fuel_type, 3000.0) for a in asgns)
            total_v_transport_work = sum(a.capacity_tons * a.distance_nm for a in asgns)

            actual_cii = total_v_emissions / max(1.0, total_v_transport_work)
            for a in asgns:
                a.cii_actual = actual_cii

            if actual_cii > vessel.cii_target:
                cii_violations += 1
                cii_excess = (actual_cii - vessel.cii_target) / vessel.cii_target
                total_squared_penalties += (cii_excess * 10.0) ** 2

        plan = DecodedPlan(
            assignments=assignments,
            unassigned_vessel_indices=unassigned_vessels,
            unmet_demand_per_route=unmet_demands,
            total_unmet_demand=total_unmet,
            fuel_availability_violations=fuel_avail_violations,
            cii_violations=cii_violations,
            raw_j1_cost=total_cost,
            raw_j2_emissions=total_emissions,
            raw_j3_reliability=on_time_count,
        )
        plan._penalty_term = self.current_lambda * total_squared_penalties
        return plan

    def evaluate(self, solution: FloatSolution) -> FloatSolution:
        plan = self.evaluate_vector(solution.variables)
        penalty = getattr(plan, "_penalty_term", 0.0)

        # Section 5.4 / Section 7:
        # Fitness = J + lambda * sum max(0, g_k)^2
        # jMetalPy minimizes all objectives
        solution.objectives[0] = plan.raw_j1_cost + penalty
        solution.objectives[1] = plan.raw_j2_emissions + penalty
        # -J3 since schedule reliability is maximized
        solution.objectives[2] = (-plan.raw_j3_reliability) + penalty

        # Store rich details in attributes for MOQPSO and dashboard
        solution.attributes["plan"] = plan
        solution.attributes["raw_j1"] = plan.raw_j1_cost
        solution.attributes["raw_j2"] = plan.raw_j2_emissions
        solution.attributes["raw_j3"] = plan.raw_j3_reliability
        solution.attributes["unmet_demand"] = plan.total_unmet_demand
        solution.attributes["fuel_violations"] = plan.fuel_availability_violations
        solution.attributes["cii_violations"] = plan.cii_violations
        return solution
