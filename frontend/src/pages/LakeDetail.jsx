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
import { getLakeById } from '../data/mockLakes';
import './LakeDetail.css';

const TABS = ['OVERVIEW', 'OBSERVATIONS', 'ALERTS', 'RAW DATA'];

const CHART_DATA = [
  { month: 'Jun 24', area: 1.18, ndwi: 0.61, turbidity: 9.2 },
  { month: 'Aug 24', area: 1.19, ndwi: 0.62, turbidity: 9.8 },
  { month: 'Oct 24', area: 1.2, ndwi: 0.63, turbidity: 10.1 },
  { month: 'Dec 24', area: 1.21, ndwi: 0.64, turbidity: 10.3 },
  { month: 'Feb 25', area: 1.22, ndwi: 0.64, turbidity: 10.8 },
  { month: 'Apr 25', area: 1.24, ndwi: 0.65, turbidity: 11.2 },
  { month: 'Jun 25', area: 1.26, ndwi: 0.65, turbidity: 11.5 },
  { month: 'Aug 25', area: 1.28, ndwi: 0.66, turbidity: 11.9 },
  { month: 'Oct 25', area: 1.3, ndwi: 0.67, turbidity: 12.1 },
  { month: 'Dec 25', area: 1.31, ndwi: 0.67, turbidity: 12.2 },
  { month: 'Feb 26', area: 1.33, ndwi: 0.68, turbidity: 12.3 },
  { month: 'Apr 26', area: 1.34, ndwi: 0.68, turbidity: 12.4 },
  { month: 'Jun 26', area: 1.35, ndwi: 0.68, turbidity: 12.4 },
];

const MOCK_OBSERVATIONS = [
  {
    date: '2026-06-01',
    area: 1.35,
    ndwi: 0.68,
    turbidity: 12.4,
    cloud: 8,
    tile: 'S2B_MSIL2A_20260601_T43RFT',
  },
  {
    date: '2026-04-15',
    area: 1.34,
    ndwi: 0.68,
    turbidity: 12.4,
    cloud: 12,
    tile: 'S2B_MSIL2A_20260415_T43RFT',
  },
  {
    date: '2026-02-10',
    area: 1.33,
    ndwi: 0.68,
    turbidity: 12.3,
    cloud: 5,
    tile: 'S2A_MSIL2A_20260210_T43RFT',
  },
  {
    date: '2025-12-20',
    area: 1.31,
    ndwi: 0.67,
    turbidity: 12.2,
    cloud: 18,
    tile: 'S2B_MSIL2A_20251220_T43RFT',
  },
  {
    date: '2025-10-05',
    area: 1.3,
    ndwi: 0.67,
    turbidity: 12.1,
    cloud: 6,
    tile: 'S2A_MSIL2A_20251005_T43RFT',
  },
  {
    date: '2025-08-18',
    area: 1.28,
    ndwi: 0.66,
    turbidity: 11.9,
    cloud: 22,
    tile: 'S2B_MSIL2A_20250818_T43RFT',
  },
  {
    date: '2025-06-02',
    area: 1.26,
    ndwi: 0.65,
    turbidity: 11.5,
    cloud: 9,
    tile: 'S2A_MSIL2A_20250602_T43RFT',
  },
  {
    date: '2025-04-12',
    area: 1.24,
    ndwi: 0.65,
    turbidity: 11.2,
    cloud: 14,
    tile: 'S2B_MSIL2A_20250412_T43RFT',
  },
];

const MOCK_ALERTS = [
  {
    id: 1,
    severity: 'emergency',
    alert_type: 'rapid_growth',
    triggered_at: '2026-05-12',
    message:
      'Lake area expanded 14% in 60 days — Z-score 4.8 vs 24-month baseline. SMS dispatched to district authorities.',
  },
  {
    id: 2,
    severity: 'warning',
    alert_type: 'turbidity_spike',
    triggered_at: '2026-03-28',
    message:
      'Turbidity index exceeded 2σ above seasonal mean. Recommend field verification within 72 hours.',
  },
  {
    id: 3,
    severity: 'watch',
    alert_type: 'shape_anomaly',
    triggered_at: '2026-01-15',
    message:
      'Perimeter irregularity increased to 0.32. Monitoring frequency elevated to 5-day cycle.',
  },
];

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

