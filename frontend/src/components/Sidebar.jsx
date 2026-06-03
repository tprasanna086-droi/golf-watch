import React from 'react';

const riskColors = {
  critical: '#ff2d2d',
  high: '#ff8c00',
  moderate: '#ffd700',
  low: '#00c853',
};

export default function Sidebar({ lakes = [], selectedLake, onLakeClick, loading }) {
  const getBadgeStyle = (riskClass) => {
    const color = riskColors[riskClass?.toLowerCase()] || '#94a3b8';
    return {
      backgroundColor: `${color}15`,
      color: color,
      border: `1px solid ${color}30`,
    };
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Glacial Lakes</h2>
        <span className="count-badge">{lakes.length} monitored</span>
      </div>

      <div className="sidebar-content">
        {loading ? (
          <div className="loading-state">
            <span className="spinner"></span>
            <p>Loading lakes...</p>
          </div>
        ) : lakes.length === 0 ? (
          <div className="empty-state">No lakes found</div>
        ) : (
          <div className="lake-list">
            {lakes.map((lake) => {
              const isSelected = selectedLake && selectedLake.id === lake.id;
              return (
                <div
                  key={lake.id}
                  className={`lake-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => onLakeClick && onLakeClick(lake)}
                >
                  <div className="lake-card-header">
                    <h3>{lake.name}</h3>
                    <span
                      className="risk-badge"
                      style={getBadgeStyle(lake.risk_class)}
                    >
                      {lake.risk_class}
                    </span>
                  </div>
                  <div className="lake-card-body">
                    <div className="info-row">
                      <span className="info-label">District:</span>
                      <span className="info-value">{lake.district}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Basin:</span>
                      <span className="info-value">{lake.basin}</span>
                    </div>
                    <div className="info-row">
                      <span className="info-label">Initial Area:</span>
                      <span className="info-value">{lake.initial_area_ha} ha</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
