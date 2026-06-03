import React from 'react';

const alertStyles = {
  emergency: {
    bg: 'rgba(255, 45, 45, 0.15)',
    border: '1px solid rgba(255, 45, 45, 0.40)',
    color: '#ff2d2d',
    dot: '#ff2d2d',
  },
  warning: {
    bg: 'rgba(255, 140, 0, 0.15)',
    border: '1px solid rgba(255, 140, 0, 0.40)',
    color: '#ff8c00',
    dot: '#ff8c00',
  },
  watch: {
    bg: 'rgba(255, 215, 0, 0.15)',
    border: '1px solid rgba(255, 215, 0, 0.40)',
    color: '#ffd700',
    dot: '#ffd700',
  },
};

export default function AlertsBar({ alerts = [] }) {
  if (alerts.length === 0) return null;

  const getStyle = (level) => {
    return alertStyles[level?.toLowerCase()] || {
      bg: 'rgba(56, 189, 248, 0.15)',
      border: '1px solid rgba(56, 189, 248, 0.4)',
      color: '#38bdf8',
      dot: '#38bdf8',
    };
  };

  return (
    <div className="alerts-bar">
      <div className="alerts-bar-label">Active Alerts</div>
      <div className="alerts-ticker">
        {alerts.map((alert) => {
          const style = getStyle(alert.alert_level);
          const delta = parseFloat(alert.area_delta_pct || 0);
          const sign = delta >= 0 ? '+' : '';

          return (
            <div
              key={`ticker-alert-${alert.id}`}
              className="alert-pill"
              style={{
                backgroundColor: style.bg,
                border: style.border,
                color: style.color,
              }}
            >
              <span
                className="alert-dot"
                style={{ backgroundColor: style.dot }}
              ></span>
              <strong>{alert.lake_name}</strong>
              <span>
                {sign}
                {delta.toFixed(1)}% area
              </span>
              <span style={{ opacity: 0.8, fontSize: '9px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                ({alert.alert_level})
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
