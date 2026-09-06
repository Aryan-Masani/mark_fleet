# Deliverable 2 — Mathematical Optimization Formulation
## Quantum-Inspired Fuel Consumption Prediction and Green Fleet Optimization (SIH26138)

---

## 1. Problem Overview

Given a fleet of heterogeneous vessels, a set of routes with cargo demand, and a set of candidate fuel types, determine the vessel-to-route assignment, cruising speed, and fuel type for each voyage that jointly minimizes fuel cost and lifecycle greenhouse gas (GHG) emissions, while satisfying cargo demand, schedule reliability, and regulatory constraints.

---

## 2. Sets and Indices

| Symbol | Meaning |
|---|---|
| $V = \{1, ..., N_v\}$ | Set of vessels in the fleet, indexed by $v$ |
| $R = \{1, ..., N_r\}$ | Set of routes/voyage legs, indexed by $r$ |
| $F = \{1, ..., N_f\}$ | Set of candidate fuel types: {HFO, LNG, Methanol, Hydrogen, Ammonia}, indexed by $f$ |
| $T = \{1, ..., N_t\}$ | Set of scheduling periods (e.g., weeks), indexed by $t$ |
| $P$ | Set of ports, used for shore-power and bunkering availability |

---

## 3. Parameters (Known / Predicted Inputs)

| Symbol | Meaning |
|---|---|
| $D_r$ | Cargo demand on route $r$ (tons) |
| $Cap_v$ | Cargo capacity of vessel $v$ (tons) |
| $Dist_r$ | Distance of route $r$ (nautical miles) |
| $s_{min}, s_{max}$ | Minimum/maximum permissible cruising speed |
| $EF_f$ | Well-to-wake emission factor of fuel $f$ (kg CO$_2$eq per ton fuel) |
| $C_f$ | Unit cost of fuel $f$ (currency per ton) |
| $Avail_{f,p}$ | Availability of fuel $f$ at port $p$ (binary/quantity) |
| $CII_v$ | Vessel $v$'s current CII rating requirement (regulatory bound) |
| $ShorePower_p$ | Shore power availability at port $p$ (binary) |
| $\hat{FC}(v, s, l, w, f)$ | **Predicted fuel consumption** — output of the Deliverable 1 prediction model, as a function of vessel $v$, speed $s$, load $l$, weather $w$, and fuel type $f$. This is where D1 plugs into D2/D3. |

---

## 4. Decision Variables

| Symbol | Type | Meaning |
|---|---|---|
| $x_{v,r,t} \in \{0,1\}$ | Binary | 1 if vessel $v$ is assigned to route $r$ in period $t$ |
| $s_{v,r,t} \in [s_{min}, s_{max}]$ | Continuous | Cruising speed of vessel $v$ on route $r$ in period $t$ |
| $y_{v,r,t,f} \in \{0,1\}$ | Binary | 1 if vessel $v$ uses fuel $f$ on route $r$ in period $t$ |
| $z_{v,p,t} \in \{0,1\}$ | Binary | 1 if vessel $v$ uses shore power at port $p$ in period $t$ |

Constraint linking $y$: $\sum_{f \in F} y_{v,r,t,f} = x_{v,r,t} \quad \forall v,r,t$ (exactly one fuel type per active voyage leg).

---

## 5. Objective Functions (Multi-Objective)

### 5.1 Minimize Total Fuel Cost

$$
J_1 = \sum_{v \in V}\sum_{r \in R}\sum_{t \in T}\sum_{f \in F} x_{v,r,t} \cdot y_{v,r,t,f} \cdot \hat{FC}(v, s_{v,r,t}, l_{v,r,t}, w_{v,r,t}, f) \cdot C_f
$$

### 5.2 Minimize Lifecycle GHG Emissions

$$
J_2 = \sum_{v \in V}\sum_{r \in R}\sum_{t \in T}\sum_{f \in F} x_{v,r,t} \cdot y_{v,r,t,f} \cdot \hat{FC}(v, s_{v,r,t}, l_{v,r,t}, w_{v,r,t}, f) \cdot EF_f
$$

### 5.3 Maximize Schedule Reliability (minimize the negative)

$$
J_3 = -\sum_{v \in V}\sum_{r \in R}\sum_{t \in T} x_{v,r,t} \cdot \mathbb{1}\left[\frac{Dist_r}{s_{v,r,t}} \le ETA^{target}_{r,t}\right]
$$

i.e., reward assignments where transit time meets the scheduled ETA window.

