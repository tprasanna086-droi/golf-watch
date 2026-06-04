import { Link } from 'react-router-dom';
import { Bell, Brain, Satellite } from 'lucide-react';
import './LandingPage.css';

function MountainIcon() {
  return (
    <svg
      width="40"
      height="40"
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

const STATS = [
  { value: '3,624', label: 'Lakes' },
  { value: '10m', label: 'Resolution' },
  { value: '5 Days', label: 'Frequency' },
  { value: '100%', label: 'Open' },
];

const FEATURES = [
  {
    title: 'AI-Powered Detection',
    text: 'Deep learning U-Net models segment glacial lakes from multispectral imagery with sub-pixel accuracy across the Himalaya.',
    icon: Brain,
    tone: 'green',
  },
  {
    title: 'Sentinel-2 Data',
    text: 'Free, open Copernicus satellite imagery refreshes every five days — no proprietary licenses required.',
    icon: Satellite,
    tone: 'amber',
  },
  {
    title: 'Instant Alerts',
    text: 'Automated SMS dispatch reaches district authorities within minutes when anomaly thresholds are breached.',
    icon: Bell,
    tone: 'green',
  },
];

const STEPS = [
  {
    num: '01',
    title: 'Satellite Acquisition',
    text: 'Sentinel-2 scans Nepal every 5 days at 10 m resolution, capturing multispectral bands across all monitored basins.',
  },
  {
    num: '02',
    title: 'AI Processing',
    text: 'U-Net models extract lake boundaries from green, NIR, SWIR, NDWI, and turbidity channels with tiled inference.',
  },
  {
    num: '03',
    title: 'Anomaly Detection',
    text: 'Statistical models flag unusual expansion, turbidity spikes, and shape anomalies against 24-month baselines.',
  },
  {
    num: '04',
    title: 'Alert Dispatch',
    text: 'SMS alerts reach authorities within minutes via Twilio when severity exceeds configured thresholds.',
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <section className="hero" aria-label="Introduction">
        <div className="hero__left">
          <div className="hero__brand">
            <MountainIcon />
            <span className="hero__label">GLOF Watch System</span>
          </div>

          <h1 className="hero__headline">
            <span className="hero__headline-line hero__headline-line--primary">
              Early Warning
            </span>
            <span className="hero__headline-line hero__headline-line--accent">
              for Every Lake
            </span>
            <span className="hero__headline-line hero__headline-line--faint">
              in Nepal
            </span>
          </h1>

          <p className="hero__subtext">
            Real-time AI monitoring of 3,624 glacial lakes using free satellite
            imagery. Protecting communities from catastrophic floods.
          </p>

          <div className="hero__actions">
            <Link to="/dashboard" className="btn btn--primary">
              View Dashboard →
            </Link>
            <a href="#how-it-works" className="btn btn--ghost">
              Learn More
            </a>
          </div>
        </div>

        <div className="hero__right">
          <div className="hero__photo" role="img" aria-label="Himalayan mountains" />
          <div className="hero__gradient" />
          <div className="hero__stats">
            {STATS.map((stat) => (
              <div key={stat.label} className="stat-card">
                <div className="stat-card__value">{stat.value}</div>
                <div className="stat-card__label">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="how" id="how-it-works" aria-labelledby="how-title">
        <h2 className="how__title" id="how-title">
          How It Works
        </h2>

        <div className="how__grid">
          {FEATURES.map(({ title, text, icon: Icon, tone }) => (
            <article key={title} className="feature-card">
              <div
                className={`feature-card__icon feature-card__icon--${tone}`}
              >
                <Icon size={28} strokeWidth={1.75} aria-hidden="true" />
              </div>
              <h3 className="feature-card__title">{title}</h3>
              <p className="feature-card__text">{text}</p>
            </article>
          ))}
        </div>

        <blockquote className="how__quote">
          <p className="how__quote-text">
            A tool built to save lives. Free, open-source, and powered by
            satellite data accessible to everyone.
          </p>
        </blockquote>
      </section>

      <section className="process" aria-labelledby="process-title">
        <h2 className="process__title" id="process-title">
          The Process
        </h2>

        <div className="process__steps">
          {STEPS.map((step) => (
            <article key={step.num} className="process-step">
              <div className="process-step__badge">{step.num}</div>
              <div>
                <h3 className="process-step__title">{step.title}</h3>
                <p className="process-step__text">{step.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="cta" aria-labelledby="cta-title">
        <h2 className="cta__title" id="cta-title">
          Start Monitoring
        </h2>
        <p className="cta__subtext">
          Open the live dashboard to explore lake risk scores, observation
          history, and active alerts across Nepal.
        </p>
        <div className="cta__actions">
          <Link to="/dashboard" className="btn btn--white">
            Open Dashboard
          </Link>
          <a
            href="https://github.com"
            className="btn btn--ghost-light"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub →
          </a>
        </div>
      </section>

      <footer className="landing-footer">
        <span>Built with Sentinel-2, Google Earth Engine &amp; ICIMOD</span>
        <span>© 2026 GLOF Watch System · Open Source</span>
      </footer>
    </div>
  );
}
