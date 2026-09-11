/**
 * AllocationTab.jsx — Tab 2: Vessel-to-route allocation table + charts.
 */
import Plot from "react-plotly.js";

const PLOTLY_DARK = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor:  "rgba(17,27,43,0.6)",
  font: { family: "Inter, sans-serif", color: "#94a3b8" },
  margin: { l: 50, r: 30, t: 30, b: 50 },
};

const FUEL_COLORS = {
  HFO:      "#94a3b8",
  LNG:      "#27AEB9",
  Methanol: "#34d399",
  Hydrogen: "#a78bfa",
  Ammonia:  "#f472b6",
};

export default function AllocationTab({ results, selectedIdx }) {
  const sol = results.pareto_solutions[selectedIdx] || results.pareto_solutions[0];
  const assignments = sol.assignments || [];

  // Fuel mix counts
  const fuelCounts = {};
  assignments.forEach(a => { fuelCounts[a.fuel_type] = (fuelCounts[a.fuel_type] || 0) + 1; });

  const pieData = [{
    type: "pie",
    labels: Object.keys(fuelCounts),
    values: Object.values(fuelCounts),
    hole: 0.45,
    marker: { colors: Object.keys(fuelCounts).map(f => FUEL_COLORS[f] || "#888") },
    textfont: { color: "#f8fafc" },
  }];

  // GHG & cost per vessel
  const vessels = [...new Set(assignments.map(a => a.vessel_id))];
  const barData = [
    {
      type: "bar",
      name: "Cost ($)",
      x: assignments.map(a => a.vessel_id),
      y: assignments.map(a => a.fuel_cost),
      marker: { color: "#27AEB9" },
    },
    {
      type: "bar",
      name: "Emissions (t CO2eq)",
      x: assignments.map(a => a.vessel_id),
      y: assignments.map(a => a.ghg_emissions_tons),
      marker: { color: "#f472b6" },
    },
  ];

  return (
    <div>
      <div className="card">
        <div className="card-title">Vessel-to-Route Allocation Matrix (Solution #{selectedIdx + 1})</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {["Vessel ID","Type","Route","Origin → Dest","Speed (kts)","Fuel","Cargo (t)","Load %","Transit (h)","ETA","Fuel (t)","Cost ($)","GHG (t CO2eq)","CII (g/t-nm)"].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assignments.map((a, i) => (
                <tr key={i}>
                  <td>{a.vessel_id}</td>
                  <td>{a.vessel_type}</td>
                  <td>{a.route_id}</td>
                  <td>{a.origin_port} → {a.destination_port}</td>
                  <td>{a.speed_knots.toFixed(1)}</td>
                  <td>
                    <span style={{ color: FUEL_COLORS[a.fuel_type] || "#fff", fontWeight: 600 }}>
                      {a.fuel_type}
                    </span>
                  </td>
                  <td>{a.cargo_load_tons.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                  <td>{(a.cargo_load_fraction * 100).toFixed(0)}%</td>
                  <td>{a.transit_time_hours.toFixed(1)}</td>
                  <td className={a.on_time ? "badge-green" : "badge-red"}>
                    {a.on_time ? "✅ On-Time" : "⚠️ Delayed"}
                  </td>
                  <td>{a.fuel_consumption_tons.toFixed(1)}</td>
                  <td>${a.fuel_cost.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                  <td>{a.ghg_emissions_tons.toFixed(1)}</td>
                  <td>{a.cii_actual?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <div className="card-title">Fuel Mix Distribution</div>
          <Plot
            data={pieData}
            layout={{
              ...PLOTLY_DARK,
              height: 320,
              margin: { l: 20, r: 20, t: 20, b: 20 },
              legend: { font: { color: "#94a3b8" } },
            }}
            config={{ responsive: true, displaylogo: false }}
            style={{ width: "100%" }}
          />
        </div>

        <div className="card">
          <div className="card-title">GHG Emissions & Fuel Cost by Vessel</div>
          <Plot
            data={barData}
            layout={{
              ...PLOTLY_DARK,
              height: 320,
              barmode: "group",
              xaxis: { tickfont: { size: 10 }, gridcolor: "#1f304d" },
              yaxis: { gridcolor: "#1f304d" },
              legend: { font: { color: "#94a3b8" } },
            }}
            config={{ responsive: true, displaylogo: false }}
            style={{ width: "100%" }}
          />
        </div>
      </div>
    </div>
  );
}
