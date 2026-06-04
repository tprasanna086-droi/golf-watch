"""FastAPI routes for glacial lake resources."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Alert, Lake, LakeObservation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lakes", tags=["lakes"])


class LakeResponse(BaseModel):
    """Public lake fields returned by list and detail endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    district: Optional[str] = None
    basin: Optional[str] = None
    latitude: float
    longitude: float
    initial_area_km2: Optional[float] = None
    risk_class: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime


class LakeObservationResponse(BaseModel):
    """Observation fields returned by the observations endpoint (no geometry)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lake_id: uuid.UUID
    observed_at: date
    area_km2: Optional[float] = None
    ndwi_mean: Optional[float] = None
    turbidity_index: Optional[float] = None
    shape_irregularity: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    sentinel_tile_id: Optional[str] = None
    created_at: datetime


class AlertResponse(BaseModel):
    """Alert fields returned by the alerts endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lake_id: uuid.UUID
    triggered_at: datetime
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    area_delta_km2: Optional[float] = None
    anomaly_score: Optional[float] = None
    message: Optional[str] = None
    sms_sent: bool
    resolved_at: Optional[datetime] = None


async def _get_lake_or_404(db: AsyncSession, lake_id: uuid.UUID) -> Lake:
    """Load a lake by primary key or raise HTTP 404."""
    lake = await db.get(Lake, lake_id)
    if lake is None:
        raise HTTPException(
            status_code=404,
            detail=f"Lake with id {lake_id} not found",
        )
    return lake


@router.get("", response_model=list[LakeResponse])
async def list_lakes(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[LakeResponse]:
    """Return a paginated list of all lakes ordered by name."""
    try:
        stmt = (
            select(Lake)
            .order_by(Lake.name.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        lakes = result.scalars().all()
        return [LakeResponse.model_validate(lake) for lake in lakes]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list lakes")
        raise


@router.get("/{lake_id}", response_model=LakeResponse)
async def get_lake(
    lake_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LakeResponse:
    """Return a single lake by UUID."""
    try:
        lake = await _get_lake_or_404(db, lake_id)
        return LakeResponse.model_validate(lake)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get lake %s", lake_id)
        raise


@router.get("/{lake_id}/observations", response_model=list[LakeObservationResponse])
async def list_lake_observations(
    lake_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> list[LakeObservationResponse]:
    """Return observations for a lake ordered by observed_at descending."""
    try:
        await _get_lake_or_404(db, lake_id)
        stmt = (
            select(LakeObservation)
            .where(LakeObservation.lake_id == lake_id)
            .order_by(LakeObservation.observed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        observations = result.scalars().all()
        return [
            LakeObservationResponse.model_validate(obs) for obs in observations
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list observations for lake %s", lake_id)
        raise


@router.get("/{lake_id}/alerts", response_model=list[AlertResponse])
async def list_lake_alerts(
    lake_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AlertResponse]:
    """Return all alerts for a lake ordered by triggered_at descending."""
    try:
        await _get_lake_or_404(db, lake_id)
        stmt = (
            select(Alert)
            .where(Alert.lake_id == lake_id)
            .order_by(Alert.triggered_at.desc())
        )
        result = await db.execute(stmt)
        alerts = result.scalars().all()
        return [AlertResponse.model_validate(alert) for alert in alerts]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list alerts for lake %s", lake_id)
        raise