function OverviewTab({ lake }) {
  const stats = useMemo(
    () => [
      { label: 'Current Area', value: `${lake.area_km2.toFixed(2)} km²` },
      { label: 'NDWI Index', value: '0.68' },
      { label: 'Turbidity', value: '12.4 NTU' },
      { label: 'Irregularity', value: '0.32' },
      { label: 'Basin', value: lake.basin },
      { label: 'District', value: lake.district },
      { label: 'Growth (24mo)', value: '12.7%' },
      { label: 'Observations', value: '25' },
    ],
    [lake],
  );

  return (
    <>
      <section>
        <h2 className="lake-detail__section-title">Area Growth Trend (24 Months)</h2>
        <div className="lake-detail__card">
          <div className="lake-detail__chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={CHART_DATA} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
                <CartesianGrid stroke="#e7e5e4" strokeDasharray="3 3" />
                <XAxis
                  dataKey="month"
                  tick={{ fill: '#78716c', fontSize: 12, fontFamily: 'Space Grotesk' }}
                  axisLine={{ stroke: '#e7e5e4' }}
                  tickLine={{ stroke: '#e7e5e4' }}
                />
                <YAxis
                  yAxisId="left"
                  domain={[0, 1.4]}
                  tick={{ fill: '#78716c', fontSize: 12, fontFamily: 'Consolas' }}
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
                  tick={{ fill: '#78716c', fontSize: 12, fontFamily: 'Consolas' }}
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
                    <span style={{ fontFamily: 'Space Grotesk', fontSize: 13, color: '#292524' }}>
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
        </div>
      </section>

      <section>
        <h2 className="lake-detail__section-title lake-detail__section-title--spaced">
          Key Statistics
        </h2>
        <div className="stats-grid">
          {stats.map((stat) => (
            <div key={stat.label} className="stat-block">
              <span className="stat-block__label">{stat.label}</span>
              <span className="stat-block__value">{stat.value}</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function ObservationsTab() {
  return (
    <section>
      <div className="observations-header">
        <h2 className="lake-detail__section-title">Satellite Observations</h2>
        <button type="button" className="lake-detail__btn-ghost">
          <Download size={16} aria-hidden="true" />
          Download CSV
        </button>
      </div>
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
            {MOCK_OBSERVATIONS.map((row, index) => (
              <tr
                key={row.date}
                className={index % 2 === 1 ? 'data-table__row--alt' : undefined}
              >
                <td className="mono">{row.date}</td>
                <td className="mono">{row.area.toFixed(2)}</td>
                <td className="mono">{row.ndwi.toFixed(2)}</td>
                <td className="mono">{row.turbidity.toFixed(1)}</td>
                <td className="mono">{row.cloud}%</td>
                <td className="mono">{row.tile}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AlertsTab() {
  return (
    <section>
      <h2 className="lake-detail__section-title">Alert History</h2>
      <div className="alert-list">
        {MOCK_ALERTS.map((alert) => (
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
                  {alert.alert_type.replace(/_/g, ' ')}
                </span>
                <span className="alert-card__date">{alert.triggered_at}</span>
              </div>
              <p className="alert-card__message">{alert.message}</p>
            </div>
            <div className="alert-card__actions">
              <button type="button" className="lake-detail__btn-ghost">
                Mark Resolved
              </button>
            </div>
          </article>
        ))}
      </div>
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

  const lake = getLakeById(id);
  const riskClass = (lake?.risk_class || 'low').toLowerCase();

  if (!lake) {
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
        {activeTab === 'OVERVIEW' && <OverviewTab lake={lake} />}
        {activeTab === 'OBSERVATIONS' && <ObservationsTab />}
        {activeTab === 'ALERTS' && <AlertsTab />}
        {activeTab === 'RAW DATA' && <RawDataTab />}
      </div>
    </div>
  );
}
