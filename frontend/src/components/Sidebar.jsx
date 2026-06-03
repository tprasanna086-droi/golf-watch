import React, { useState } from 'react';

export default function Sidebar({ lakes = [], selectedLake, onLakeClick, loading }) {
  const [filter, setFilter] = useState('all');

  const filteredLakes = lakes.filter((lake) => {
    if (filter === 'all') return true;
    if (filter === 'critical') return lake.risk_class?.toLowerCase() === 'critical';
    if (filter === 'high') return lake.risk_class?.toLowerCase() === 'high';
    if (filter === 'watch') {
      return (
        lake.risk_class?.toLowerCase() === 'moderate' ||
        lake.risk_class?.toLowerCase() === 'low'
      );
    }
    return true;
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🏔️</div>
          <div className="sidebar-logo-text">glof<span>-watch</span></div>
        </div>
        
        <div className="sidebar-filter">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={`filter-btn ${filter === 'critical' ? 'active' : ''}`}
            onClick={() => setFilter('critical')}
          >
            Critical
          </button>
          <button
            className={`filter-btn ${filter === 'high' ? 'active' : ''}`}
            onClick={() => setFilter('high')}
          >
            High
          </button>
          <button
            className={`filter-btn ${filter === 'watch' ? 'active' : ''}`}
            onClick={() => setFilter('watch')}
          >
            Watch
          </button>
        </div>
      </div>

      <div className="sidebar-list">
        {loading ? (
          <div className="loading-text">Loading lakes...</div>
        ) : filteredLakes.length === 0 ? (
          <div className="loading-text">No lakes match filter</div>
        ) : (
          filteredLakes.map((lake) => {
            const isSelected = selectedLake && selectedLake.id === lake.id;
            const riskClass = lake.risk_class?.toLowerCase() || 'low';
            
            return (
              <div
                key={lake.id}
                className={`lake-card ${isSelected ? 'selected' : ''}`}
                onClick={() => onLakeClick && onLakeClick(lake)}
              >
                <div className="lake-card-header">
                  <div className="lake-card-name">{lake.name}</div>
                  <span className={`risk-badge ${riskClass}`}>
                    {lake.risk_class}
                  </span>
                </div>
                <div className="lake-card-meta">
                  <span>{lake.district}</span>
                  <span>•</span>
                  <span>{lake.initial_area_ha?.toFixed(2)} ha</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
