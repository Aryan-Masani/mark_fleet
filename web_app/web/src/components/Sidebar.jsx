/**
 * Sidebar.jsx — All scenario & optimizer controls.
 * Mirrors the 4 Streamlit sidebar expanders exactly.
 */
import { useState, useEffect } from "react";

const FUEL_POLICY_OPTIONS = [
  "Pareto Multi-Fuel Free Choice (Optimizer Selects)",
  "Force Zero-Carbon Only (Hydrogen / Ammonia)",
  "Force Transitional LNG",
  "Force Green Methanol",
  "Force Conventional HFO Baseline",
];

function SidebarSection({ title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="sidebar-section">
      <div className="sidebar-section-header" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <span>{open ? "▲" : "▼"}</span>
      </div>
      <div className={`sidebar-section-body ${open ? "" : "collapsed"}`}>
        {children}
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <div className="toggle-item">
      <label className="toggle-switch">
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="toggle-slider" />
      </label>
      <span>{label}</span>
    </div>
  );
}

export default function Sidebar({ onRun, isRunning, fetchDefaultScenario }) {
  const [fleetSize, setFleetSize]   = useState(5);
  const [nRoutes, setNRoutes]       = useState(3);
  const [swarmSize, setSwarmSize]   = useState(30);
  const [maxEvals, setMaxEvals]     = useState(900);
  const [modelType, setModelType]   = useState("quantum");
  const [runNsga2, setRunNsga2]     = useState(true);
  const [seed, setSeed]             = useState(42);
  const [cii, setCii]               = useState(1.0);
  const [fuelPolicy, setFuelPolicy] = useState(FUEL_POLICY_OPTIONS[0]);

  const [ports, setPorts]           = useState([]);
  const [portFuelAvail, setPortFuelAvail] = useState({});
  const [shorePower, setShorePower] = useState({});

  // Load default scenario whenever fleet/route changes
  useEffect(() => {
    fetchDefaultScenario(fleetSize, nRoutes).then(data => {
      const ps = data.ports || [];
      setPorts(ps);
      const pfa = {};
      const sp  = {};
      ps.forEach(p => {
        pfa[p] = { HFO: true, LNG: true, Methanol: true, Hydrogen: ["Rotterdam"].includes(p), Ammonia: ["Rotterdam","Singapore"].includes(p) };
        sp[p]  = ["Rotterdam","Shanghai"].includes(p);
      });
      setPortFuelAvail(pfa);
      setShorePower(sp);
    });
  }, [fleetSize, nRoutes, fetchDefaultScenario]);

  const handleRun = () => {
    const portFuelPayload = {};
    ports.forEach(p => {
      const f = portFuelAvail[p] || {};
      portFuelPayload[p] = {
        HFO: f.HFO ? 1.0 : 0.0, LNG: f.LNG ? 1.0 : 0.0,
        Methanol: f.Methanol ? 1.0 : 0.0, Hydrogen: f.Hydrogen ? 1.0 : 0.0,
        Ammonia: f.Ammonia ? 1.0 : 0.0,
      };
    });
    onRun({
      fleet_size: fleetSize, n_routes: nRoutes, swarm_size: swarmSize,
      max_evaluations: maxEvals, model_type: modelType, seed,
      run_nsga2: runNsga2, cii_stringency: cii,
      fuel_override_mode: fuelPolicy,
      port_fuel_avail: portFuelPayload,
      shore_power: Object.fromEntries(ports.map(p => [p, shorePower[p] ?? false])),
    });
  };

  const toggleFuel = (port, fuel, val) => {
    setPortFuelAvail(prev => ({
      ...prev, [port]: { ...prev[port], [fuel]: val },
    }));
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h2>⚙️ Scenario & Optimizer</h2>
        <p>Controls for Green Fleet Optimization</p>
      </div>

      {/* 1. Fleet & Route */}
      <SidebarSection title="🚢 1. Fleet & Route Setup">
        <div className="form-group">
          <label className="form-label">Fleet Size (Vessels): <strong>{fleetSize}</strong></label>
          <input type="range" min={3} max={8} step={1} value={fleetSize} onChange={e => setFleetSize(+e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Active Routes: <strong>{nRoutes}</strong></label>
          <input type="range" min={2} max={5} step={1} value={nRoutes} onChange={e => setNRoutes(+e.target.value)} />
        </div>
      </SidebarSection>

      {/* 2. Port Bunkering */}
      <SidebarSection title="⚓ 2. Port Bunkering & Shore Power">
        {ports.map(port => (
          <div key={port} className="port-section">
            <div className="port-name">🛢 {port}</div>
            <div className="checkbox-grid">
              {["HFO","LNG","Methanol","Hydrogen","Ammonia"].map(fuel => (
                <label key={fuel} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={portFuelAvail[port]?.[fuel] ?? false}
                    onChange={e => toggleFuel(port, fuel, e.target.checked)}
                  />
                  {fuel}
                </label>
              ))}
            </div>
          </div>
        ))}
        <div className="form-group" style={{ marginTop: 8 }}>
          <div className="form-label">🔌 Shore Power (Cold-Ironing)</div>
          <div className="toggle-row">
            {ports.map(port => (
              <Toggle
                key={port}
                label={port}
                checked={shorePower[port] ?? false}
                onChange={val => setShorePower(prev => ({ ...prev, [port]: val }))}
              />
            ))}
          </div>
        </div>
      </SidebarSection>

      {/* 3. Decarbonization Policy */}
      <SidebarSection title="🌱 3. Decarbonization Policy & Fuel Mix">
        <div className="form-group">
          <label className="form-label">Fuel-Type-Mix Policy Override</label>
          <select value={fuelPolicy} onChange={e => setFuelPolicy(e.target.value)}>
            {FUEL_POLICY_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">CII Regulatory Bound Multiplier: <strong>{cii.toFixed(2)}x</strong></label>
          <input type="range" min={0.7} max={1.3} step={0.05} value={cii} onChange={e => setCii(+e.target.value)} />
          <div className="caption">Lower = stricter IMO carbon intensity target</div>
        </div>
      </SidebarSection>

      {/* 4. Algorithm */}
      <SidebarSection title="🔬 4. Algorithm & Engine Parameters" defaultOpen={false}>
        <div className="form-group">
          <div className="form-label">D1 Prediction Model</div>
          <div className="radio-group">
            <label className="radio-item">
              <input type="radio" checked={modelType === "quantum"} onChange={() => setModelType("quantum")} />
              Quantum-Inspired Model (QIEA)
            </label>
            <label className="radio-item">
              <input type="radio" checked={modelType === "baseline"} onChange={() => setModelType("baseline")} />
              Classical XGBoost Baseline
            </label>
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Swarm Size: <strong>{swarmSize}</strong></label>
          <input type="range" min={15} max={60} step={5} value={swarmSize} onChange={e => setSwarmSize(+e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Max Evaluations: <strong>{maxEvals}</strong></label>
          <input type="range" min={300} max={2000} step={100} value={maxEvals} onChange={e => setMaxEvals(+e.target.value)} />
        </div>
        <div className="form-group">
          <label className="checkbox-item">
            <input type="checkbox" checked={runNsga2} onChange={e => setRunNsga2(e.target.checked)} />
            Run Classical NSGA-II Comparison (pymoo)
          </label>
        </div>
        <div className="form-group">
          <label className="form-label">Random Seed</label>
          <input type="number" value={seed} onChange={e => setSeed(+e.target.value)} />
        </div>
      </SidebarSection>

      <button className="run-btn" onClick={handleRun} disabled={isRunning}>
        {isRunning ? "⏳ Running Optimization..." : "🚀 Run Green Fleet Optimization"}
      </button>
    </aside>
  );
}
