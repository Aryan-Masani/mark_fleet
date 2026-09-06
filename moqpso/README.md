# Deliverable 3 — Multi-Objective Quantum-Inspired Particle Swarm Optimization (MOQPSO)
## Package: `moqpso/` (SIH26138 Egreen Quanta)

---

## 1. Executive Summary & Scope Decisions

`moqpso` is an optimization engine designed to solve the Green Fleet Deployment and Speed Optimization problem defined in `SIH26138_D2_Mathematical_Formulation.md`. It finds the Pareto-optimal trade-offs between **Total Fuel Cost ($J_1$)**, **Lifecycle GHG Emissions ($J_2$)**, and **Schedule Reliability ($-J_3$)**.

### Scope Decisions (MVP vs Future Deliverables)
1. **Single-Period Assignment ($T=1$)**:
   - Implements single-period fleet deployment (one complete voyage cycle) fully and rigorously.
   - Multi-period scheduling ($T > 1$) with recurring weekly time horizons is out of scope for this Deliverable 3 MVP. It is formally flagged as a documented extension for the **Deliverable 5** comprehensive benchmarking and write-up.
2. **Shore Power Logic ($z_{v,p,t}$)**:
   - Out of scope for the D3 fitness evaluation engine; main propulsion during berth is not simulated.
   - Surfaced exclusively as a **Deliverable 4 Dashboard scenario toggle** to allow operators to model cold ironing availability and port-level grid emission credits.

---

## 2. Actual `predict.py` Interface Used (D1 Contract)

The D1 $\to$ D3 interface strictly honors Section 9 of the binding mathematical formulation: **the prediction model $\hat{FC}(v, s, l, w, f)$ is queried as a pure black box; fuel consumption is never calculated analytically inside `moqpso`**.

In `fuel_prediction/fuel_prediction/predict.py`, the actual production class and signature is:

```python
from predict import FuelPredictor

predictor = FuelPredictor(model_type="quantum", models_dir=MODELS_DIR)  # or "baseline"

fuel_tons = predictor.predict_one(
    vessel_type=vessel_type,          # str: 'container', 'bulk_carrier', 'tanker', 'general_cargo'
    fuel_type=fuel_type,              # str: 'HFO', 'LNG', 'Methanol', 'Hydrogen', 'Ammonia'
    displacement_tons=displacement,   # float: vessel total displacement in metric tons
    cargo_load_fraction=load_frac,    # float: cargo carried / capacity in [0.0, 1.0]
    speed_knots=speed,                # float: cruising speed in knots
    wind_speed_knots=wind,            # float: exogenous wind speed in knots
    wave_height_m=wave,               # float: exogenous significant wave height in meters
    distance_nm=dist,                 # float: voyage leg distance in nautical miles
) -> float
```

`moqpso.fitness_adapter.FitnessAdapter` wraps this function, ensures `sys.path` dynamically resolves the pickled `QuantumInspiredFuelModel` without touching `fuel_prediction/` code, and guarantees physically non-negative fuel output (`max(0.0, prediction)`).

---

## 3. Particle Encoding & Greedy Decoding Rule (Section 8)

### Continuous Particle Representation
Each particle $i$ in the swarm represents a candidate fleet deployment strategy encoded as a real-valued vector:

$$
X_i = \big[\, s_{1,1}, \phi_{1,1}, \; s_{1,2}, \phi_{1,2}, \; \dots, \; s_{v,r}, \phi_{v,r}, \; \pi_1, \dots, \pi_{N_v} \,\big]
$$

- **Total Dimensions**: $D = 2 \cdot N_v \cdot N_r + N_v$
- **Speed Sub-vector**: $s_{v,r} \in [s_{min}, s_{max}]$ (continuous cruising speed for vessel $v$ if assigned to route $r$).
- **Continuous Fuel Relaxation**: $\phi_{v,r} \in [0, N_f]$.
  Discretized to candidate fuel index:
  $$f^* = \min\big(\lfloor \phi_{v,r} \rfloor, N_f - 1\big)$$
  Fuel ordering matches Deliverable 1 and 2:
  $$\{0: \text{HFO}, \; 1: \text{LNG}, \; 2: \text{Methanol}, \; 3: \text{Hydrogen}, \; 4: \text{Ammonia}\}$$
