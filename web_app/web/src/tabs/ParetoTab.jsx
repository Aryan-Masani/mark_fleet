/**
 * ParetoTab.jsx — Tab 1: Pareto trade-off charts + KPI cards.
 * Charts exactly match the Streamlit dashboard (plotly_dark template,
 * Viridis 2D scatter with red ring on selected, Turbo 3D scatter).
 */
import { useState, useMemo } from "react";
import Plot from "react-plotly.js";
import KpiCard from "../components/KpiCard.jsx";

// ── Shared layout base (mirrors Streamlit plotly_dark template) ─────────────
const DARK_BASE = {
  paper_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, sans-serif", color: "#a0aec0" },
  legend: { font: { size: 12, color: "#a0aec0" }, bgcolor: "rgba(0,0,0,0)" },
};

export default function ParetoTab({ results, selectedIdx, setSelectedIdx }) {
  const { pareto_solutions: sols, routes } = results;
  const nRoutes = routes.length;

  const [chartMode, setChartMode] = useState("2d");

  // ── Quick-select indices ────────────────────────────────────────────────
  const minCostIdx = useMemo(
    () => sols.reduce((b, s, i) => s.cost_usd   < sols[b].cost_usd   ? i : b, 0), [sols]);
  const minGhgIdx  = useMemo(
    () => sols.reduce((b, s, i) => s.ghg_tons   < sols[b].ghg_tons   ? i : b, 0), [sols]);
  const maxRelIdx  = useMemo(
    () => sols.reduce((b, s, i) => s.on_time_legs > sols[b].on_time_legs ? i : b, 0), [sols]);

  const sel = sols[selectedIdx] || sols[0];

  // ── 2-D Scatter (mirrors px.scatter + go.Scatter ring overlay) ──────────
  // Marker sizes: 16 for selected, 10 for rest (same as Streamlit)
  const markerSizes = sols.map((_, i) => i === selectedIdx ? 16 : 10);

  const scatter2d = {
    data: [
      {
        // Main Pareto cloud — mimics px.scatter with color=OnTime_Legs
        type: "scatter",
        mode: "markers",
        name: "Pareto Front",
        x: sols.map(s => s.cost_usd),
        y: sols.map(s => s.ghg_tons),
        customdata: sols.map(s => [s.unmet_demand]),
        text: sols.map((s, i) => `Sol #${i + 1}`),
        hovertemplate:
          "<b>%{text}</b><br>" +
          "Cost: $%{x:,.0f}<br>" +
          "GHG: %{y:,.1f} t CO2eq<br>" +
          "On-Time Legs: %{marker.color}<br>" +
          "Unmet Demand: %{customdata[0]:,.0f} t<extra></extra>",
        marker: {
          size: markerSizes,
          color: sols.map(s => s.on_time_legs),     // color = OnTime_Legs
          colorscale: "Viridis",
          showscale: true,
          colorbar: {
            title: { text: "On-Time Legs", font: { color: "#a0aec0" } },
            thickness: 14,
            tickfont: { color: "#a0aec0" },
            outlinecolor: "#1f304d",
          },
          line: { width: 0 },
        },
      },
      {
        // Selected solution red ring overlay (mirrors go.Scatter)
        type: "scatter",
        mode: "markers",
        name: `Selected Sol #${selectedIdx + 1}`,
        x: [sel.cost_usd],
        y: [sel.ghg_tons],
        hoverinfo: "skip",
        showlegend: true,
        marker: {
          size: 22,
          color: "rgba(0,0,0,0)",
          line: { color: "#f43f5e", width: 3 },
        },
      },
    ],
    layout: {
      ...DARK_BASE,
      template: "plotly_dark",
      height: 650,
      margin: { l: 60, r: 40, t: 50, b: 60 },
      plot_bgcolor: "rgba(17, 27, 43, 0.6)",
      xaxis: {
        title: { text: "Total Fuel Cost ($)", font: { size: 14 } },
        tickfont: { size: 12 },
        gridcolor: "#1f304d",
        zerolinecolor: "#1f304d",
      },
      yaxis: {
        title: { text: "Lifecycle GHG Emissions (tons CO2eq)", font: { size: 14 } },
        tickfont: { size: 12 },
        gridcolor: "#1f304d",
        zerolinecolor: "#1f304d",
      },
    },
  };

  // ── 3-D Scatter (mirrors px.scatter_3d with Turbo, marker_size=6) ───────
  const scatter3d = {
    data: [
      {
        type: "scatter3d",
        mode: "markers",
        x: sols.map(s => s.cost_usd),
        y: sols.map(s => s.ghg_tons),
        z: sols.map(s => s.on_time_legs),
        text: sols.map((s, i) => `Sol #${i + 1}`),
        hovertemplate:
          "<b>%{text}</b><br>Cost: $%{x:,.0f}<br>GHG: %{y:,.1f} t<br>On-Time: %{z}<extra></extra>",
        marker: {
          size: 6,
          color: sols.map(s => s.ghg_tons),   // color = GHG_Tons (same as Streamlit)
          colorscale: "Turbo",
          showscale: true,
          colorbar: {
            title: { text: "GHG (t CO2eq)", font: { color: "#a0aec0" } },
            thickness: 14,
            tickfont: { color: "#a0aec0" },
          },
        },
      },
    ],
    layout: {
      ...DARK_BASE,
      template: "plotly_dark",
      height: 720,
      margin: { l: 0, r: 0, t: 30, b: 0 },
      scene: {
        // All axes match Streamlit's backgroundcolor
        xaxis: {
          title: "Cost ($)",
          backgroundcolor: "rgba(17,27,43,0.6)",
          gridcolor: "#1f304d",
          color: "#a0aec0",
        },
        yaxis: {
          title: "GHG (t CO2eq)",
          backgroundcolor: "rgba(17,27,43,0.6)",
          gridcolor: "#1f304d",
          color: "#a0aec0",
        },
        zaxis: {
          title: "On-Time Legs",
          backgroundcolor: "rgba(17,27,43,0.6)",
          gridcolor: "#1f304d",
          color: "#a0aec0",
        },
      },
    },
  };

  const fmt = (n, d = 0) =>
    n?.toLocaleString(undefined, { maximumFractionDigits: d }) ?? "-";

  return (
    <div>
      {/* ── Preset quick-selects + chart mode toggle ── */}
      <div className="chart-controls">
        <button className="preset-btn" onClick={() => setSelectedIdx(minCostIdx)}>💰 Min Cost</button>
        <button className="preset-btn" onClick={() => setSelectedIdx(minGhgIdx)}>🌱 Min GHG</button>
        <button className="preset-btn" onClick={() => setSelectedIdx(maxRelIdx)}>⏱️ Max ETA</button>
        <div className="chart-mode-toggle">
          <button
            className={`toggle-btn ${chartMode === "2d" ? "active" : ""}`}
            onClick={() => setChartMode("2d")}
          >
            2D Scatter (Cost vs GHG)
          </button>
          <button
            className={`toggle-btn ${chartMode === "3d" ? "active" : ""}`}
            onClick={() => setChartMode("3d")}
          >
            3D Trade-off (Cost vs GHG vs Reliability)
          </button>
        </div>
      </div>

      {/* ── Solution selector ── */}
      <div className="sol-select-wrap">
        <div className="sol-select-label">Select Solution Index off Pareto Front:</div>
        <select
          className="sol-select"
          value={selectedIdx}
          onChange={e => setSelectedIdx(+e.target.value)}
        >
          {sols.map((s, i) => (
            <option key={i} value={i}>
              Sol #{i + 1} — ${fmt(s.cost_usd)} | {s.ghg_tons.toFixed(1)} t CO2 | {s.on_time_legs.toFixed(0)} on-time legs
            </option>
          ))}
        </select>
      </div>

      <hr />

      {/* ── Full-width chart (mirrors st.plotly_chart use_container_width=True) ── */}
      <div className="card">
        <div className="card-title">📊 Pareto Optimal Trade-off Surface (MOQPSO)</div>
        {chartMode === "2d" ? (
          <Plot
            data={scatter2d.data}
            layout={scatter2d.layout}
            config={{ responsive: true, displaylogo: false, displayModeBar: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        ) : (
          <Plot
            data={scatter3d.data}
            layout={scatter3d.layout}
            config={{ responsive: true, displaylogo: false, displayModeBar: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        )}
      </div>

      <hr />

      {/* ── Solution details + KPI cards ── */}
      <div className="two-col">
        {/* Left: solution detail table */}
        <div className="card">
          <div className="card-title">🎯 Selected Solution Details</div>
          <table className="detail-table">
            <tbody>
              <tr>
                <td>💵 Fuel Cost</td>
                <td>${fmt(sel.cost_usd, 2)}</td>
              </tr>
              <tr>
                <td>💨 GHG Emissions</td>
                <td>{sel.ghg_tons?.toFixed(2)} t CO2eq</td>
              </tr>
              <tr>
                <td>⏰ Schedule Reliability</td>
                <td>
                  {sel.on_time_legs?.toFixed(0)}/{nRoutes} legs ({sel.reliability_pct?.toFixed(0)}%)
                </td>
              </tr>
              <tr>
                <td>📦 Unmet Cargo Demand</td>
                <td>{fmt(sel.unmet_demand)} tons</td>
              </tr>
              <tr>
                <td>⚖️ Feasibility</td>
                <td>
                  {sel.cii_violations === 0 && sel.fuel_violations === 0
                    ? "✅ 100% Compliant"
                    : `⚠️ ${sel.cii_violations} CII / ${sel.fuel_violations} Fuel Violations`}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Right: KPI cards */}
        <div className="card">
          <div className="card-title">🏆 Deployment KPIs</div>
          <div className="kpi-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <KpiCard
              title="Total Fuel Cost"
              value={`$${fmt(sel.raw_j1_cost)}`}
              sub={`Avg: $${fmt(sel.raw_j1_cost / Math.max(1, sel.assignments.length))}/voyage`}
            />
            <KpiCard
              title="Lifecycle GHG Emissions"
              value={(sel.raw_j2_emissions / 1000).toFixed(1)}
              unit=" t CO2eq"
              sub="Well-to-wake cumulative"
            />
            <KpiCard
              title="Schedule Reliability"
              value={`${sel.raw_j3_reliability?.toFixed(0)} / ${nRoutes}`}
              sub={`${((sel.raw_j3_reliability / nRoutes) * 100).toFixed(0)}% legs on target ETA`}
            />
            <KpiCard
              title="Green Cargo Share"
              value={`${sel.green_share_pct?.toFixed(0)}%`}
              sub={`${fmt(sel.green_cargo_tons)} t via LNG/MeOH/H₂/NH₃`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
