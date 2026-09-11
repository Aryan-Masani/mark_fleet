# 🎙️ Maritime Q — Green Fleet Optimizer: Demo Presentation Script

> **Audience**: Panel / Evaluators / Technical judges  
> **Duration**: ~8–12 minutes  
> **URL**: http://localhost:5173

---

## 🗺️ Presentation Order (Big Picture)

```
1. Opening Hook       → What problem we're solving
2. Sidebar            → How we configure a scenario  
3. Run Optimization   → Watching the algorithm work live
4. Tab 1 — Pareto     → Exploring trade-off solutions
5. Tab 2 — Allocation → Drilling into a specific solution
6. Tab 3 — Benchmark  → Proving MOQPSO beats NSGA-II
7. Tab 4 — Report     → Export & real-world handoff
8. Closing            → Impact & novelty summary
```

---

## 🎬 PART 1 — Opening Hook (30 seconds)

> *"The shipping industry accounts for nearly 3% of global CO₂ emissions. 
> A fleet operator running 5 vessels across 3 trade routes makes hundreds of 
> decisions every day — which fuel to burn, how fast to sail, which port to bunker at — 
> and each decision is a trade-off between cost, emissions, and schedule reliability.
> We built Maritime Q to solve all of those trade-offs simultaneously, 
> using a quantum-inspired optimization algorithm we call MOQPSO."*

**[Point to the screen — the empty landing state with the 🚢 icon]**

> *"This is the dashboard. On the left is your control panel — your scenario configurator. 
> The right side is where the results live. Let's walk through it."*

---

## 🎬 PART 2 — The Sidebar (2–3 minutes)

**[Point to the sidebar on the left]**

> *"The sidebar has 4 collapsible sections. Think of them as the 4 questions 
> a fleet manager asks before every deployment."*

---

### Section 1 — 🚢 Fleet & Route Setup

**[Point to the sliders]**

> *"Question one: How large is my fleet, and how many routes am I covering?"*

> *"The Fleet Size slider goes from 3 to 8 vessels. I'll leave it at 5.  
> Active Routes controls how many trade lanes are active — I'll set it to 3.  
> As soon as I change these, the dashboard auto-fetches the default port configuration 
> from our FastAPI backend — you'll notice Section 2 updates automatically."*

---

### Section 2 — ⚓ Port Bunkering & Shore Power

**[Point to the checkbox grid under each port name]**

> *"Question two: What fuels are actually available at each port?"*

> *"Each port gets a row — Rotterdam, Singapore, Shanghai, and so on.  
> The checkboxes represent the five fuel types: 
> **HFO** (conventional heavy fuel oil), **LNG**, **Methanol**, **Hydrogen**, and **Ammonia**.  
> Not every port can supply every fuel — Rotterdam can do Hydrogen and Ammonia 
> because of its terminal infrastructure, while others are limited to HFO and LNG.  
> This is real-world port infrastructure encoded directly into the optimizer constraints."*

> *"Below that — the **Shore Power (Cold-Ironing)** toggles. 
> When a vessel is docked and we flip this on, it draws electricity from the grid 
> instead of running its auxiliary engines, cutting hoteling emissions to near zero.
> Rotterdam and Shanghai have it enabled by default."*

---

### Section 3 — 🌱 Decarbonization Policy & Fuel Mix

**[Point to the dropdown and CII slider]**

> *"Question three: What's the regulatory and strategic fuel mandate?"*

> *"The **Fuel Policy dropdown** has 5 options:*
> - *Pareto Multi-Fuel Free Choice — the optimizer picks freely across all fuels*
> - *Force Zero-Carbon Only — locks to Hydrogen or Ammonia*
> - *Force LNG, Methanol, or conventional HFO — for scenario analysis*"*

> *"Below that is the **CII Regulatory Bound Multiplier** — CII stands for 
> Carbon Intensity Indicator, the IMO's rating system for vessel efficiency.  
> At 1.0x we match the current regulation. Slide it to 0.7x and we tighten 
> the constraint — the optimizer must find solutions that are 30% cleaner. 
> This is exactly how a compliance team stress-tests their fleet against future IMO targets."*

---

### Section 4 — 🔬 Algorithm & Engine Parameters *(collapsed by default)*

**[Click to expand it]**