- **Permutation/Priority Sub-vector**: $\pi_v \in [0, 1]$ (one continuous priority scalar per vessel).
- **Exogenous Weather**: Wind speed and wave height are scenario parameters ($w_{v,r}$), not decision variables.

### Greedy Demand-Matching Decode Rule
At evaluation time, the priority sub-vector $\mathbf{\pi}$ is decoded into discrete vessel-to-route assignments:
1. **Sort Routes by Demand**: Routes are ordered in descending order of cargo demand: $D_{(1)} \ge D_{(2)} \ge \dots \ge D_{(N_r)}$.
2. **Prioritize Unassigned Vessels**: For each route, all currently unassigned vessels are sorted in descending order of their priority scalar $\pi_v$.
3. **Greedy Allocation**: Vessels are sequentially assigned to the route until $\sum_{v \in \text{assigned}} Cap_v \ge D_r$ or no unassigned vessels remain.
4. **Load Allocation**: The carried cargo load is $l_{v,r} = \min(\text{remaining demand}, Cap_v)$ with load fraction $l_{v,r} / Cap_v$.

---

## 4. Constraint Handling Breakdown (Section 6 & 7)

Constraints from Section 6 of the mathematical formulation are partitioned into **Enforced by Construction** vs. **Quadratic Penalties**:

| Constraint | Category | Enforcement Mechanism |
|---|---|---|
| **Single Assignment** ($\sum_r x_{v,r} \le 1$) | **By Construction** | Greedy decode removes vessel from available pool once assigned. No penalty required. |
| **Capacity Bound** ($l_{v,r} \le Cap_v$) | **By Construction** | Cargo load is explicitly capped at $\min(\text{demand}, Cap_v)$. |
| **Speed Bounds** ($s_{min} \le s_{v,r} \le s_{max}$) | **By Construction** | Variable search bounds $[s_{min}, s_{max}]$ in `FloatProblem`. |
| **Demand Satisfaction** ($\sum_v x_{v,r} Cap_v \ge D_r$) | **Quadratic Penalty** | $g_r = D_r - \sum_v x_{v,r} Cap_v$. Only fires if total fleet capacity cannot satisfy route demand. |
| **Fuel Availability** ($y_{v,r,f^*} \le Avail_{f^*, port(r)}$) | **Quadratic Penalty** | $g_{v,r} = 1 - Avail_{f^*, port(r)}$. Penalizes using fuel not bunkered at departure port. |
| **CII Regulatory Compliance** | **Quadratic Penalty** | $g_v = \frac{\sum_r x_{v,r} \hat{FC} \cdot EF_{f^*}}{\sum_r x_{v,r} Cap_v Dist_r} - CII_v$. Penalizes vessels exceeding their carbon intensity rating. |

### Annealed Penalty Formulation
Per Section 7, constraint violations are integrated into the multi-objective fitness evaluation:

$$
Fitness_m = J_m + \lambda(t) \sum_k \max(0, g_k)^2, \quad \forall m \in \{1, 2, 3\}
$$

where $\lambda(t)$ is linearly annealed from $\lambda_{init} = 100$ to $\lambda_{max} = 5000$ as search progress $t / T_{max}$ advances, encouraging broad early-stage exploration before enforcing strict feasibility.

---

## 5. MOQPSO Algorithm Mechanics

`MOQPSO` subclasses jMetalPy's `SMPSO`. It preserves SMPSO's proven multi-objective Pareto infrastructure (`CrowdingDistanceArchive`, `DominanceComparator`, and `select_global_best()` binary tournament over leaders) and mutation `perturbation`, while replacing velocity updates with the **Quantum-Behaved Particle Swarm Optimization (QPSO)** mechanics with Mean Best Position ($mbest$):

