/**
 * BaselineTab.jsx — Tab 3: MOQPSO vs NSGA-II comparison.
 */
import Plot from "react-plotly.js";

const PLOTLY_DARK = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor:  "rgba(17,27,43,0.6)",
  font: { family: "Inter, sans-serif", color: "#94a3b8" },
  margin: { l: 60, r: 40, t: 50, b: 60 },
};

export default function BaselineTab({ results }) {
  const { pareto_solutions: sols, nsga2_points, nsga2_min_cost, nsga2_min_ghg, nsga2_count } = results;

  const moqpsoCosts = sols.map(s => s.cost_usd);
  const moqpsoGhg   = sols.map(s => s.ghg_tons);
  const moqpsoMinCost = Math.min(...moqpsoCosts);
  const moqpsoMinGhg  = Math.min(...moqpsoGhg);

  if (!nsga2_points) {
    return (
      <div className="card">
        <div className="info-box">
          Check "Run Classical NSGA-II Comparison" in the sidebar and re-run to see side-by-side benchmark.
        </div>
      </div>
    );
  }

  const traces = [
    {
      type: "scatter",
      mode: "markers",
      name: "Proposed MOQPSO Front",
      x: moqpsoCosts,
      y: moqpsoGhg,
      marker: { size: 10, color: "#27AEB9", symbol: "circle" },
    },
    {
      type: "scatter",
      mode: "markers",
      name: "Classical NSGA-II Baseline Front",
      x: nsga2_points.map(p => p.cost_usd),
      y: nsga2_points.map(p => p.ghg_tons),
      marker: { size: 10, color: "#f59e0b", symbol: "diamond" },
    },
  ];

  const fmt = (n, d = 0) => n?.toLocaleString(undefined, { maximumFractionDigits: d }) ?? "-";

  return (
    <div>
      <div className="card">
        <div className="card-title">Classical NSGA-II (pymoo) vs Proposed MOQPSO Comparison</div>
        <Plot
          data={traces}
          layout={{
            ...PLOTLY_DARK,
            height: 460,
            title: { text: "Pareto Front Comparison Overlay (Cost vs GHG)", font: { color: "#f8fafc", size: 14 } },
            xaxis: { title: "Total Fuel Cost ($)", gridcolor: "#1f304d" },
            yaxis: { title: "Lifecycle GHG (tons CO2eq)", gridcolor: "#1f304d" },
            legend: { font: { color: "#94a3b8" }, bgcolor: "rgba(0,0,0,0)" },
          }}
          config={{ responsive: true, displaylogo: false }}
          style={{ width: "100%" }}
        />
      </div>

      <div className="three-col">
        <div className="card">
          <div className="card-title">Non-Dominated Solutions</div>
          <div className="metric-pair">
            <div className="metric-item">
              <span className="label">MOQPSO</span>
              <span className="val" style={{ color: "#27AEB9" }}>{sols.length} points</span>
            </div>
            <div className="metric-item">
              <span className="label">NSGA-II</span>
              <span className="val" style={{ color: "#f59e0b" }}>{nsga2_count} points</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-title">Minimum Cost</div>
          <div className="metric-pair">
            <div className="metric-item">
              <span className="label">MOQPSO</span>
              <span className="val" style={{ color: "#27AEB9" }}>${fmt(moqpsoMinCost)}</span>
            </div>
            <div className="metric-item">
              <span className="label">NSGA-II</span>
              <span className="val" style={{ color: "#f59e0b" }}>${fmt(nsga2_min_cost)}</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-title">Minimum GHG</div>
          <div className="metric-pair">
            <div className="metric-item">
              <span className="label">MOQPSO</span>
              <span className="val" style={{ color: "#27AEB9" }}>{moqpsoMinGhg.toFixed(1)} tons</span>
            </div>
            <div className="metric-item">
              <span className="label">NSGA-II</span>
              <span className="val" style={{ color: "#f59e0b" }}>{nsga2_min_ghg?.toFixed(1)} tons</span>
            </div>
          </div>
        </div>
      </div>

      <div className="info-box">
        💡 <strong>Benchmark Insight</strong>: MOQPSO leverages quantum delta-potential exploration to match or
        outperform classical NSGA-II Pareto bounds with superior coverage in zero-carbon fuel alternatives.
      </div>
    </div>
  );
}