### 5.4 Combined Multi-Objective Problem

$$
\min_{x, s, y, z} \; \mathbf{J}(x,s,y,z) = \big(J_1,\; J_2,\; J_3\big)
$$

Solved as a true Pareto-front problem (no fixed weights) — QPSO/MOQPSO maintains a non-dominated solution archive rather than collapsing to one scalar. A weighted-sum scalarization is kept as a fallback baseline for benchmarking against classical single-objective GA/PSO:

$$
J_{scalar} = w_1 \frac{J_1}{J_1^{ref}} + w_2 \frac{J_2}{J_2^{ref}} + w_3 \frac{J_3}{J_3^{ref}}, \quad \sum_i w_i = 1
$$

---

## 6. Constraints

**Demand satisfaction** — cargo carried on each route meets demand:
$$
\sum_{v \in V} x_{v,r,t} \cdot Cap_v \ge D_r \quad \forall r, t
$$

**Capacity** — a vessel cannot be assigned beyond its own capacity (redundant with above per-vessel but kept explicit for load-based fuel prediction):
$$
l_{v,r,t} \le Cap_v \quad \forall v,r,t
$$

**Single assignment** — a vessel serves at most one route per period:
$$
\sum_{r \in R} x_{v,r,t} \le 1 \quad \forall v, t
$$

**Speed bounds:**
$$
s_{min} \le s_{v,r,t} \le s_{max} \quad \forall v,r,t
$$

**Fuel availability** — a vessel can only use a fuel available at its departure port:
$$
y_{v,r,t,f} \le Avail_{f, port(r)} \quad \forall v,r,t,f
$$

**Emission regulation compliance (CII/EEXI):**
$$
\frac{\sum_{r,t} x_{v,r,t}\hat{FC}(\cdot) \cdot EF_{f}}{\sum_{r,t} x_{v,r,t} \cdot Cap_v \cdot Dist_r} \le CII_v \quad \forall v
$$

**Shore power logic** — shore power usable only where available, and excludes main-engine fuel consumption during that berth period:
$$
z_{v,p,t} \le ShorePower_p \quad \forall v,p,t
$$

**Non-negativity / domain constraints** as declared in Section 4.

---

## 7. Penalty Formulation (for metaheuristic fitness — used by D3)

Since QPSO/MOQPSO operates in a continuous-relaxed search space, hard constraints are handled via penalty terms rather than exact enforcement at every iteration:

$$
Fitness(x,s,y,z) = \mathbf{J}(x,s,y,z) + \lambda \sum_k \max(0, g_k(x,s,y,z))^2
$$

where $g_k \le 0$ represents each constraint in Section 6 rewritten in standard form, and $\lambda$ is a large penalty coefficient (or dynamically increased over iterations — "annealed penalty" — to improve early-stage exploration).

---

## 8. Particle Encoding for the Quantum-Inspired Algorithm (bridges to Deliverable 3)

Each particle $i$ in the QPSO swarm encodes one complete fleet deployment plan as a real-valued vector:

$$
X_i = \big[\, s_{1,1}, \phi_{1,1}, \; s_{1,2}, \phi_{1,2}, \; \dots, \; s_{v,r}, \phi_{v,r} \,\big]
$$

where $s_{v,r} \in [s_{min}, s_{max}]$ is the continuous speed dimension, and $\phi_{v,r} \in [0, N_f]$ is a continuous relaxation of the fuel-type choice, discretized by $y_{v,r,\cdot,f^*} = 1$ where $f^* = \lfloor \phi_{v,r} \rfloor$. Vessel-to-route assignment $x_{v,r,t}$ is handled by a separate permutation/priority-encoding sub-vector decoded via a greedy demand-matching rule at fitness-evaluation time.

This vector is exactly what mbest, pbest, and gbest operate over in the QPSO update rule.

---

## 9. Interface Contract Between Deliverables

- **D1 → D2/D3:** the prediction model $\hat{FC}(\cdot)$ is called as a black-box function inside $J_1$, $J_2$, and every fitness evaluation. D3 never computes fuel consumption analytically.
- **D2 → D3:** this document's objective/constraint definitions are implemented literally as the fitness and penalty functions inside the QPSO/MOQPSO loop.
- **D3 → D4:** the Pareto archive returned by D3 is what the dashboard visualizes and lets the user select from.

---

*This formulation is the shared contract for Deliverables 1, 3, and 4 — any change to variables/objectives here should be propagated to the prediction feature set (D1) and the optimizer implementation (D3).*
