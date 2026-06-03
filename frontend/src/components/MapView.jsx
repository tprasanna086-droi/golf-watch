import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import AlertsBar from './AlertsBar';

const NepalCenter = [28.3949, 84.1240];

const riskColors = {
  critical: '#ff2d2d',
  high: '#ff8c00',
  moderate: '#ffd700',
  low: '#00c853',
};

const alertColors = {
  emergency: '#ff2d2d',
  warning: '#ff8c00',
  watch: '#ffd700',
};

export default function MapView({ lakes = [], alerts = [], onLakeClick }) {
  const getLakeColor = (riskClass) => {
    return riskColors[riskClass?.toLowerCase()] || '#94a3b8';
  };

  const getAlertColor = (level) => {
    return alertColors[level?.toLowerCase()] || '#38bdf8';
  };

  return (
    <div className="map-container" style={{ width: '100%', height: '100%' }}>
      <div className="map-header">
        <div className="map-header-dot"></div>
        <div className="map-header-text">Live Monitoring</div>
      </div>

      <MapContainer
        center={NepalCenter}
        zoom={7}
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Render Lakes */}
        {lakes.map((lake) => {
          const lat = parseFloat(lake.lat);
          const lon = parseFloat(lake.lon);
          if (isNaN(lat) || isNaN(lon)) return null;

          return (
            <CircleMarker
              key={`lake-${lake.id}`}
              center={[lat, lon]}
              radius={8}
              fillColor={getLakeColor(lake.risk_class)}
              color="#ffffff"
              weight={1.5}
              fillOpacity={0.8}
              eventHandlers={{
                click: () => onLakeClick && onLakeClick(lake),
              }}
            >
              <Tooltip direction="top" offset={[0, -5]} opacity={0.9}>
                <div style={{ padding: '2px 4px' }}>
                  <strong>{lake.name}</strong>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                    District: {lake.district} | Risk: {lake.risk_class}
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Render Active Alerts (Pulsing Effect) */}
        {alerts.map((alert) => {
          const lat = parseFloat(alert.lat);
          const lon = parseFloat(alert.lon);
          if (isNaN(lat) || isNaN(lon)) return null;

          return (
            <CircleMarker
              key={`alert-${alert.id}`}
              center={[lat, lon]}
              radius={16}
              fill={false}
              color={getAlertColor(alert.alert_level)}
              weight={2}
              opacity={0.6}
              dashArray="4, 4"
            />
          );
        })}
      </MapContainer>

      <AlertsBar alerts={alerts} />
    </div>
  );
}
