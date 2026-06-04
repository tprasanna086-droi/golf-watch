-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Master list of monitored glacial lakes
CREATE TABLE IF NOT EXISTS lakes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    district          TEXT,
    basin             TEXT,
    latitude          DOUBLE PRECISION NOT NULL,
    longitude         DOUBLE PRECISION NOT NULL,
    geom              GEOMETRY(Point, 4326),
    initial_area_km2  DOUBLE PRECISION,
    risk_class        TEXT CHECK (risk_class IN ('low', 'medium', 'high', 'critical')),
    source            TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- One row per lake per satellite observation pass
CREATE TABLE IF NOT EXISTS lake_observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id             UUID NOT NULL REFERENCES lakes(id) ON DELETE CASCADE,
    observed_at         DATE NOT NULL,
    area_km2            DOUBLE PRECISION,
    ndwi_mean           DOUBLE PRECISION,
    turbidity_index     DOUBLE PRECISION,
    shape_irregularity  DOUBLE PRECISION,
    mask_geom           GEOMETRY(MultiPolygon, 4326),
    cloud_cover_pct     DOUBLE PRECISION,
    sentinel_tile_id    TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Triggered anomaly alerts
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id         UUID NOT NULL REFERENCES lakes(id) ON DELETE CASCADE,
    triggered_at    TIMESTAMPTZ DEFAULT now(),
    alert_type      TEXT CHECK (alert_type IN ('rapid_growth', 'turbidity_spike', 'shape_anomaly')),
    severity        TEXT CHECK (severity IN ('watch', 'warning', 'emergency')),
    area_delta_km2  DOUBLE PRECISION,
    anomaly_score   DOUBLE PRECISION,
    message         TEXT,
    sms_sent        BOOLEAN DEFAULT false,
    resolved_at     TIMESTAMPTZ
);

-- Spatial indexes
CREATE INDEX IF NOT EXISTS idx_lakes_geom ON lakes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_lake_observations_mask_geom ON lake_observations USING GIST (mask_geom);

-- Time-series lookups per lake
CREATE INDEX IF NOT EXISTS idx_lake_observations_lake_observed_at ON lake_observations (lake_id, observed_at DESC);
