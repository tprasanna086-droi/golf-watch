import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else
load_dotenv(Path(__file__).resolve().parent / ".env")

from routers import lakes, alerts, observations  # noqa: E402

app = FastAPI(
    title="Glacial Risk Nepal API",
    description="GLOF early warning system for Nepal",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(lakes.router)
app.include_router(alerts.router)
app.include_router(observations.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "project": "glacial-risk-nepal"}
