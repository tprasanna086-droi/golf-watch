-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Table: lakes
-- Stores the master list of monitored glacial lakes (seeded from ICIMOD inventory)
CREATE TABLE IF NOT EXISTS lakes (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    district        TEXT,
    basin           TEXT,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    geom            GEOMETRY(Point, 4326),
    initial_area_ha DOUBLE PRECISION,
    risk_class      TEXT CHECK (risk_class IN ('low', 'moderate', 'high', 'critical')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Table: lake_observations
-- One row per lake per satellite pass — stores the mask and computed metrics
CREATE TABLE IF NOT EXISTS lake_observations (
    id              SERIAL PRIMARY KEY,
    lake_id         INTEGER REFERENCES lakes(id) ON DELETE CASCADE,
    observed_at     DATE NOT NULL,
    area_ha         DOUBLE PRECISION,
    ndwi_mean       DOUBLE PRECISION,
    turbidity_index DOUBLE PRECISION,
    mask_geom       GEOMETRY(MultiPolygon, 4326),
    cloud_cover_pct DOUBLE PRECISION,
    source_tile     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Table: alerts
-- One row per triggered anomaly alert
CREATE TABLE IF NOT EXISTS alerts (
    id              SERIAL PRIMARY KEY,
    lake_id         INTEGER REFERENCES lakes(id) ON DELETE CASCADE,
    triggered_at    TIMESTAMPTZ DEFAULT NOW(),
    anomaly_score   DOUBLE PRECISION,
    area_delta_pct  DOUBLE PRECISION,
    alert_level     TEXT CHECK (alert_level IN ('watch', 'warning', 'emergency')),
    sms_sent        BOOLEAN DEFAULT FALSE,
    message         TEXT
);

-- Indexes for fast geo and time queries
CREATE INDEX IF NOT EXISTS idx_lakes_geom ON lakes USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_observations_lake_date ON lake_observations(lake_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_lake ON alerts(lake_id, triggered_at DESC);

-- Table: alert_recipients
-- Phone numbers of authorities and field officers to notify when alert is triggered
CREATE TABLE IF NOT EXISTS alert_recipients (
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    phone        TEXT NOT NULL UNIQUE,
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

