/* ProgressBar.jsx */
export default function ProgressBar({ pct, msg }) {
  return (
    <div className="progress-wrap">
      <div className="progress-label">
        <span>{msg || "Initializing..."}</span>
        <span>{pct}%</span>
      </div>
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${Math.max(0, pct)}%` }} />
      </div>
    </div>
  );
}
