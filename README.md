# glof-watch

> Glacial Lake Outburst Flood early warning system for Nepal

## What it does

glof-watch is a real-time monitoring and anomaly detection system designed to mitigate Glacial Lake Outburst Flood (GLOF) risks in Nepal. The application continuously ingests Sentinel-2 satellite imagery over target lakes, segments water boundaries via deep learning, calculates temporal changes, evaluates anomaly risks, and publishes alerts through an interactive GIS mapping dashboard and automated Twilio SMS dispatches to local disaster management teams.

## Architecture

The system operates as an end-to-end data processing and visualization pipeline:
1. **Imagery Ingestion**: Sentinel-2 L2A surface reflectance data is pulled on-demand for specific lake bounds via the Google Earth Engine (GEE) Python API.
2. **Segmentation**: A custom 5-channel U-Net segmentation network (using a ResNet-34 encoder) predicts lake boundaries from Green, NIR, SWIR, NDWI, and Turbidity inputs.
3. **Change Detection & Anomaly Analysis**: Extracted polygons are analyzed for area changes and shape irregularities (Polsby-Popper score). An Isolation Forest model identifies anomalous size/spectral trends.
4. **Data Store & API**: Metrics and geographic geometries are stored in a PostGIS database. A FastAPI server exposes REST endpoints to query lakes, active alerts, and historic observation timeseries.
5. **Dashboard & Notification**: A React/Leaflet frontend visualizes map risk centers and active alert tickers, while Celery tasks automatically dispatch SMS warnings to registered authorities.

## Stack

| Backend | Frontend |
|---|---|
| Python (FastAPI / Uvicorn) | React (Vite / SPA) |
| PostGIS (PostgreSQL) | Leaflet (react-leaflet) |
| Redis (Broker & Backend) | Recharts (History visualization) |
| Celery (Task queue & Beat scheduler) | Axios (API client) |
| PyTorch / SMP (U-Net) | Vanilla CSS (Dashboard theme) |
| scikit-learn (Isolation Forest) | |

## Running locally

### Prerequisites
- Docker and Docker Compose
- A Google Earth Engine service account key
- A Twilio account (for SMS alerts)

### Setup
1. **Clone the repo:**
   ```bash
   git clone https://github.com/tprasanna086-droi/golf-watch.git
   cd golf-watch
   ```

2. **Configure backend variables:**
   ```bash
   cp backend/.env.example backend/.env
   # Fill in values including DATABASE_URL, REDIS_URL, GEE_KEY_FILE, TWILIO_*
   ```

3. **Configure root environment:**
   ```bash
   cp .env.example .env
   # Set POSTGRES_PASSWORD
   ```

4. **Spin up local infrastructure:**
   ```bash
   docker-compose up --build
   ```

5. **Seed the database (first time only):**
   The database schema is auto-applied on first `docker-compose up` (via `docker-entrypoint-initdb.d/01_schema.sql`). No manual init is needed.
   ```bash
   docker-compose exec backend python db/seed_lakes.py
   ```
   If you ever need to re-apply the schema (e.g. after dropping tables), run `docker-compose exec backend python db/init_db.py` — it is idempotent and safe to re-run.

6. **Start the frontend application:**
   ```bash
   cd frontend
   cp .env.example .env
   # Update VITE_API_URL if needed
   npm install
   npm run dev
   ```

## Deployment
- **Frontend**: Vercel (auto-deploys from the `main` branch, configuration defined in `vercel.json`).
- **Backend**: Any Docker-compliant hosting platform (Railway, Render, or a cloud VPS).

## License
MIT