> *"Question four — the engine room. This is where we tune the optimizer itself."*

> *"The **D1 Prediction Model** radio toggles between our novel 
> **Quantum-Inspired QIEA model** — which uses quantum superposition to explore 
> the fuel-consumption space — and a classical **XGBoost baseline** for comparison.*"

> *"**Swarm Size** and **Max Evaluations** control the MOQPSO particle cloud — 
> think of it as how many candidate fleet deployments the algorithm explores in parallel 
> and how long it searches.*"

> *"**Run NSGA-II Comparison** — when checked, it simultaneously runs the classical 
> genetic algorithm from pymoo so we get a direct head-to-head benchmark.  
> I'll keep that on.  **Random Seed** ensures reproducibility."*

---

## 🎬 PART 3 — Running the Optimization (1 minute)

**[Click the big 🚀 "Run Green Fleet Optimization" button]**

> *"I'll hit Run now."*

**[Point to the progress bar that appears]**

> *"You can see the live progress bar — this is a Server-Sent Events stream 
> from the FastAPI backend. The algorithm is running MOQPSO iterations in real-time, 
> and every update is pushed to the UI instantly without polling.  
> Watch the percentage climb..."*

**[Wait for it to complete — ~10–20 seconds]**

> *"...and we have results. Four analysis tabs just appeared at the top. 
> Let's go through each one."*

---

## 🎬 PART 4 — Tab 1: 📈 Interactive Pareto Trade-offs (2–3 minutes)

**[Click "📈 Interactive Pareto Trade-offs" tab]**

> *"This is the heart of the system — the Pareto Optimal Trade-off Surface."*

### Quick-Select Presets

**[Point to the 3 buttons at the top: 💰 Min Cost, 🌱 Min GHG, ⏱️ Max ETA]**

> *"These three preset buttons let us instantly jump to extreme solutions:*
> - *Min Cost — cheapest deployment, ignoring emissions*
> - *Min GHG — cleanest deployment, ignoring cost*
> - *Max ETA — best schedule reliability, vessels arrive on time*"*

> *"This is the classic trilemma of shipping logistics — you can't minimize all three simultaneously. 
> The Pareto front gives you every optimal compromise between them."*

### 2D Scatter Chart

**[Point to the main chart]**

> *"The 2D chart plots **Total Fuel Cost on the X-axis** against **Lifecycle GHG Emissions on the Y-axis**. 
> Each dot is one non-dominated solution — a valid fleet deployment strategy.  
> The **color of each dot encodes On-Time Schedule Reliability** using the Viridis colorscale — 
> brighter dots have better ETA performance.  
> The **red ring** marks whichever solution is currently selected."*

> *"You can hover any dot and see all its metrics. 
> Or click Min GHG — watch the ring jump to the bottom-left, 
> the greenest strategy on the front."*

### 3D Toggle

**[Click "3D Trade-off" toggle]**

> *"Switch to 3D and we add the third axis — Schedule Reliability. 
> Now we see the full trade-off surface in 3 dimensions. 
> You can rotate it, zoom in — it's fully interactive."*

### Solution Selector

**[Point to the dropdown]**

> *"The solution selector dropdown lists every Pareto point with its cost, GHG, and on-time legs. 
> Whatever I pick here propagates across all tabs — so Tab 2 will show me 
> the exact vessel assignments for the selected solution."*

### KPI Cards & Solution Details

**[Point to the bottom cards]**

> *"Below the chart are two panels:*
> - *Left — a detail card showing Fuel Cost, GHG, Schedule Reliability, Unmet Cargo, and Regulatory Feasibility (CII and port fuel violations)*
> - *Right — four KPI cards: Total Fuel Cost per voyage, Lifecycle GHG (well-to-wake), Schedule Reliability as a fraction, and Green Cargo Share — the percentage of cargo moved on clean fuels"*

---

## 🎬 PART 5 — Tab 2: 📋 Fleet Allocation & Emissions (1–2 minutes)

**[Click "📋 Fleet Allocation & Emissions" tab]**

> *"Tab 2 drills into the specific solution we selected."*

### Allocation Table

**[Point to the big table]**

