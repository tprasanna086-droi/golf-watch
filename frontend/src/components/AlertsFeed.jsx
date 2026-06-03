import React from 'react';

const alertIcons = {
  emergency: '🔴',
  warning: '⚠️',
  watch: '👁️',
};

const riskColors = {
  emergency: '#ff2d2d',
  warning: '#ff8c00',
  watch: '#ffd700',
};

function timeAgo(dateString) {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (isNaN(date.getTime())) return '—';
    if (diffSecs < 60) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  } catch (e) {
    return '—';
  }
}

export default function AlertsFeed({ alerts = [], onLakeClick }) {
  const getIcon = (level) => alertIcons[level?.toLowerCase()] || '👁️';
  const getColor = (level) => riskColors[level?.toLowerCase()] || '#38bdf8';

  return (
    <div className="alerts-feed">
      <div className="alerts-feed-header">
        <span className="alerts-feed-title">Recent Alerts</span>
        <span className="alerts-count-badge">{alerts.length}</span>
      </div>

      <div style={{ maxHeight: '400px', overflowY: 'auto', paddingRight: '4px' }}>
        {alerts.length === 0 ? (
          <div className="no-alerts">No active alerts</div>
        ) : (
          alerts.map((alert) => {
            const delta = parseFloat(alert.area_delta_pct || 0);
            const sign = delta >= 0 ? '+' : '';
            const color = getColor(alert.alert_level);

            return (
              <div
                key={`feed-alert-${alert.id}`}
                className="alert-row"
                onClick={() =>
                  onLakeClick &&
                  onLakeClick({
                    id: alert.lake_id,
                    name: alert.lake_name,
                    lat: alert.lat,
                    lon: alert.lon,
                  })
                }
              >
                <span className="alert-icon">{getIcon(alert.alert_level)}</span>
                <span className="alert-lake-name">{alert.lake_name}</span>
                <span className="alert-delta" style={{ color }}>
                  {sign}
                  {delta.toFixed(1)}%
                </span>
                <span className="alert-time">{timeAgo(alert.triggered_at)}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