1. **Velocity Update**: Completely eliminated (`update_velocity` is a no-op). Particles have no velocity state.
2. **Mean Best Position ($mbest$)**:
   Computed once per iteration across all swarm particles' personal historical best positions:
   $$mbest_d = \frac{1}{N_{swarm}} \sum_{i=1}^{N_{swarm}} pbest_{i, d}$$
3. **Contraction-Expansion Coefficient Annealing**:
   $\beta(t)$ linearly decreases from $\beta_{max} = 1.0$ to $\beta_{min} = 0.4$ over the optimization run:
   $$\beta(t) = \beta_{max} - \frac{t}{T_{max}}\big(\beta_{max} - \beta_{min}\big)$$
4. **Quantum Delta-Potential Position Sampling**:
   For each particle $i$ and dimension $d$:
   - Draw independent uniform random variables $\phi \sim U(0, 1)$ and $u \sim U(0, 1)$.
   - Compute stochastic local attractor:
     $$p_{id} = \phi \cdot pbest_{id} + (1 - \phi) \cdot gbest_d$$
     where $gbest$ is sampled from the `CrowdingDistanceArchive` via binary tournament.
   - Compute characteristic quantum potential length:
     $$L_{id} = 2 \cdot \beta(t) \cdot |mbest_d - x_{id}|$$
   - Update particle coordinate:
     $$x_{id} \leftarrow p_{id} \pm L_{id} \cdot \ln\left(\frac{1}{u}\right), \quad \text{sign } \pm \text{ with probability } 0.5$$
   - Clip to lower/upper variable bounds.

---

## 6. Known Limitation & Scalability Note

> [!WARNING]
> **High Dimensionality at Large Fleet Sizes ($O(N_v \times N_r)$):**
> The continuous matrix encoding represents all potential $(v, r)$ candidate pairings, yielding a decision vector of dimension $D = 2 \cdot N_v \cdot N_r + N_v$.
> While highly expressive for small-to-medium fleets (e.g. 5 vessels $\times$ 3 routes = 35 dimensions), this quadratic scaling may slow down convergence at large fleet sizes (e.g., Deliverable 5's 200-vessel benchmark with 10 routes = 4,200 dimensions) due to the curse of dimensionality rather than algorithm quality.
> 
> **Documented Linear Fallback Encoding ($O(N_v)$):**
> If large-scale benchmarking in Deliverable 5 exhibits dimensionality-driven degradation, the fallback formulation switches to a per-vessel direct vector:
> $$X_i = \big[\, r_1, s_1, \phi_1, \; r_2, s_2, \phi_2, \; \dots, \; r_{N_v}, s_{N_v}, \phi_{N_v} \,\big]$$
> where each vessel has exactly 3 variables: continuous route target $r_v \in [0, N_r]$, cruising speed $s_v$, and fuel choice $\phi_v$, reducing total dimensionality to strictly $3 \cdot N_v$ (600 dimensions for 200 vessels).

---

## 7. Deliverable 3 $\to$ Deliverable 4 Contract

Deliverable 4 (Streamlit Dashboard) interacts with Deliverable 3 via:
```python
from moqpso import FleetOptimizationProblem, MOQPSO, VesselInfo, RouteInfo, FitnessAdapter

problem = FleetOptimizationProblem(vessels=vessels, routes=routes, ...)
optimizer = MOQPSO(problem=problem, swarm_size=50, max_evaluations=2500, step_callback=on_progress)
optimizer.run()

pareto_solutions = optimizer.get_pareto_front()
# Each solution provides:
# - solution.objectives: [Fitness_J1, Fitness_J2, Fitness_J3]
# - solution.attributes["plan"]: DecodedPlan (vessel-route table, speed, fuel, load, costs, CII)
# - solution.attributes["raw_j1"]: Total fuel cost ($)
# - solution.attributes["raw_j2"]: Lifecycle GHG emissions (kg CO2eq)
# - solution.attributes["raw_j3"]: Count of on-time voyage legs
```
