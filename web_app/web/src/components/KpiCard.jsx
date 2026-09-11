/* KpiCard.jsx */
export default function KpiCard({ title, value, unit, sub }) {
  return (
    <div className="kpi-card">
      <div className="kpi-title">{title}</div>
      <div className="kpi-value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
