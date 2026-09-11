"""
main.py — FastAPI backend for Maritime Q Green Fleet Optimization Dashboard.
Runs on port 8000. Streamlit stays on 8502.

Endpoints:
  GET  /api/health
  GET  /api/default-scenario
  POST /api/run-optimization     → { run_id }
  GET  /api/stream/{run_id}      → SSE progress + completion event
  GET  /api/results/{run_id}     → full OptimizationResult JSON
  GET  /api/report/pdf/{run_id}/{sol_idx}
  GET  /api/report/markdown/{run_id}/{sol_idx}
"""

from __future__ import annotations
import asyncio
import json
import os
import random
import sys
import time
import threading
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

# ── sys.path setup ──────────────────────────────────────────────────────────
_API_DIR = os.path.dirname(os.path.abspath(__file__))
# Ensure our api/ dir is first so "models" resolves to our local models.py
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)
_WEBAPP_DIR = os.path.abspath(os.path.join(_API_DIR, ".."))
_FLEET_ROOT = os.path.abspath(os.path.join(_WEBAPP_DIR, ".."))

for _p in [_FLEET_ROOT, os.path.join(_FLEET_ROOT, "fuel_prediction", "fuel_prediction")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from moqpso.encoding import (
    VesselInfo, RouteInfo, FUEL_TYPES,
    DEFAULT_FUEL_COSTS, DEFAULT_EMISSION_FACTORS,
)
from moqpso.fitness_adapter import FitnessAdapter
from moqpso.problem import FleetOptimizationProblem
from moqpso.moqpso import MOQPSO
from dashboard.report import generate_pdf_report, generate_markdown_report

from pymoo.core.problem import Problem as PymooProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize as pymoo_minimize

from models import (
    OptimizationRequest, OptimizationResult, RunStarted,
    HealthResponse, ParetoSolutionOut, VoyageAssignmentOut,
    Nsga2PointOut,
)

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Maritime Q — Green Fleet Optimization API",
    description="FastAPI backend for the MOQPSO multi-objective green fleet optimizer.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory store ─────────────────────────────────────────────────────────
# run_id -> { "status": "running"|"done"|"error", "result": OptimizationResult | None, "progress": [...] }
_runs: Dict[str, Dict[str, Any]] = {}


# ── Helpers ─────────────────────────────────────────────────────────────────

PRESET_VESSELS = [
    VesselInfo("V1_Container_L",   "container",    85000, 50000, 12.0, 22.0, 0.013),
    VesselInfo("V2_Container_M",   "container",    55000, 32000, 12.0, 22.0, 0.015),
    VesselInfo("V3_Bulk_Carrier",  "bulk_carrier", 95000, 65000, 10.0, 17.0, 0.010),
    VesselInfo("V4_Tanker",        "tanker",      130000, 85000, 11.0, 18.0, 0.011),
    VesselInfo("V5_General_Cargo", "general_cargo",22000, 15000, 10.0, 19.0, 0.017),
    VesselInfo("V6_Container_Feed","container",    35000, 20000, 12.0, 20.0, 0.016),
    VesselInfo("V7_Handysize_Bulk","bulk_carrier", 45000, 30000, 10.0, 16.0, 0.012),
    VesselInfo("V8_Chem_Tanker",   "tanker",       50000, 32000, 11.0, 17.0, 0.013),
]

PRESET_ROUTES = [
    RouteInfo("R1_Sha_Sin", "Shanghai",  "Singapore",  2250.0, 45000.0, 150.0, 12.0, 1.5),
    RouteInfo("R2_Rot_NYC", "Rotterdam", "New York",   3400.0, 60000.0, 210.0, 16.0, 2.1),
    RouteInfo("R3_Sin_Dub", "Singapore", "Dubai",      3650.0, 50000.0, 240.0, 11.0, 1.2),
    RouteInfo("R4_Yok_LA",  "Yokohama",  "Los Angeles",4800.0, 55000.0, 280.0, 15.0, 2.0),
    RouteInfo("R5_Ant_San", "Antwerp",   "Santos",     5600.0, 65000.0, 320.0, 14.0, 1.8),
]


def _build_scenario(req: OptimizationRequest):
    import copy
    fleet_size = max(2, min(len(PRESET_VESSELS), req.fleet_size))
    n_routes   = max(1, min(len(PRESET_ROUTES),  req.n_routes))
    vessels = [copy.copy(v) for v in PRESET_VESSELS[:fleet_size]]
    routes  = list(PRESET_ROUTES[:n_routes])

    # CII stringency
    for v in vessels:
        v.cii_target *= req.cii_stringency

    # Fuel policy override
    mode = req.fuel_override_mode
    if "Zero-Carbon" in mode:
        for v in vessels:
            v.fixed_fuel_override = random.choice(["Hydrogen", "Ammonia"])
    elif "LNG" in mode:
        for v in vessels:
            v.fixed_fuel_override = "LNG"
    elif "Methanol" in mode:
        for v in vessels:
            v.fixed_fuel_override = "Methanol"
    elif "Conventional HFO" in mode:
        for v in vessels:
            v.fixed_fuel_override = "HFO"

    # Port fuel availability
    ports = list(set([r.origin_port for r in routes] + [r.destination_port for r in routes]))
    port_fuel_avail: Dict[str, Dict[str, float]] = {}
    for port in ports:
        if port in req.port_fuel_avail:
            pfa = req.port_fuel_avail[port]
            port_fuel_avail[port] = {
                "HFO": pfa.HFO, "LNG": pfa.LNG, "Methanol": pfa.Methanol,
                "Hydrogen": pfa.Hydrogen, "Ammonia": pfa.Ammonia,
            }
        else:
            port_fuel_avail[port] = {"HFO": 1.0, "LNG": 1.0, "Methanol": 1.0, "Hydrogen": 0.0, "Ammonia": 0.0}

    return vessels, routes, ports, port_fuel_avail


class _PymooAdapter(PymooProblem):
    def __init__(self, fleet_problem: FleetOptimizationProblem):
        self.fleet_problem = fleet_problem
        n_vars = fleet_problem.number_of_variables()
        xl = np.array(fleet_problem.lower_bound, dtype=float)
        xu = np.array(fleet_problem.upper_bound, dtype=float)
        super().__init__(n_var=n_vars, n_obj=3, n_constr=0, xl=xl, xu=xu)

    def _evaluate(self, X, out, *args, **kwargs):
        F = []
        for x in X:
            plan = self.fleet_problem.evaluate_vector(x)
            penalty = getattr(plan, "_penalty_term", 0.0)
            F.append([
                plan.raw_j1_cost + penalty,
                plan.raw_j2_emissions + penalty,
                (-plan.raw_j3_reliability) + penalty,
            ])
        out["F"] = np.array(F, dtype=float)


def _sol_to_out(i: int, sol, routes: List[RouteInfo]) -> ParetoSolutionOut:
    j1 = sol.attributes.get("raw_j1", sol.objectives[0])
    j2 = sol.attributes.get("raw_j2", sol.objectives[1]) / 1000.0
    j3 = sol.attributes.get("raw_j3", -sol.objectives[2])
    plan = sol.attributes["plan"]

    green_fuels = {"Hydrogen", "Ammonia", "Methanol", "LNG"}
    green_cargo = sum(a.cargo_load_tons for a in plan.assignments if a.fuel_type in green_fuels)
    total_cargo = max(1.0, sum(a.cargo_load_tons for a in plan.assignments))

    assignments = [
        VoyageAssignmentOut(
            vessel_id=a.vessel_id,
            vessel_type=a.vessel_type,
            route_id=a.route_id,
            origin_port=a.origin_port,
            destination_port=a.destination_port,
            speed_knots=round(a.speed_knots, 2),
            fuel_type=a.fuel_type,
            cargo_load_tons=round(a.cargo_load_tons, 2),
            cargo_load_fraction=round(a.cargo_load_fraction, 4),
            transit_time_hours=round(a.transit_time_hours, 2),
            on_time=a.on_time,
            fuel_consumption_tons=round(a.fuel_consumption_tons, 3),
            fuel_cost=round(a.fuel_cost, 2),
            ghg_emissions_tons=round(a.ghg_emissions_tons, 3),
            cii_actual=round(a.cii_actual * 1000.0, 4),
        )
        for a in plan.assignments
    ]

    return ParetoSolutionOut(
        index=i,
        cost_usd=round(j1, 2),
        ghg_tons=round(j2, 3),
        on_time_legs=round(j3, 1),
        reliability_pct=round((j3 / max(1, len(routes))) * 100.0, 1),
        unmet_demand=round(sol.attributes.get("unmet_demand", 0.0), 2),
        cii_violations=int(sol.attributes.get("cii_violations", 0)),
        fuel_violations=int(sol.attributes.get("fuel_violations", 0)),
        assignments=assignments,
        raw_j1_cost=round(plan.raw_j1_cost, 2),
        raw_j2_emissions=round(plan.raw_j2_emissions, 2),
        raw_j3_reliability=round(plan.raw_j3_reliability, 2),
        green_share_pct=round((green_cargo / total_cargo) * 100.0, 1),
        green_cargo_tons=round(green_cargo, 2),
    )


def _run_optimization_thread(run_id: str, req: OptimizationRequest):
    """Runs in a background thread; writes progress events and final result to _runs."""
    store = _runs[run_id]

    def _push(msg: str, pct: int):
        store["progress"].append({"pct": pct, "msg": msg})

    try:
        random.seed(req.seed)
        np.random.seed(req.seed)

        _push("Building scenario...", 2)
        vessels, routes, ports, port_fuel_avail = _build_scenario(req)

        _push("Initializing Quantum Swarm & Leader Archive...", 5)
        adapter = FitnessAdapter(model_type=req.model_type)
        problem = FleetOptimizationProblem(
            vessels=vessels,
            routes=routes,
            fitness_adapter=adapter,
            port_fuel_avail=port_fuel_avail,
            initial_lambda=100.0,
            max_lambda=5000.0,
        )

        def _step_cb(evals, max_e, leaders):
            pct = min(80, 5 + int((evals / max_e) * 75))
            _push(f"MOQPSO: {evals}/{max_e} evals | {len(leaders)} non-dominated leaders", pct)

        moqpso = MOQPSO(
            problem=problem,
            swarm_size=req.swarm_size,
            max_evaluations=req.max_evaluations,
            beta_max=1.0,
            beta_min=0.4,
            step_callback=_step_cb,
        )

        t0 = time.time()
        moqpso.run()
        moqpso_time = time.time() - t0

        _push("MOQPSO complete. Extracting Pareto front...", 82)
        pareto_solutions = moqpso.get_pareto_front()
        pareto_out = [_sol_to_out(i, sol, routes) for i, sol in enumerate(pareto_solutions)]

        # NSGA-II comparison
        nsga2_points, nsga2_min_cost, nsga2_min_ghg, nsga2_count = None, None, None, None
        if req.run_nsga2:
            _push("Running Classical NSGA-II Baseline (pymoo)...", 85)
            pymoo_prob = _PymooAdapter(problem)
            nsga2 = NSGA2(pop_size=req.swarm_size)
            n_gen = max(5, req.max_evaluations // req.swarm_size)
            res = pymoo_minimize(pymoo_prob, nsga2, ("n_gen", n_gen), seed=req.seed, verbose=False)
            F = res.F
            nsga2_points = [Nsga2PointOut(cost_usd=float(row[0]), ghg_tons=float(row[1]) / 1000.0) for row in F]
            nsga2_min_cost = float(F[:, 0].min())
            nsga2_min_ghg  = float(F[:, 1].min() / 1000.0)
            nsga2_count    = len(F)

        _push("Done!", 100)

        scenario_params = {
            "Prediction Model": "Quantum-Inspired QIEA" if req.model_type == "quantum" else "Classical XGBoost",
            "Swarm Size": str(req.swarm_size),
            "Evaluations": str(req.max_evaluations),
            "Fuel Availability Policy": "Port-specific bunkering constraints",
            "Shore Power Berth Toggles": f"{sum(req.shore_power.values())}/{len(ports)} ports enabled",
            "Fuel Override Mode": req.fuel_override_mode,
            "CII Stringency Factor": f"{req.cii_stringency:.2f}x",
        }

        result = OptimizationResult(
            run_id=run_id,
            moqpso_time_s=round(moqpso_time, 2),
            pareto_solutions=pareto_out,
            nsga2_points=nsga2_points,
            nsga2_min_cost=nsga2_min_cost,
            nsga2_min_ghg=nsga2_min_ghg,
            nsga2_count=nsga2_count,
            scenario_params=scenario_params,
            vessels=[{"id": v.vessel_id, "type": v.vessel_type, "capacity": v.capacity_tons} for v in vessels],
            routes=[{"id": r.route_id, "origin": r.origin_port, "dest": r.destination_port, "demand": r.demand_tons} for r in routes],
        )

        store["result"] = result
        store["status"] = "done"
        # store vessels/routes/plan objects for report generation
        store["_vessels"] = vessels
        store["_routes"] = routes
        store["_pareto_raw"] = pareto_solutions

    except Exception as exc:
        store["status"] = "error"
        store["error"] = str(exc)
        store["progress"].append({"pct": -1, "msg": f"ERROR: {exc}"})


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.get("/api/default-scenario")
def default_scenario(fleet_size: int = 5, n_routes: int = 3):
    import copy
    fleet_size = max(2, min(len(PRESET_VESSELS), fleet_size))
    n_routes   = max(1, min(len(PRESET_ROUTES),  n_routes))
    vessels = [copy.copy(v) for v in PRESET_VESSELS[:fleet_size]]
    routes  = list(PRESET_ROUTES[:n_routes])
    ports = list(set([r.origin_port for r in routes] + [r.destination_port for r in routes]))

    return {
        "vessels": [
            {"id": v.vessel_id, "type": v.vessel_type,
             "displacement": v.displacement_tons, "capacity": v.capacity_tons,
             "s_min": v.s_min, "s_max": v.s_max, "cii_target": v.cii_target}
            for v in vessels
        ],
        "routes": [
            {"id": r.route_id, "origin": r.origin_port, "dest": r.destination_port,
             "distance_nm": r.distance_nm, "demand_tons": r.demand_tons,
             "eta_hours": r.eta_target_hours, "wind": r.wind_speed_knots, "wave": r.wave_height_m}
            for r in routes
        ],
        "ports": ports,
        "total_capacity": sum(v.capacity_tons for v in vessels),
        "total_demand": sum(r.demand_tons for r in routes),
    }


@app.post("/api/run-optimization", response_model=RunStarted)
def run_optimization(req: OptimizationRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"status": "running", "result": None, "progress": [], "error": None}
    background_tasks.add_task(_run_optimization_thread, run_id, req)
    return RunStarted(run_id=run_id)


@app.get("/api/stream/{run_id}")
async def stream_progress(run_id: str):
    """Server-Sent Events endpoint: streams progress then completion."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="run_id not found")

    async def _generator():
        sent = 0
        while True:
            store = _runs[run_id]
            events = store["progress"]
            while sent < len(events):
                evt = events[sent]
                yield f"data: {json.dumps(evt)}\n\n"
                sent += 1

            if store["status"] == "done":
                yield f"data: {json.dumps({'pct': 100, 'msg': 'complete', 'done': True})}\n\n"
                break
            elif store["status"] == "error":
                yield f"data: {json.dumps({'pct': -1, 'msg': store['error'], 'error': True})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/results/{run_id}", response_model=OptimizationResult)
def get_results(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="run_id not found")
    store = _runs[run_id]
    if store["status"] == "running":
        raise HTTPException(status_code=202, detail="Optimization still running")
    if store["status"] == "error":
        raise HTTPException(status_code=500, detail=store["error"])
    return store["result"]


@app.get("/api/report/pdf/{run_id}/{sol_idx}")
def get_pdf_report(run_id: str, sol_idx: int):
    if run_id not in _runs or _runs[run_id]["status"] != "done":
        raise HTTPException(status_code=404, detail="Results not available")
    store = _runs[run_id]
    result: OptimizationResult = store["result"]
    if sol_idx < 0 or sol_idx >= len(result.pareto_solutions):
        raise HTTPException(status_code=400, detail="Invalid solution index")

    pareto_raw = store["_pareto_raw"]
    vessels    = store["_vessels"]
    routes     = store["_routes"]
    plan       = pareto_raw[sol_idx].attributes["plan"]

    scenario_params = result.scenario_params
    pdf_bytes = generate_pdf_report(sol_idx, plan, vessels, routes, scenario_params)

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Fleet_Solution_{sol_idx+1}.pdf"'},
    )


@app.get("/api/report/markdown/{run_id}/{sol_idx}")
def get_markdown_report(run_id: str, sol_idx: int):
    if run_id not in _runs or _runs[run_id]["status"] != "done":
        raise HTTPException(status_code=404, detail="Results not available")
    store = _runs[run_id]
    result: OptimizationResult = store["result"]
    if sol_idx < 0 or sol_idx >= len(result.pareto_solutions):
        raise HTTPException(status_code=400, detail="Invalid solution index")

    pareto_raw = store["_pareto_raw"]
    vessels    = store["_vessels"]
    routes     = store["_routes"]
    plan       = pareto_raw[sol_idx].attributes["plan"]

    md = generate_markdown_report(sol_idx, plan, vessels, routes, result.scenario_params)

    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="Fleet_Solution_{sol_idx+1}.md"'},
    )
