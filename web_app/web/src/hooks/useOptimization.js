/**
 * useOptimization.js — manages SSE streaming, API calls, and result caching.
 */
import { useState, useRef, useCallback } from "react";

const API = "http://localhost:8000";

export function useOptimization() {
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [progress, setProgress] = useState({ pct: 0, msg: "" });
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const esRef = useRef(null);
  const runIdRef = useRef(null);

  const runOptimization = useCallback(async (params) => {
    // close any previous SSE
    if (esRef.current) esRef.current.close();
    setStatus("running");
    setProgress({ pct: 0, msg: "Submitting optimization request..." });
    setResults(null);
    setError(null);

    try {
      // Start the optimization job
      const startRes = await fetch(`${API}/api/run-optimization`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!startRes.ok) throw new Error(await startRes.text());
      const { run_id } = await startRes.json();
      runIdRef.current = run_id;

      // Open SSE stream
      const es = new EventSource(`${API}/api/stream/${run_id}`);
      esRef.current = es;

      es.onmessage = async (e) => {
        const data = JSON.parse(e.data);
        setProgress({ pct: data.pct, msg: data.msg });

        if (data.done) {
          es.close();
          // Fetch full results
          const resRes = await fetch(`${API}/api/results/${run_id}`);
          if (!resRes.ok) throw new Error(await resRes.text());
          const result = await resRes.json();
          setResults(result);
          setStatus("done");
        } else if (data.error) {
          es.close();
          setError(data.msg);
          setStatus("error");
        }
      };

      es.onerror = () => {
        es.close();
        setError("Connection to server lost");
        setStatus("error");
      };
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, []);

  const downloadPdf = useCallback((solIdx) => {
    if (!runIdRef.current) return;
    window.open(`${API}/api/report/pdf/${runIdRef.current}/${solIdx}`, "_blank");
  }, []);

  const downloadMarkdown = useCallback((solIdx) => {
    if (!runIdRef.current) return;
    window.open(`${API}/api/report/markdown/${runIdRef.current}/${solIdx}`, "_blank");
  }, []);

  const fetchDefaultScenario = useCallback(async (fleetSize, nRoutes) => {
    const res = await fetch(`${API}/api/default-scenario?fleet_size=${fleetSize}&n_routes=${nRoutes}`);
    return res.json();
  }, []);

  return {
    status, progress, results, error,
    runOptimization, downloadPdf, downloadMarkdown, fetchDefaultScenario,
  };
}
