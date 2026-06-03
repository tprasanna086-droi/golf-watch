# CLAUDE.md — glof-watch project conventions

## Project overview
glof-watch is a Glacial Lake Outburst Flood (GLOF) early warning system for Nepal.
It ingests Sentinel-2 satellite imagery, runs U-Net segmentation + anomaly detection,
and surfaces risk alerts on a live Leaflet map with SMS dispatch via Twilio.

## Monorepo structure
- backend/      FastAPI app, ML pipeline, Celery tasks, PostGIS DB
- frontend/     React + Vite app, Leaflet map, Recharts time-series

## Backend conventions
- Python 3.11+
- All routes live in backend/routers/ — one file per resource
- All ML code lives in backend/ml/ — one file per concern
- All Celery tasks live in backend/tasks/
- DB access: raw psycopg2 only, no ORM. Use get_db() from backend/db/connection.py
- Environment variables loaded via python-dotenv from backend/.env
- Never hardcode credentials or paths
- All functions must have docstrings
- Error handling: always wrap DB and ML calls in try/except, log errors, re-raise

## Frontend conventions
- React 18 + Vite
- Component files in frontend/src/components/ — one component per file
- All API calls via axios in frontend/src/api/client.js (to be created)
- Map logic isolated in frontend/src/components/MapView.jsx
- No inline styles — use CSS modules or App.css
- Colors: use CSS variables defined in index.css

## ML pipeline conventions
- U-Net input: 5-channel float32 tensor (green, nir, swir, ndwi, turbidity)
- Tile size: 256x256 with 32px overlap
- Anomaly scorer: IsolationForest, contamination=0.05
- Alert thresholds: watch >0.4, warning >0.6, emergency >0.8

## Git conventions
- Branch naming: feat/*, fix/*, chore/*
- Commit format: "type: short description" (feat, fix, chore, docs, refactor)
- Never commit .env, __pycache__, node_modules, dist

## Key environment variables
DATABASE_URL, REDIS_URL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
GEE_SERVICE_ACCOUNT, GEE_KEY_FILE

## Running locally
Backend:  cd backend && uvicorn main:app --reload --port 8000
Worker:   cd backend && celery -A tasks.celery_app worker --loglevel=info
Frontend: cd frontend && npm run dev