> *"This is the **Vessel-to-Route Allocation Matrix**. Every row is one vessel on one route leg.*
> - *Vessel ID and Type — what class of ship*
> - *Route and Origin → Destination ports*
> - *Speed in knots — the optimizer chose this, trading off fuel burn vs transit time*
> - *Fuel type — color-coded: teal for LNG, green for Methanol, purple for Hydrogen, pink for Ammonia*
> - *Cargo load in tons and load fraction*
> - *Transit time and ETA status — green badge means on-time, red means delayed*
> - *Fuel consumption, cost, GHG emissions, and CII rating per leg"*

### Charts

**[Point to the two charts below]**

> *"Below the table are two charts:*
> - *Left: a **Fuel Mix donut chart** — at a glance you see what percentage of voyages run on each fuel type*
> - *Right: a **grouped bar chart of GHG vs Cost per vessel** — which vessel is the biggest cost or emissions driver in this scenario"*

---

## 🎬 PART 6 — Tab 3: ⚔️ NSGA-II Benchmark (1 minute)

**[Click "⚔️ Classical NSGA-II Benchmark" tab]**

> *"Now the academic credibility check."*

> *"This tab overlays our MOQPSO Pareto front in **teal** against 
> the classical NSGA-II front from pymoo in **amber/gold**.*"

> *"You can see our front pushes further into the lower-left corner — 
> lower cost and lower emissions simultaneously — and provides **denser coverage** 
> of the trade-off space, meaning operators have more choices."*

**[Point to the three metric cards below]**

> *"The three cards quantify it:*
> - *Non-Dominated Solutions: MOQPSO vs NSGA-II point count*
> - *Minimum Cost achieved by each*
> - *Minimum GHG achieved by each"*

> *"The info box summarizes the key insight: MOQPSO uses **quantum delta-potential 
> exploration** to escape local optima that trap classical evolutionary algorithms, 
> giving us better Pareto spread with the same computational budget."*

---

## 🎬 PART 7 — Tab 4: 📄 Report Export (30 seconds)

**[Click "📄 Report Export (PDF/Markdown)" tab]**

> *"Finally, real-world handoff."*

> *"The currently selected solution can be exported as:*
> - *A **PDF executive document** — KPIs, allocation table, scenario parameters, ready for a boardroom or port authority presentation*
> - *A **Markdown file** — for technical docs, GitHub wikis, or compliance logs*"*

**[Point to the preview panel]**

> *"The preview shows the exact report that will be generated — 
> you can read the assignment table, KPIs, and scenario config right here before downloading."*

> *"[Click Download PDF]"*

---

## 🎬 PART 8 — Closing (30–45 seconds)

> *"So to recap — what we built is a full-stack maritime decarbonization decision support tool:*
> - *A **Python MOQPSO optimizer** with quantum-inspired exploration — our core research contribution*
> - *A **FastAPI backend** with real-time SSE streaming*
> - *A **React + Plotly dashboard** with interactive Pareto analysis, vessel-level drill-down, 
>   head-to-head benchmarking, and report generation*"*

> *"The system directly answers the question every green-shipping operator faces: 
> **'What is the cheapest way for my fleet to sail cleanly and reliably?'** — 
> and it gives them not one answer, but an entire frontier of optimal strategies 
> to choose from based on their priorities."*

> *"Thank you."*

---

## ⏱️ Timing Reference

| Section | Time |
|---|---|
| Opening Hook | 0:00 – 0:30 |
| Sidebar walkthrough | 0:30 – 3:00 |
| Running optimization | 3:00 – 4:00 |
| Pareto Tab | 4:00 – 6:30 |
| Allocation Tab | 6:30 – 8:00 |
| Benchmark Tab | 8:00 – 9:00 |
| Report Tab | 9:00 – 9:30 |
| Closing | 9:30 – 10:15 |

---

## 💡 Quick Tips for the Demo

- **Pre-run before presenting** — have results already visible so you don't wait during the opening
- If you want a **dramatic live run**, start with the empty state and hit 🚀 after the sidebar walkthrough
- Click **💰 Min Cost** then **🌱 Min GHG** on Pareto tab to visually show the trade-off live
- **Hover over dots** on the scatter chart to show the rich tooltip data
- On the Benchmark tab, emphasize *"our dots are further bottom-left"* — judges understand that instantly
- For the 3D chart, **rotate it slowly** — it's visually impressive
