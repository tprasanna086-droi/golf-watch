import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChevronLeft, Download, MapPin, Waves } from 'lucide-react';
import { resolveAlert } from '../api/alerts';
import { triggerAnalysis } from '../api/lakes';
import SkeletonCard from '../components/SkeletonCard';
import Spinner from '../components/Spinner';
import Toast from '../components/Toast';
import { FALLBACK_CHART_DATA } from '../data/mockLakeDetail';
import { useLake } from '../hooks/useLake';
import {
  computeGrowthPercent,
  formatAlertDate,
  formatObservationRow,
  observationsToChartData,
} from '../utils/lakeUtils';
import './LakeDetail.css';

const TABS = ['OVERVIEW', 'OBSERVATIONS', 'ALERTS', 'RAW DATA'];

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const units = {
    area: 'km²',
    ndwi: '',
    turbidity: 'NTU',
  };

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__label">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="chart-tooltip__row">
          {entry.name}: {entry.value}
          {units[entry.dataKey] ? ` ${units[entry.dataKey]}` : ''}
        </p>
      ))}
    </div>
  );
}

function OverviewTab({
  lake,
  observations,
  chartData,
  loading,
  onRunAnalysis,
  analyzing,
}) {
  const latest = observations?.[0];
  const growth = computeGrowthPercent(observations);

  const stats = useMemo(() => {
    if (loading) return [];
    return [
      {
        label: 'Current Area',
        value: `${(latest?.area_km2 ?? lake.area_km2 ?? 0).toFixed(2)} km²`,
      },
      {
        label: 'NDWI Index',
        value: (latest?.ndwi_mean ?? 0).toFixed(2),
      },
      {
        label: 'Turbidity',
        value: `${(latest?.turbidity_index ?? 0).toFixed(1)} NTU`,
      },
      {
        label: 'Irregularity',
        value: (latest?.shape_irregularity ?? 0.32).toFixed(2),
      },
      { label: 'Basin', value: lake.basin },
      { label: 'District', value: lake.district },
      {
        label: 'Growth (24mo)',
        value: growth != null ? `${growth}%` : '—',
      },
      {
        label: 'Observations',
        value: String(observations?.length ?? 0),
      },
    ];
  }, [lake, observations, latest, growth, loading]);

  const areaMax = useMemo(() => {
    const maxArea = Math.max(...chartData.map((d) => d.area), 0);
    return Math.max(maxArea * 1.1, 0.5);
  }, [chartData]);

  return (
    <>
      <section>
        <h2 className="lake-detail__section-title">Area Growth Trend (24 Months)</h2>
        <div className="lake-detail__card">
          {loading ? (
            <div className="lake-detail__chart-loading">
              <Spinner centered />
            </div>
          ) : (
            <div className="lake-detail__chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={chartData}
                  margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
                >
                  <CartesianGrid stroke="#e7e5e4" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="month"
                    tick={{
                      fill: '#78716c',
                      fontSize: 12,
                      fontFamily: 'Space Grotesk',
                    }}
                    axisLine={{ stroke: '#e7e5e4' }}
                    tickLine={{ stroke: '#e7e5e4' }}
                  />
                  <YAxis
                    yAxisId="left"
                    domain={[0, areaMax]}
                    tick={{
                      fill: '#78716c',
                      fontSize: 12,
                      fontFamily: 'Consolas',
                    }}
                    axisLine={{ stroke: '#e7e5e4' }}
                    tickLine={{ stroke: '#e7e5e4' }}
                    label={{
                      value: 'Area (km²)',
                      angle: -90,
                      position: 'insideLeft',
                      fill: '#78716c',
                      fontSize: 12,
                    }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    domain={[0, 16]}
                    tick={{
                      fill: '#78716c',
                      fontSize: 12,
                      fontFamily: 'Consolas',
                    }}
                    axisLine={{ stroke: '#e7e5e4' }}
                    tickLine={{ stroke: '#e7e5e4' }}
                    label={{
                      value: 'NDWI / Turbidity',
                      angle: 90,
                      position: 'insideRight',
                      fill: '#78716c',
                      fontSize: 12,
                    }}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    formatter={(value) => (
                      <span
                        style={{
                          fontFamily: 'Space Grotesk',
                          fontSize: 13,
                          color: '#292524',
                        }}
                      >
                        {value}
                      </span>
                    )}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="area"
                    name="Area (km²)"
                    stroke="#059669"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="ndwi"
                    name="NDWI"
                    stroke="#10b981"
                    strokeWidth={1.5}
                    dot={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="turbidity"
                    name="Turbidity (NTU)"
                    stroke="#78716c"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="lake-detail__section-title lake-detail__section-title--spaced">
          Key Statistics
        </h2>
        <div className="stats-grid">
          {loading
            ? Array.from({ length: 8 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))
            : stats.map((stat) => (
                <div key={stat.label} className="stat-block">
                  <span className="stat-block__label">{stat.label}</span>
                  <span className="stat-block__value">{stat.value}</span>
                </div>
              ))}
        </div>
      </section>

      <div className="lake-detail__actions">
        <button
          type="button"
          className="dashboard-btn dashboard-btn--primary"
          onClick={onRunAnalysis}
          disabled={analyzing}
        >
          {analyzing ? 'Running…' : 'Run Analysis Now'}
        </button>
        <Link to="/dashboard" className="dashboard-btn dashboard-btn--ghost">
          Back to Dashboard →
        </Link>
      </div>
    </>
  );
}

function ObservationsTab({ observations, loading }) {
  const rows = observations.map(formatObservationRow);

  return (
    <section>
      <div className="observations-header">
        <h2 className="lake-detail__section-title">Satellite Observations</h2>
        <button type="button" className="lake-detail__btn-ghost">
          <Download size={16} aria-hidden="true" />
          Download CSV
        </button>
      </div>
      {loading ? (
        <div className="lake-detail__tab-loading">
          <Spinner centered />
        </div>
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Area (km²)</th>
                <th>NDWI</th>
                <th>Turbidity</th>
                <th>Cloud Cover</th>
                <th>Tile ID</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="lake-detail__empty-row">
                    No observations recorded yet.
                  </td>
                </tr>
              ) : (
                rows.map((row, index) => (
                  <tr
                    key={row.id ?? row.date}
                    className={index % 2 === 1 ? 'data-table__row--alt' : undefined}
                  >
                    <td className="mono">{row.date}</td>
                    <td className="mono">{row.area.toFixed(2)}</td>
                    <td className="mono">{row.ndwi.toFixed(2)}</td>
                    <td className="mono">{row.turbidity.toFixed(1)}</td>
                    <td className="mono">{row.cloud}%</td>
                    <td className="mono">{row.tile}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AlertsTab({ alerts, loading, onResolve, resolvingId }) {
  const unresolved = alerts.filter((a) => !a.resolved_at);

  return (
    <section>
      <h2 className="lake-detail__section-title">Alert History</h2>
      {loading ? (
        <div className="lake-detail__tab-loading">
          <Spinner centered />
        </div>
      ) : (
        <div className="alert-list">
          {unresolved.length === 0 ? (
            <p className="lake-detail__empty-alerts">No active alerts for this lake.</p>
          ) : (
            unresolved.map((alert) => (
              <article
                key={alert.id}
                className={`alert-card alert-card--${alert.severity}`}
              >
                <div>
                  <div className="alert-card__header">
                    <span
                      className={`alert-card__severity alert-card__severity--${alert.severity}`}
                    >
                      {alert.severity}
                    </span>
                    <span className="alert-card__type">
                      {(alert.alert_type || 'alert').replace(/_/g, ' ')}
                    </span>
                    <span className="alert-card__date">
                      {formatAlertDate(alert.triggered_at)}
                    </span>
                  </div>
                  <p className="alert-card__message">{alert.message}</p>
                </div>
                <div className="alert-card__actions">
                  <button
                    type="button"
                    className="lake-detail__btn-ghost"
                    disabled={resolvingId === alert.id}
                    onClick={() => onResolve(alert.id)}
                  >
                    {resolvingId === alert.id ? 'Resolving…' : 'Mark Resolved'}
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      )}
    </section>
  );
}

function RawDataTab() {
  const exports = [
    {
      title: 'Lake Mask GeoJSON',
      description:
        'Vector polygon of the current lake boundary extracted from the latest U-Net segmentation pass.',
      label: 'Download .geojson',
    },
    {
      title: 'Observations CSV',
      description:
        'Full time-series of area, NDWI, turbidity, and cloud cover for all satellite passes.',
      label: 'Download .csv',
    },
    {
      title: 'Alert History JSON',
      description:
        'Structured export of all alerts, severity levels, and dispatch metadata for this lake.',
      label: 'Download .json',
    },
  ];

  return (
    <section>
      <h2 className="lake-detail__section-title">Raw Data Export</h2>
      <div className="export-grid">
        {exports.map((item) => (
          <div key={item.title} className="export-card">
            <h3 className="export-card__title">{item.title}</h3>
            <p className="export-card__desc">{item.description}</p>
            <button type="button" className="export-card__btn">
              {item.label}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function LakeDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('OVERVIEW');
  const [toast, setToast] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);

  const { lake, observations, alerts, loading, refetch } = useLake(id);

  const chartData = useMemo(() => {
    const derived = observationsToChartData(observations);
    return derived?.length ? derived : FALLBACK_CHART_DATA;
  }, [observations]);

  const riskClass = (lake?.risk_class || 'low').toLowerCase();

  const handleRunAnalysis = async () => {
    if (!lake) return;
    setAnalyzing(true);
    try {
      const result = await triggerAnalysis(lake.id);
      if (result.alert_created) {
        setToast({
          message: `Analysis complete — ${result.severity} alert created`,
          type: 'success',
        });
      } else {
        setToast({ message: 'No anomaly detected', type: 'success' });
      }
      refetch();
    } catch {
      setToast({
        message: 'Analysis failed — backend unavailable',
        type: 'error',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResolve = async (alertId) => {
    setResolvingId(alertId);
    try {
      await resolveAlert(alertId);
      refetch();
    } catch {
      setToast({
        message: 'Failed to resolve alert — backend unavailable',
        type: 'error',
      });
    } finally {
      setResolvingId(null);
    }
  };

  if (!loading && !lake) {
    return (
      <div className="lake-detail">
        <div className="lake-detail__not-found">
          <h1>Lake not found</h1>
          <p>No lake matches ID {id}.</p>
          <Link to="/dashboard" className="lake-detail__btn-ghost">
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="lake-detail">
      <header className="lake-detail__header">
        <button
          type="button"
          className="lake-detail__back"
          onClick={() => navigate(-1)}
        >
          <ChevronLeft size={18} aria-hidden="true" />
          Back to Dashboard
        </button>

        {loading && !lake ? (
          <Spinner centered />
        ) : (
          <div className="lake-detail__header-row">
            <div>
              <h1 className="lake-detail__title">{lake.name}</h1>
              <div className="lake-detail__meta">
                <span className="lake-detail__meta-item">
                  <Waves size={16} aria-hidden="true" />
                  Basin: {lake.basin}
                </span>
                <span className="lake-detail__meta-sep" aria-hidden="true">
                  ·
                </span>
                <span className="lake-detail__meta-item">
                  <MapPin size={16} aria-hidden="true" />
                  District: {lake.district}
                </span>
                <span className="lake-detail__meta-sep" aria-hidden="true">
                  ·
                </span>
                <span className="lake-detail__coords">
                  {lake.lat.toFixed(4)}°N, {lake.lon.toFixed(4)}°E
                </span>
              </div>
            </div>

            <div
              className={`lake-detail__risk-badge lake-detail__risk-badge--${riskClass}`}
            >
              <span className="lake-detail__risk-dot" aria-hidden="true" />
              <span className="lake-detail__risk-label">{riskClass}</span>
            </div>
          </div>
        )}
      </header>

      <div className="lake-detail__hero">
        <img
          className="lake-detail__hero-img"
          src="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1400"
          alt=""
        />
        <div className="lake-detail__hero-gradient" aria-hidden="true" />
      </div>

      <nav className="lake-detail__tabs" role="tablist" aria-label="Lake detail sections">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            className={`lake-detail__tab${activeTab === tab ? ' lake-detail__tab--active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="lake-detail__content" role="tabpanel">
        {activeTab === 'OVERVIEW' && lake && (
          <OverviewTab
            lake={lake}
            observations={observations}
            chartData={chartData}
            loading={loading}
            onRunAnalysis={handleRunAnalysis}
            analyzing={analyzing}
          />
        )}
        {activeTab === 'OBSERVATIONS' && (
          <ObservationsTab observations={observations} loading={loading} />
        )}
        {activeTab === 'ALERTS' && (
          <AlertsTab
            alerts={alerts}
            loading={loading}
            onResolve={handleResolve}
            resolvingId={resolvingId}
          />
        )}
        {activeTab === 'RAW DATA' && <RawDataTab />}
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
