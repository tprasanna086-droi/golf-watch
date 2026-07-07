# Contributing to glof-watch

Thank you for your interest in contributing to the GLOF early warning system for Nepal.

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 20.19+ |
| PostgreSQL | 14+ with PostGIS extension |
| Redis | 6+ |

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/tprasanna086-droi/golf-watch.git
cd golf-watch
```

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Open .env and fill in your values:
#   DATABASE_URL, REDIS_URL, TWILIO_ACCOUNT_SID, etc.

# Initialize the database schema
python db/init_db.py

# Seed the lakes table with sample data
python db/seed_lakes.py
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

## Running locally

**API server:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Celery worker** (requires Redis running):
```bash
cd backend
celery -A tasks.celery_app worker --loglevel=info
```

**Frontend dev server:**
```bash
cd frontend
npm run dev
```

## Branch and commit conventions

### Branch naming

| Prefix | Use |
|--------|-----|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `chore/` | Tooling, deps, CI |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring |

### Commit format

```
type: short description
```

Examples:
```
feat: add lake detail page with time-series chart
fix: handle missing NDWI values in observation insert
chore: update rasterio to 1.4.x
docs: add API endpoint reference to README
```

## What NOT to commit

> **Never** commit these files — they are excluded by `.gitignore`, but double-check before pushing.

1. **`.env`** — contains secrets (database credentials, Twilio keys, GEE service account)
2. **Model weights** (`*.pth`, `*.pt`, `*.onnx`) — too large for git; use cloud storage or DVC
3. **Satellite imagery** (`*.tif`, `*.jp2`) — store on cloud or local data directories outside the repo
