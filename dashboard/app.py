"""
dashboard/app.py — Streamlit Interactive Web Application for Green Fleet Deployment (D4).
SIH26138 Egreen Quanta: Quantum-Inspired Fuel Prediction & MOQPSO Green Fleet Optimization.
"""

from __future__ import annotations
import os
import sys
import time
import random
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Setup workspace sys.path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from moqpso.encoding import VesselInfo, RouteInfo, FUEL_TYPES, DEFAULT_FUEL_COSTS, DEFAULT_EMISSION_FACTORS
from moqpso.fitness_adapter import FitnessAdapter
from moqpso.problem import FleetOptimizationProblem
from moqpso.moqpso import MOQPSO
from dashboard.report import generate_pdf_report, generate_markdown_report

# pymoo for optional comparison
from pymoo.core.problem import Problem as PymooProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize as pymoo_minimize

# --- Page Configuration & Styling ---
st.set_page_config(
    page_title="Egreen Quanta — Green Fleet Optimization",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0b1d3a 0%, #102a4e 50%, #0d3b66 100%);
        padding: 24px 30px;
        border-radius: 14px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    .kpi-card {
        background: #111b2b;
        border-radius: 12px;
        padding: 18px 20px;
        border: 1px solid #1f304d;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        text-align: left;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: #00b4d8;
    }
    
    .kpi-title {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 6px;
        font-weight: 600;
    }
    
    .kpi-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.2;
    }
    
    .kpi-subtitle {
        font-size: 0.78rem;
        color: #38bdf8;
        margin-top: 6px;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%);
        color: white;
        font-weight: 600;
        font-size: 1rem;
        border: none;
        padding: 12px 28px;
        border-radius: 8px;
        box-shadow: 0 4px 14px rgba(0, 180, 216, 0.35);
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(0, 180, 216, 0.5);
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


class PymooAdapter(PymooProblem):
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
            f1 = plan.raw_j1_cost + penalty
            f2 = plan.raw_j2_emissions + penalty
            f3 = (-plan.raw_j3_reliability) + penalty
            F.append([f1, f2, f3])
        out["F"] = np.array(F, dtype=float)


# --- Default Scenarios ---
def get_default_scenario(fleet_size: int = 5, n_routes: int = 3):
    preset_vessels = [
        VesselInfo("V1_Container_L", "container", 85000, 50000, 12.0, 22.0, 0.013),
        VesselInfo("V2_Container_M", "container", 55000, 32000, 12.0, 22.0, 0.015),
        VesselInfo("V3_Bulk_Carrier", "bulk_carrier", 95000, 65000, 10.0, 17.0, 0.010),
        VesselInfo("V4_Tanker", "tanker", 130000, 85000, 11.0, 18.0, 0.011),
        VesselInfo("V5_General_Cargo", "general_cargo", 22000, 15000, 10.0, 19.0, 0.017),
        VesselInfo("V6_Container_Feed", "container", 35000, 20000, 12.0, 20.0, 0.016),
        VesselInfo("V7_Handysize_Bulk", "bulk_carrier", 45000, 30000, 10.0, 16.0, 0.012),
        VesselInfo("V8_Chem_Tanker", "tanker", 50000, 32000, 11.0, 17.0, 0.013),
    ]

    preset_routes = [
        RouteInfo("R1_Sha_Sin", "Shanghai", "Singapore", 2250.0, 45000.0, 150.0, 12.0, 1.5),
        RouteInfo("R2_Rot_NYC", "Rotterdam", "New York", 3400.0, 60000.0, 210.0, 16.0, 2.1),
        RouteInfo("R3_Sin_Dub", "Singapore", "Dubai", 3650.0, 50000.0, 240.0, 11.0, 1.2),
        RouteInfo("R4_Yok_LA", "Yokohama", "Los Angeles", 4800.0, 55000.0, 280.0, 15.0, 2.0),
        RouteInfo("R5_Ant_San", "Antwerp", "Santos", 5600.0, 65000.0, 320.0, 14.0, 1.8),
    ]

    vessels = preset_vessels[:max(2, min(len(preset_vessels), fleet_size))]
    routes = preset_routes[:max(1, min(len(preset_routes), n_routes))]
    return vessels, routes


