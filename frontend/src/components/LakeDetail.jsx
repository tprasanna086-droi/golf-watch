import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

export default function LakeDetail({ lake, history = [], loading }) {
  if (!lake) {
    return (
      <div className="detail-panel">
        <div className="detail-empty">
          <div className="detail-empty-icon">🏔️</div>
          <p>Select a lake from the sidebar or map to view real-time metrics and historical trends.</p>
        </div>
      </div>
    );
  }

  // Get latest metrics from history if available, otherwise fallback
  const latestObs = history.length > 0 ? history[history.length - 1] : null;

  const areaVal = latestObs ? latestObs.area_ha.toFixed(2) : '—';
  const ndwiVal = latestObs ? latestObs.ndwi_mean.toFixed(3) : '—';
  const turbidityVal = latestObs ? latestObs.turbidity_index.toFixed(3) : '—';
  const riskClass = lake.risk_class || '—';

  // Format date for chart X-axis
  const chartData = history.map((obs) => ({
    ...obs,
    formattedDate: new Date(obs.observed_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    }),
  }));

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div className="detail-name">{lake.name}</div>
        <div className="detail-sub">
          {lake.basin} Basin, {lake.district} District
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Area</div>
          <div className="stat-value">
            {areaVal}
            {latestObs && <span className="stat-unit">ha</span>}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">NDWI</div>
          <div className="stat-value">{ndwiVal}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Turbidity</div>
          <div className="stat-value">{turbidityVal}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Risk</div>
          <div className="stat-value" style={{ color: `var(--risk-${riskClass.toLowerCase()})`, fontSize: '16px', textTransform: 'uppercase', marginTop: '4px' }}>
            {riskClass}
          </div>
        </div>
      </div>

      <div className="chart-section">
        <div className="chart-title">Surface Area History</div>
        {loading ? (
          <div className="loading-text">Loading history...</div>
        ) : history.length === 0 ? (
          <div className="no-history">No observation history yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData} margin={{ top: 10, right: 5, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="formattedDate"
                stroke="#64748b"
                fontSize={9}
                tickLine={false}
              />
              <YAxis
                stroke="#64748b"
                fontSize={9}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1a2235',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  fontSize: '11px',
                  color: '#e2e8f0',
                }}
              />
              <Line
                type="monotone"
                dataKey="area_ha"
                stroke="#00e5ff"
                strokeWidth={2}
                dot={{ r: 2, fill: '#00e5ff', strokeWidth: 0 }}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
