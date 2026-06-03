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

const riskColors = {
  critical: '#ff2d2d',
  high: '#ff8c00',
  moderate: '#ffd700',
  low: '#00c853',
};

export default function LakeDetail({ lake, history = [], loading }) {
  if (!lake) {
    return (
      <div className="lake-detail-empty">
        <p>Select a lake from the sidebar or map to view details</p>
      </div>
    );
  }

  const getBadgeStyle = (riskClass) => {
    const color = riskColors[riskClass?.toLowerCase()] || '#94a3b8';
    return {
      backgroundColor: `${color}15`,
      color: color,
      border: `1px solid ${color}30`,
    };
  };

  // Format date for chart X-axis
  const chartData = history.map((obs) => ({
    ...obs,
    formattedDate: new Date(obs.observed_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: '2-digit',
    }),
  }));

  return (
    <section className="lake-detail">
      <div className="detail-header">
        <h2>{lake.name}</h2>
        <div className="meta-row">
          <span className="risk-badge" style={getBadgeStyle(lake.risk_class)}>
            {lake.risk_class}
          </span>
          <span className="basin-badge">{lake.basin} Basin</span>
        </div>
      </div>

      <div className="detail-content">
        <div className="section-title">Details</div>
        <div className="detail-grid">
          <div className="detail-item">
            <span className="label">District</span>
            <span className="value">{lake.district}</span>
          </div>
          <div className="detail-item">
            <span className="label">Coordinates</span>
            <span className="value">{parseFloat(lake.lat).toFixed(4)}°, {parseFloat(lake.lon).toFixed(4)}°</span>
          </div>
          <div className="detail-item">
            <span className="label">Baseline Area</span>
            <span className="value">{lake.initial_area_ha} ha</span>
          </div>
          {history.length > 0 && (
            <div className="detail-item">
              <span className="label">Latest Area</span>
              <span className="value">{history[history.length - 1].area_ha.toFixed(2)} ha</span>
            </div>
          )}
        </div>

        <div className="section-title">Surface Area History (Hectares)</div>
        {loading ? (
          <div className="loading-state-mini">
            <span className="spinner"></span>
            <p>Loading history...</p>
          </div>
        ) : history.length === 0 ? (
          <div className="empty-history">
            <p>No observation history yet</p>
          </div>
        ) : (
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="formattedDate"
                  stroke="#64748b"
                  fontSize={10}
                  tickLine={false}
                />
                <YAxis
                  stroke="#64748b"
                  fontSize={10}
                  tickLine={false}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a2235',
                    border: '1px solid #1e293b',
                    borderRadius: '6px',
                    fontSize: '12px',
                    color: '#e2e8f0',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="area_ha"
                  stroke="#00e5ff"
                  strokeWidth={2}
                  dot={{ r: 3, fill: '#00e5ff', strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {history.length > 0 && (
          <>
            <div className="section-title">Spectral Indices</div>
            <div className="stats-row">
              <div className="stat-card">
                <span className="stat-label">Mean NDWI</span>
                <span className="stat-value">
                  {history[history.length - 1].ndwi_mean.toFixed(3)}
                </span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Turbidity Index</span>
                <span className="stat-value">
                  {history[history.length - 1].turbidity_index.toFixed(3)}
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
