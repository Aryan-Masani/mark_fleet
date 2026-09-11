/**
 * App.jsx — Root application with sidebar + tab layout.
 */
import { useState } from "react";
import "./index.css";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ProgressBar from "./components/ProgressBar.jsx";
import ParetoTab from "./tabs/ParetoTab.jsx";
import AllocationTab from "./tabs/AllocationTab.jsx";
import BaselineTab from "./tabs/BaselineTab.jsx";
import ReportTab from "./tabs/ReportTab.jsx";
import { useOptimization } from "./hooks/useOptimization.js";

const TABS = [
  { id: "pareto",     label: "📈 Interactive Pareto Trade-offs" },
  { id: "allocation", label: "📋 Fleet Allocation & Emissions" },
  { id: "baseline",   label: "⚔️ Classical NSGA-II Benchmark" },
  { id: "report",     label: "📄 Report Export (PDF/Markdown)" },
];

export default function App() {
  const [activeTab, setActiveTab]   = useState("pareto");
  const [selectedIdx, setSelectedIdx] = useState(0);

  const {
    status, progress, results, error,
    runOptimization, downloadPdf, downloadMarkdown, fetchDefaultScenario,
  } = useOptimization();

  const isRunning = status === "running";

  return (
    <div className="app-layout">
      <Sidebar
        onRun={runOptimization}
        isRunning={isRunning}
        fetchDefaultScenario={fetchDefaultScenario}
      />

      <main className="main-content">
        <Header />

        {/* Progress bar */}
        {isRunning && <ProgressBar pct={progress.pct} msg={progress.msg} />}

        {/* Error */}
        {error && (
          <div className="error-banner">
            ⚠️ <strong>Optimization Error:</strong> {error}
          </div>
        )}

        {/* Results */}
        {results ? (
          <>
            {/* Tab nav */}
            <div className="tabs-nav">
              {TABS.map(t => (
                <button
                  key={t.id}
                  className={`tab-btn ${activeTab === t.id ? "active" : ""}`}
                  onClick={() => setActiveTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === "pareto" && (
              <ParetoTab
                results={results}
                selectedIdx={selectedIdx}
                setSelectedIdx={setSelectedIdx}
              />
            )}
            {activeTab === "allocation" && (
              <AllocationTab results={results} selectedIdx={selectedIdx} />
            )}
            {activeTab === "baseline" && (
              <BaselineTab results={results} />
            )}
            {activeTab === "report" && (
              <ReportTab
                results={results}
                selectedIdx={selectedIdx}
                downloadPdf={downloadPdf}
                downloadMarkdown={downloadMarkdown}
              />
            )}
          </>
        ) : !isRunning && (
          /* Empty state */
          <div className="empty-state">
            <div className="empty-icon">🚢</div>
            <h2>Maritime Q — Green Fleet Optimizer</h2>
            <p>
              Configure your fleet size, route parameters, bunkering policies, and
              decarbonization targets in the sidebar, then click <strong>Run Green Fleet Optimization</strong> to compute
              the Pareto-optimal deployment strategy using MOQPSO.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