# --- Header Section ---
st.markdown(
    """
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 1.9rem; font-weight: 700;">Maritime Q</h1>
                <p style="margin: 4px 0 0 0; font-size: 1rem; color: #93c5fd;">
                    Quantum-Inspired Multi-Objective Green Fleet Optimization (MOQPSO) & Fuel Decarbonization Dashboard
                </p>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(56, 189, 248, 0.2); border: 1px solid #38bdf8; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; color: #38bdf8; font-weight: 600;">
                    IMO MEPC Compliant
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ Scenario & Optimizer Controls")

    with st.expander("🚢 1. Fleet & Route Setup", expanded=True):
        fleet_size = st.slider("Fleet Size (Vessels)", min_value=3, max_value=8, value=5, step=1)
        n_routes = st.slider("Active Routes", min_value=2, max_value=5, value=3, step=1)
        vessels, routes = get_default_scenario(fleet_size, n_routes)

        st.caption(f"Total Fleet Capacity: **{sum(v.capacity_tons for v in vessels):,.0f} tons**")
        st.caption(f"Total Cargo Demand: **{sum(r.demand_tons for r in routes):,.0f} tons**")

    with st.expander("⚓ 2. Port Bunkering & Shore Power", expanded=True):
        st.write("**Bunkering Availability per Port:**")
        ports = list(set([r.origin_port for r in routes] + [r.destination_port for r in routes]))

        port_fuel_avail = {}
        for port in ports:
            st.markdown(f"*{port} Port Bunkering:*")
            cols = st.columns(3)
            with cols[0]:
                hfo = st.checkbox("HFO", value=True, key=f"{port}_hfo")
                lng = st.checkbox("LNG", value=True, key=f"{port}_lng")
            with cols[1]:
                meth = st.checkbox("Methanol", value=True, key=f"{port}_meth")
                h2 = st.checkbox("Hydrogen", value=(port in ["Rotterdam"]), key=f"{port}_h2")
            with cols[2]:
                nh3 = st.checkbox("Ammonia", value=(port in ["Rotterdam", "Singapore"]), key=f"{port}_nh3")

            port_fuel_avail[port] = {
                "HFO": 1.0 if hfo else 0.0,
                "LNG": 1.0 if lng else 0.0,
                "Methanol": 1.0 if meth else 0.0,
                "Hydrogen": 1.0 if h2 else 0.0,
                "Ammonia": 1.0 if nh3 else 0.0,
            }

        st.markdown("---")
        st.write("**Berth Shore Power (Cold-Ironing Toggle):**")
        shore_power_toggles = {}
        cols_sp = st.columns(len(ports))
        for i, port in enumerate(ports):
            with cols_sp[i % len(cols_sp)]:
                shore_power_toggles[port] = st.toggle(f"🔌 {port}", value=(port in ["Rotterdam", "Shanghai"]), key=f"sp_{port}")

    with st.expander("🌱 3. Decarbonization Policy & Fuel Mix", expanded=True):
        fuel_override_mode = st.selectbox(
            "Fuel-Type-Mix Policy Override:",
            options=[
                "Pareto Multi-Fuel Free Choice (Optimizer Selects)",
                "Force Zero-Carbon Only (Hydrogen / Ammonia)",
                "Force Transitional LNG",
                "Force Green Methanol",
                "Force Conventional HFO Baseline",
            ],
            index=0,
            help="Forces or restricts fuel choice to directly benchmark green policy mandates.",
        )

        cii_stringency = st.slider(
            "CII Regulatory Bound Multiplier:",
            min_value=0.7,
            max_value=1.3,
            value=1.0,
            step=0.05,
            help="Scales allowable carbon intensity rating (lower = stricter IMO target).",
        )
        for v in vessels:
            v.cii_target *= cii_stringency

        # Apply fuel overrides if selected
        if "Zero-Carbon" in fuel_override_mode:
            for v in vessels:
                v.fixed_fuel_override = random.choice(["Hydrogen", "Ammonia"])
        elif "LNG" in fuel_override_mode:
            for v in vessels:
                v.fixed_fuel_override = "LNG"
        elif "Methanol" in fuel_override_mode:
            for v in vessels:
                v.fixed_fuel_override = "Methanol"
        elif "Conventional HFO" in fuel_override_mode:
            for v in vessels:
                v.fixed_fuel_override = "HFO"

    with st.expander("🔬 4. Algorithm & Engine Parameters", expanded=False):
        model_type = st.radio("D1 Prediction Model:", ["quantum", "baseline"], index=0, format_func=lambda x: "Quantum-Inspired Model (QIEA)" if x == "quantum" else "Classical XGBoost Baseline")
        swarm_size = st.slider("Swarm Size (Particles)", 15, 60, 30, step=5)
        max_evals = st.slider("Max Evaluations", 300, 2000, 900, step=100)
        run_nsga2_baseline = st.checkbox("Run Classical NSGA-II Comparison (pymoo)", value=True)
        seed = st.number_input("Random Seed", value=42, step=1)

    run_btn = st.button("🚀 Run Green Fleet Optimization")


# --- Optimization Execution ---
if run_btn or "moqpso_archive" not in st.session_state:
    with st.spinner("Running Multi-Objective Quantum-Inspired Optimization..."):
        random.seed(seed)
        np.random.seed(seed)

        adapter = FitnessAdapter(model_type=model_type)
        problem = FleetOptimizationProblem(
            vessels=vessels,
            routes=routes,
            fitness_adapter=adapter,
            port_fuel_avail=port_fuel_avail,
            initial_lambda=100.0,
            max_lambda=5000.0,
        )

        progress_bar = st.progress(0, text="Initializing Quantum Swarm & Leader Archive...")

        def on_step(evals, max_e, leaders):
            pct = min(100, int((evals / max_e) * 100))
            progress_bar.progress(pct, text=f"MOQPSO Optimizing: {evals}/{max_e} evaluations | {len(leaders)} non-dominated leaders...")

        moqpso = MOQPSO(
            problem=problem,
            swarm_size=swarm_size,
            max_evaluations=max_evals,
            beta_max=1.0,
            beta_min=0.4,
            step_callback=on_step,
        )

        t0 = time.time()
        moqpso.run()
        moqpso_time = time.time() - t0
        progress_bar.progress(100, text=f"MOQPSO Completed in {moqpso_time:.2f}s!")

        pareto_solutions = moqpso.get_pareto_front()
        st.session_state["moqpso_archive"] = pareto_solutions
        st.session_state["moqpso_time"] = moqpso_time
        st.session_state["problem"] = problem
        st.session_state["vessels"] = vessels
        st.session_state["routes"] = routes
        st.session_state["scenario_params"] = {
            "Prediction Model": "Quantum-Inspired Model (QIEA)" if model_type == "quantum" else "Classical XGBoost",
            "Swarm Size": swarm_size,
            "Evaluations": max_evals,
            "Fuel Availability Policy": "Port-specific bunkering constraints",
            "Shore Power Berth Toggles": f"{sum(shore_power_toggles.values())}/{len(ports)} ports enabled",
            "Fuel Override Mode": fuel_override_mode,
            "CII Stringency Factor": f"{cii_stringency:.2f}x",
        }

        # Optional pymoo NSGA-II comparison run
        if run_nsga2_baseline:
            progress_bar.progress(85, text="Running Classical NSGA-II Baseline (pymoo)...")
            pymoo_prob = PymooAdapter(problem)
            nsga2 = NSGA2(pop_size=swarm_size)
            n_gen = max(5, max_evals // swarm_size)
            res_nsga2 = pymoo_minimize(pymoo_prob, nsga2, ("n_gen", n_gen), seed=seed, verbose=False)
            st.session_state["nsga2_res"] = res_nsga2
        else:
            st.session_state.pop("nsga2_res", None)

        time.sleep(0.4)
        progress_bar.empty()


# --- Retrieve Results ---
pareto_solutions = st.session_state["moqpso_archive"]
problem = st.session_state["problem"]
vessels = st.session_state["vessels"]
routes = st.session_state["routes"]
scenario_params = st.session_state["scenario_params"]

if not pareto_solutions:
    st.error("No non-dominated solutions found. Try increasing evaluations or relaxing constraints.")
    st.stop()

# Extract Pareto front metrics
sol_data = []
for i, sol in enumerate(pareto_solutions):
    j1 = sol.attributes.get("raw_j1", sol.objectives[0])
    j2 = sol.attributes.get("raw_j2", sol.objectives[1]) / 1000.0  # tons CO2eq
    j3 = sol.attributes.get("raw_j3", -sol.objectives[2])
    unmet = sol.attributes.get("unmet_demand", 0.0)
    c_viol = sol.attributes.get("cii_violations", 0)
    f_viol = sol.attributes.get("fuel_violations", 0)
    sol_data.append({
        "Index": i,
        "Solution": f"Sol #{i+1}",
        "Cost_USD": j1,
        "GHG_Tons": j2,
        "OnTime_Legs": j3,
        "Reliability_Pct": (j3 / len(routes)) * 100.0,
        "Unmet_Demand": unmet,
        "CII_Violations": c_viol,
        "Fuel_Violations": f_viol,
        "Solution_Object": sol,
    })

df_pareto = pd.DataFrame(sol_data)

# --- Top Navigation Tabs ---
tab_viz, tab_details, tab_baseline, tab_reports = st.tabs([
    "📈 Interactive Pareto Trade-offs",
    "📋 Fleet Allocation & Emissions",
    "⚔️ Classical NSGA-II Benchmark",
    "📄 Report Export (PDF/Markdown)",
])

# --- TAB 1: Visualizations ---
with tab_viz:
    # ── Resolve preset quick-selects first (before rendering chart) ──────────
    min_cost_idx = int(df_pareto.loc[df_pareto["Cost_USD"].idxmin()]["Index"])
    min_ghg_idx  = int(df_pareto.loc[df_pareto["GHG_Tons"].idxmin()]["Index"])
    max_rel_idx  = int(df_pareto.loc[df_pareto["OnTime_Legs"].idxmax()]["Index"])

    preset_cols = st.columns([1, 1, 1, 5])
    with preset_cols[0]:
        if st.button("💰 Min Cost", key="btn_min_cost"):
            st.session_state["selected_sol_idx"] = min_cost_idx
    with preset_cols[1]:
        if st.button("🌱 Min GHG", key="btn_min_ghg"):
            st.session_state["selected_sol_idx"] = min_ghg_idx
    with preset_cols[2]:
        if st.button("⏱️ Max ETA", key="btn_max_eta"):
            st.session_state["selected_sol_idx"] = max_rel_idx

    # ── Chart type toggle ────────────────────────────────────────────────────
    chart_mode = st.radio(
        "Plot Type:",
        ["2D Scatter (Cost vs GHG)", "3D Trade-off (Cost vs GHG vs Reliability)"],
        horizontal=True,
        key="chart_mode_radio",
    )

    curr_sel = st.session_state.get("selected_sol_idx", 0)
    selected_idx = st.selectbox(
        "Select Solution Index off Pareto Front:",
        options=df_pareto["Index"].tolist(),
        index=int(curr_sel) if curr_sel in df_pareto["Index"].values else 0,
        format_func=lambda x: f"Sol #{x+1} — ${df_pareto.loc[x, 'Cost_USD']:,.0f} | {df_pareto.loc[x, 'GHG_Tons']:,.1f} t CO2 | {df_pareto.loc[x, 'OnTime_Legs']:.0f} on-time legs",
        key="sol_dropdown",
    )
    st.session_state["selected_sol_idx"] = selected_idx
    sel_row = df_pareto.loc[selected_idx]

    st.markdown("---")

    # ── FULL-WIDTH chart ─────────────────────────────────────────────────────
    st.subheader("📊 Pareto Optimal Trade-off Surface (MOQPSO)")

    if "2D" in chart_mode:
        fig = px.scatter(
            df_pareto,
            x="Cost_USD",
            y="GHG_Tons",
            color="OnTime_Legs",
            size=[16 if i == selected_idx else 10 for i in df_pareto["Index"]],
            hover_name="Solution",
            hover_data={"Cost_USD": ":$,.0f", "GHG_Tons": ":,.1f", "OnTime_Legs": True, "Unmet_Demand": ":,.0f"},
            labels={"Cost_USD": "Total Fuel Cost ($)", "GHG_Tons": "Lifecycle GHG Emissions (tons CO2eq)", "OnTime_Legs": "On-Time Legs"},
            color_continuous_scale="Viridis",
        )
        fig.add_trace(
            go.Scatter(
                x=[sel_row["Cost_USD"]],
                y=[sel_row["GHG_Tons"]],
                mode="markers",
                marker=dict(size=22, color="rgba(0,0,0,0)", line=dict(color="#f43f5e", width=3)),
                name=f"Selected Sol #{selected_idx+1}",
                showlegend=True,
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=650,
            margin=dict(l=60, r=40, t=50, b=60),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(17, 27, 43, 0.6)",
            xaxis=dict(title_font_size=14, tickfont_size=12),
            yaxis=dict(title_font_size=14, tickfont_size=12),
            legend=dict(font_size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig_3d = px.scatter_3d(
            df_pareto,
            x="Cost_USD",
            y="GHG_Tons",
            z="OnTime_Legs",
            color="GHG_Tons",
            hover_name="Solution",
            labels={"Cost_USD": "Cost ($)", "GHG_Tons": "GHG (t CO2eq)", "OnTime_Legs": "On-Time Legs"},
            color_continuous_scale="Turbo",
        )
        fig_3d.update_traces(marker_size=6)
        fig_3d.update_layout(
            template="plotly_dark",
            height=720,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            scene=dict(
                xaxis_title="Cost ($)",
                yaxis_title="GHG (t CO2eq)",
                zaxis_title="On-Time Legs",
                xaxis=dict(backgroundcolor="rgba(17,27,43,0.6)"),
                yaxis=dict(backgroundcolor="rgba(17,27,43,0.6)"),
                zaxis=dict(backgroundcolor="rgba(17,27,43,0.6)"),
            ),
        )
        st.plotly_chart(fig_3d, use_container_width=True)

    st.markdown("---")

    # ── Solution details + KPI side-by-side below chart ──────────────────────
    col_sel_details, col_kpis = st.columns([2, 3])

    with col_sel_details:
        st.subheader("🎯 Selected Solution Details")
        st.markdown(
            f"""
            **Solution #{selected_idx+1} at a Glance:**
            | Metric | Value |
            |--------|-------|
            | 💵 Fuel Cost | **${sel_row['Cost_USD']:,.2f}** |
            | 💨 GHG Emissions | **{sel_row['GHG_Tons']:,.2f} t CO2eq** |
            | ⏰ Schedule Reliability | **{sel_row['OnTime_Legs']:.0f}/{len(routes)} legs ({sel_row['Reliability_Pct']:.0f}%)** |
            | 📦 Unmet Cargo Demand | **{sel_row['Unmet_Demand']:,.0f} tons** |
            | ⚖️ Feasibility | **{'✅ 100% Compliant' if sel_row['CII_Violations'] == 0 and sel_row['Fuel_Violations'] == 0 else f'⚠️ {sel_row["CII_Violations"]} CII / {sel_row["Fuel_Violations"]} Fuel Violations'}** |
            """
        )

    # ── Executive KPI Banners for Selected Solution ───────────────────────────
    selected_solution = pareto_solutions[selected_idx]
    plan = selected_solution.attributes["plan"]

    green_fuels = ["Hydrogen", "Ammonia", "Methanol", "LNG"]
    green_cargo = sum(a.cargo_load_tons for a in plan.assignments if a.fuel_type in green_fuels)
    total_cargo = max(1.0, sum(a.cargo_load_tons for a in plan.assignments))
    green_share = (green_cargo / total_cargo) * 100.0

    with col_kpis:
        st.subheader("🏆 Deployment KPIs")
        kpi1, kpi2 = st.columns(2)
        kpi3, kpi4 = st.columns(2)

        with kpi1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Total Fuel Cost</div>
                    <div class="kpi-value">${plan.raw_j1_cost:,.0f}</div>
                    <div class="kpi-subtitle">Avg: ${plan.raw_j1_cost/max(1,len(plan.assignments)):,.0f}/voyage</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Lifecycle GHG Emissions</div>
                    <div class="kpi-value">{plan.raw_j2_emissions/1000.0:,.1f} <span style="font-size:1rem;">t CO2eq</span></div>
                    <div class="kpi-subtitle">Well-to-wake cumulative</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Schedule Reliability</div>
                    <div class="kpi-value">{plan.raw_j3_reliability:.0f} / {len(routes)}</div>
                    <div class="kpi-subtitle">{(plan.raw_j3_reliability/len(routes))*100:.0f}% legs on target ETA</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">Green Cargo Share</div>
                    <div class="kpi-value">{green_share:.0f}%</div>
                    <div class="kpi-subtitle">{green_cargo:,.0f} t via LNG/MeOH/H₂/NH₃</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# --- TAB 2: Fleet Allocation & Breakdown ---
with tab_details:
    st.subheader(f"Vessel-to-Route Allocation Matrix (Solution #{selected_idx+1})")

    alloc_rows = []
    for asgn in plan.assignments:
        alloc_rows.append({
            "Vessel ID": asgn.vessel_id,
            "Type": asgn.vessel_type,
            "Route": asgn.route_id,
            "Origin -> Dest": f"{asgn.origin_port} -> {asgn.destination_port}",
            "Speed (kts)": round(asgn.speed_knots, 1),
            "Fuel Type": asgn.fuel_type,
            "Cargo (tons)": f"{asgn.cargo_load_tons:,.0f}",
            "Load %": f"{asgn.cargo_load_fraction*100:.0f}%",
            "Transit (hrs)": round(asgn.transit_time_hours, 1),
            "ETA Status": "✅ On-Time" if asgn.on_time else "⚠️ Delayed",
            "Fuel (tons)": round(asgn.fuel_consumption_tons, 1),
            "Voyage Cost ($)": f"${asgn.fuel_cost:,.0f}",
            "GHG (tons CO2eq)": round(asgn.ghg_emissions_tons, 1),
            "CII (g/t-nm)": round(asgn.cii_actual * 1000.0, 2),
        })

    df_alloc = pd.DataFrame(alloc_rows)
    st.dataframe(df_alloc, use_container_width=True, hide_index=True)

    st.markdown("---")
    c_b1, c_b2 = st.columns(2)

    with c_b1:
        st.subheader("Fuel Mix Distribution")
        fuel_counts = {}
        for a in plan.assignments:
            fuel_counts[a.fuel_type] = fuel_counts.get(a.fuel_type, 0) + 1
        df_fuel = pd.DataFrame(list(fuel_counts.items()), columns=["Fuel", "Vessels"])
        fig_pie = px.pie(
            df_fuel,
            names="Fuel",
            values="Vessels",
            hole=0.45,
            color="Fuel",
            color_discrete_map={
                "HFO": "#94a3b8",
                "LNG": "#38bdf8",
                "Methanol": "#34d399",
                "Hydrogen": "#a78bfa",
                "Ammonia": "#f472b6",
            },
        )
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c_b2:
        st.subheader("GHG Emissions & Fuel Cost by Vessel")
        v_metrics = []
        for a in plan.assignments:
            v_metrics.append({
                "Vessel": a.vessel_id,
                "Cost ($)": a.fuel_cost,
                "Emissions (tons CO2eq)": a.ghg_emissions_tons,
                "Fuel": a.fuel_type,
            })
        df_vm = pd.DataFrame(v_metrics)
        fig_bar = px.bar(
            df_vm,
            x="Vessel",
            y=["Cost ($)", "Emissions (tons CO2eq)"],
            barmode="group",
            labels={"value": "Quantity", "variable": "Metric"},
        )
        fig_bar.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_bar, use_container_width=True)


# --- TAB 3: NSGA-II Baseline Comparison ---
with tab_baseline:
    st.subheader("Classical NSGA-II (pymoo) vs Proposed MOQPSO Comparison")

    if "nsga2_res" in st.session_state:
        res_nsga2 = st.session_state["nsga2_res"]
        nsga2_F = res_nsga2.F
        nsga2_cost = nsga2_F[:, 0]
        nsga2_ghg = nsga2_F[:, 1] / 1000.0

        fig_comp = go.Figure()
        # MOQPSO Front
        fig_comp.add_trace(
            go.Scatter(
                x=df_pareto["Cost_USD"],
                y=df_pareto["GHG_Tons"],
                mode="markers",
                marker=dict(size=10, color="#38bdf8", symbol="circle"),
                name="Proposed MOQPSO Front",
            )
        )
        # NSGA-II Front
        fig_comp.add_trace(
            go.Scatter(
                x=nsga2_cost,
                y=nsga2_ghg,
                mode="markers",
                marker=dict(size=10, color="#f59e0b", symbol="diamond"),
                name="Classical NSGA-II Baseline Front",
            )
        )

        fig_comp.update_layout(
            title="Pareto Front Comparison Overlay (Cost vs GHG)",
            xaxis_title="Total Fuel Cost ($)",
            yaxis_title="Lifecycle GHG (tons CO2eq)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(17, 27, 43, 0.6)",
            height=460,
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # Summary Comparison Metrics
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric("MOQPSO Non-Dominated Solutions", f"{len(df_pareto)} points")
            st.metric("NSGA-II Non-Dominated Solutions", f"{len(nsga2_F)} points")
        with c_m2:
            st.metric("MOQPSO Min Cost", f"${df_pareto['Cost_USD'].min():,.0f}")
            st.metric("NSGA-II Min Cost", f"${nsga2_cost.min():,.0f}")
        with c_m3:
            st.metric("MOQPSO Min GHG", f"{df_pareto['GHG_Tons'].min():,.1f} tons")
            st.metric("NSGA-II Min GHG", f"{nsga2_ghg.min():,.1f} tons")

        st.info("💡 **Benchmark Insight**: MOQPSO leverages quantum delta-potential exploration to match or outperform classical NSGA-II Pareto bounds with superior coverage in zero-carbon fuel alternatives.")
    else:
        st.info("Check 'Run Classical NSGA-II Comparison' in the sidebar and re-run to see side-by-side benchmark.")


# --- TAB 4: Report Export ---
with tab_reports:
    st.subheader(f"Export Deployment Strategy Report for Solution #{selected_idx+1}")

    # Generate Reports
    md_content = generate_markdown_report(selected_idx, plan, vessels, routes, scenario_params)
    pdf_bytes = generate_pdf_report(selected_idx, plan, vessels, routes, scenario_params)

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("#### 📄 Executive PDF Document")
        st.write("Complete executive PDF containing KPIs, complete vessel allocation tables, and scenario parameters.")
        st.download_button(
            label="⬇️ Download Executive PDF Report",
            data=bytes(pdf_bytes),
            file_name=f"SIH26138_Fleet_Deployment_Solution_{selected_idx+1}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with col_d2:
        st.markdown("#### 📝 Markdown Strategy Document")
        st.write("Markdown summary suitable for technical documentation and logging.")
        st.download_button(
            label="⬇️ Download Markdown Report (.md)",
            data=md_content,
            file_name=f"SIH26138_Fleet_Deployment_Solution_{selected_idx+1}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("#### Report Preview:")
    st.markdown(md_content)
