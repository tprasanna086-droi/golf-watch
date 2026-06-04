import { Fragment, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip,
} from 'react-leaflet';
import { ChevronRight, Search, Settings } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { triggerAnalysis } from '../api/lakes';
import Spinner from '../components/Spinner';
import Toast from '../components/Toast';
import { useAlertsSummary } from '../hooks/useAlertsSummary';
import { useLake } from '../hooks/useLake';
import { useLakes } from '../hooks/useLakes';
import './Dashboard.css';

const NEPAL_CENTER = [28.3949, 84.1240];
const DEFAULT_ZOOM = 7;

const TILE_STREET = {
  url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
};

const TILE_SATELLITE = {
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  attribution:
    '&copy; <a href="https://www.esri.com/">Esri</a> — Esri, Maxar, Earthstar Geographics',
};

const FILTER_CHIPS = ['All', 'Watch', 'Warning', 'Emergency'];

const RISK_FILL = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

const FILTER_TO_RISK = {
  All: null,
  Watch: ['low'],
  Warning: ['medium', 'high'],
  Emergency: ['critical'],
};

const TICKER_TEXT =
  '⚠ EMERGENCY: Tsho Rolpa growing 3× faster than average · ⚠ WARNING: Imja Tsho turbidity spike detected · ✓ Chamlang South observation complete · ';

function MountainIcon({ size = 28 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <ellipse cx="32" cy="52" rx="20" ry="4.5" fill="#10b981" />
      <path fill="#059669" d="M32 10 L52 46 L12 46 Z" />
    </svg>
  );
}

function RiskBadge({ riskClass, large = false }) {
  const normalized = (riskClass || 'low').toLowerCase();
  return (
    <span
      className={`risk-badge risk-badge--${normalized}${large ? ' risk-badge--large' : ''}`}
    >
      {large && <span className="risk-badge__dot" aria-hidden="true" />}
      {normalized}
    </span>
  );
}

function getLakeMetrics(lake, latestObs) {
  if (latestObs) {
    return {
      area: `${(latestObs.area_km2 ?? lake.area_km2 ?? 0).toFixed(2)} km²`,
      ndwi: (latestObs.ndwi_mean ?? 0).toFixed(2),
      turbidity: (latestObs.turbidity_index ?? 0).toFixed(1),
      irregularity: (latestObs.shape_irregularity ?? 0.32).toFixed(2),
    };
  }

  const seed = typeof lake.id === 'number' ? lake.id : 1;
  return {
    area: `${(lake.area_km2 ?? 0).toFixed(2)} km²`,
    ndwi: (0.42 + seed * 0.03).toFixed(2),
    turbidity: (8 + seed * 1.2).toFixed(1),
    irregularity: (0.18 + seed * 0.02).toFixed(2),
  };
}

function LakeMapMarkers({ lakes, selectedLake, onSelect }) {
  return (
    <>
      {lakes.map((lake) => {
        const isSelected = selectedLake?.id === lake.id;
        const fillColor = RISK_FILL[lake.risk_class] || RISK_FILL.low;

        return (
          <Fragment key={lake.id}>
            {isSelected && (
              <CircleMarker
                center={[lake.lat, lake.lon]}
                radius={18}
                pathOptions={{
                  color: fillColor,
                  fillColor,
                  fillOpacity: 0.25,
                  weight: 1,
                  opacity: 0.4,
                }}
                className="lake-pulse-ring"
                interactive={false}
              />
            )}
            <CircleMarker
              center={[lake.lat, lake.lon]}
              radius={isSelected ? 14 : 10}
              pathOptions={{
                color: '#ffffff',
                fillColor,
                weight: 2,
                fillOpacity: 0.85,
              }}
              eventHandlers={{
                click: () => onSelect(lake),
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{lake.name}</strong>
                <br />
                <span style={{ fontSize: '11px' }}>{lake.district}</span>
              </Tooltip>
            </CircleMarker>
          </Fragment>
        );
      })}
    </>
  );
}

function AreaSparkline() {
  return (
    <svg
      className="sparkline-card__chart"
      viewBox="0 0 280 64"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#059669" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#059669" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 52 L40 48 L80 44 L120 38 L160 32 L200 26 L240 18 L280 10 L280 64 L0 64 Z"
        fill="url(#spark-fill)"
      />
      <polyline
        points="0,52 40,48 80,44 120,38 160,32 200,26 240,18 280,10"
        fill="none"
        stroke="#059669"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { lakes, loading: lakesLoading, error: lakesError, usingMock } = useLakes();
  const { summary, refetch: refetchSummary } = useAlertsSummary();
  const [selectedLake, setSelectedLake] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');
  const [mapStyle, setMapStyle] = useState('street');
  const [toast, setToast] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  const { observations: selectedObservations } = useLake(
    selectedLake?.id ?? null,
  );

  const filteredLakes = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const allowedRisks = FILTER_TO_RISK[activeFilter];

    return lakes.filter((lake) => {
      const matchesSearch =
        !q ||
        lake.name.toLowerCase().includes(q) ||
        (lake.district || '').toLowerCase().includes(q) ||
        (lake.basin || '').toLowerCase().includes(q);
      const matchesFilter =
        !allowedRisks || allowedRisks.includes(lake.risk_class);
      return matchesSearch && matchesFilter;
    });
  }, [lakes, searchQuery, activeFilter]);

  const latestObs = selectedObservations?.[0];
  const metrics = selectedLake
    ? getLakeMetrics(selectedLake, latestObs)
    : null;

  const alertCount = summary?.total_unresolved ?? 0;
  const alertLabel =
    alertCount === 1 ? '1 Active Alert' : `${alertCount} Active Alerts`;

  const handleRunAnalysis = async () => {
    if (!selectedLake) return;
    setAnalyzing(true);
    try {
      const result = await triggerAnalysis(selectedLake.id);
      if (result.alert_created) {
        setToast({
          message: `Analysis complete — ${result.severity} alert created`,
          type: 'success',
        });
      } else {
        setToast({ message: 'No anomaly detected', type: 'success' });
      }
      refetchSummary();
    } catch {
      setToast({
        message: 'Analysis failed — backend unavailable',
        type: 'error',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const tile = mapStyle === 'satellite' ? TILE_SATELLITE : TILE_STREET;

  return (
    <div className="dashboard">
      {lakesError && !usingMock && (
        <div className="dashboard-error-banner" role="alert">
          Could not reach API: {lakesError.message}
        </div>
      )}

      <header className="dashboard-nav">
        <Link to="/" className="dashboard-nav__brand">
          <MountainIcon size={28} />
          <span className="dashboard-nav__title">GLOF Watch</span>
        </Link>

        <div className="dashboard-nav__status">
          <span className="pulse-dot" aria-hidden="true" />
          <span>Last scan: 2 hours ago</span>
        </div>

        <div className="dashboard-nav__actions">
          <span className="dashboard-nav__alert-badge">{alertLabel}</span>
          <button
            type="button"
            className="dashboard-nav__settings"
            aria-label="Settings"
          >
            <Settings size={20} />
          </button>
        </div>
      </header>

      <div className="dashboard-body">
        <aside className="dashboard-sidebar">
          <div className="dashboard-sidebar__inner">
            <div className="dashboard-search">
              <Search className="dashboard-search__icon" size={16} />
              <input
                type="search"
                className="dashboard-search__input"
                placeholder="Search lakes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search lakes"
              />
            </div>

            <div className="dashboard-filters" role="group" aria-label="Filter lakes">
              {FILTER_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className={`filter-chip${activeFilter === chip ? ' filter-chip--active' : ''}`}
                  onClick={() => setActiveFilter(chip)}
                >
                  {chip}
                </button>
              ))}
            </div>

            {lakesLoading ? (
              <div className="dashboard-sidebar__loading">
                <Spinner centered />
              </div>
            ) : (
              <ul className="lake-list">
                {filteredLakes.map((lake) => (
                  <li key={lake.id}>
                    <button
                      type="button"
                      className={`lake-item${selectedLake?.id === lake.id ? ' lake-item--selected' : ''}`}
                      onClick={() => setSelectedLake(lake)}
                    >
                      <div className="lake-item__main">
                        <p className="lake-item__name">{lake.name}</p>
                        <p className="lake-item__district">{lake.district}</p>
                        <RiskBadge riskClass={lake.risk_class} />
                      </div>
                      <ChevronRight
                        className="lake-item__arrow"
                        size={16}
                        aria-hidden="true"
                      />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="dashboard-map" aria-label="Lake map">
          <div className="dashboard-map__toggle" role="group" aria-label="Map style">
            <button
              type="button"
              className={`map-toggle-btn${mapStyle === 'street' ? ' map-toggle-btn--active' : ''}`}
              onClick={() => setMapStyle('street')}
            >
              Street
            </button>
            <button
              type="button"
              className={`map-toggle-btn${mapStyle === 'satellite' ? ' map-toggle-btn--active' : ''}`}
              onClick={() => setMapStyle('satellite')}
            >
              Satellite
            </button>
          </div>

          <MapContainer
            center={NEPAL_CENTER}
            zoom={DEFAULT_ZOOM}
            className="dashboard-map__container"
            zoomControl
          >
            <TileLayer
              key={mapStyle}
              url={tile.url}
              attribution={tile.attribution}
            />
            <LakeMapMarkers
              lakes={lakes}
              selectedLake={selectedLake}
              onSelect={setSelectedLake}
            />
          </MapContainer>
        </section>

        <aside className="dashboard-detail">
          {!selectedLake ? (
            <div className="dashboard-detail--empty">
              <div className="dashboard-detail__empty-icon">
                <MountainIcon size={48} />
              </div>
              <p className="dashboard-detail__empty-text">
                Select a lake to view details
              </p>
            </div>
          ) : (
            <>
              <h2 className="dashboard-detail__name">{selectedLake.name}</h2>
              <p className="dashboard-detail__coords">
                {selectedLake.lat.toFixed(4)}°N, {selectedLake.lon.toFixed(4)}°E
              </p>
              <div className="dashboard-detail__risk">
                <RiskBadge riskClass={selectedLake.risk_class} large />
              </div>

              <div className="metrics-grid">
                <div className="metric-card">
                  <span className="metric-card__label">Current Area</span>
                  <span className="metric-card__value">{metrics.area}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-card__label">NDWI Index</span>
                  <span className="metric-card__value">{metrics.ndwi}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-card__label">Turbidity</span>
                  <span className="metric-card__value">
                    {metrics.turbidity} NTU
                  </span>
                </div>
                <div className="metric-card">
                  <span className="metric-card__label">Irregularity</span>
                  <span className="metric-card__value">
                    {metrics.irregularity}
                  </span>
                </div>
              </div>

              <div className="sparkline-card">
                <p className="sparkline-card__label">Area trend — 24 months</p>
                <AreaSparkline />
              </div>

              <div className="dashboard-detail__actions">
                <button
                  type="button"
                  className="dashboard-btn dashboard-btn--primary"
                  onClick={handleRunAnalysis}
                  disabled={analyzing}
                >
                  {analyzing ? 'Running…' : 'Run Analysis Now'}
                </button>
                <button
                  type="button"
                  className="dashboard-btn dashboard-btn--ghost"
                  onClick={() => navigate(`/lake/${selectedLake.id}`)}
                >
                  View Full Report →
                </button>
              </div>
            </>
          )}
        </aside>
      </div>

      <div className="alert-ticker" aria-live="polite">
        <div className="alert-ticker__track">
          <span className="alert-ticker__content">{TICKER_TEXT}</span>
          <span className="alert-ticker__content" aria-hidden="true">
            {TICKER_TEXT}
          </span>
        </div>
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  );
}
