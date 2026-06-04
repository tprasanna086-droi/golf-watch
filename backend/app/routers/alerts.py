"""FastAPI routes for alerts and on-demand lake anomaly analysis."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import _async_database_url, get_db
from app.db.models import Alert, Lake
from app.ml.anomaly import MIN_ZSCORE_HISTORY, fetch_and_analyze

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])

VALID_SEVERITIES = frozenset({"watch", "warning", "emergency"})


class AlertWithLakeResponse(BaseModel):
    """Alert fields including the related lake name."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lake_id: uuid.UUID
    lake_name: str
    triggered_at: datetime
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    area_delta_km2: Optional[float] = None
    anomaly_score: Optional[float] = None
    message: Optional[str] = None
    sms_sent: bool
    resolved_at: Optional[datetime] = None


class AlertsSummaryResponse(BaseModel):
    """Aggregated alert counts for dashboards."""

    total_unresolved: int
    by_severity: dict[str, int] = Field(
        default_factory=lambda: {"watch": 0, "warning": 0, "emergency": 0},
    )
    by_type: dict[str, int] = Field(
        default_factory=lambda: {
            "rapid_growth": 0,
            "turbidity_spike": 0,
            "shape_anomaly": 0,
        },
    )


class LakeAnalyzeResponse(BaseModel):
    """Result of an on-demand anomaly analysis for one lake."""

    lake_id: str
    latest_area_km2: float
    mean_area_km2: float
    std_area_km2: float
    z_score: float
    isolation_score: float
    is_anomaly: bool
    severity: str
    contributing_factors: list[str]
    alert_created: bool


def _sync_database_url() -> str:
    """Return a psycopg2-compatible database URL."""
    return _async_database_url().replace("postgresql+asyncpg://", "postgresql://")


def _alert_with_lake_response(alert: Alert, lake_name: str) -> AlertWithLakeResponse:
    """Build a response model from an Alert ORM row and lake name."""
    return AlertWithLakeResponse(
        id=alert.id,
        lake_id=alert.lake_id,
        lake_name=lake_name,
        triggered_at=alert.triggered_at,
        alert_type=alert.alert_type,
        severity=alert.severity,
        area_delta_km2=alert.area_delta_km2,
        anomaly_score=alert.anomaly_score,
        message=alert.message,
        sms_sent=alert.sms_sent,
        resolved_at=alert.resolved_at,
    )


async def _get_alert_with_lake_or_404(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> tuple[Alert, str]:
    """Load an alert and its lake name or raise HTTP 404."""
    stmt = (
        select(Alert, Lake.name)
        .join(Lake, Alert.lake_id == Lake.id)
        .where(Alert.id == alert_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alert with id {alert_id} not found",
        )
    alert, lake_name = row
    return alert, lake_name


def _infer_alert_type(contributing_factors: list[str]) -> str:
    """Map contributing factor text to a schema alert_type value."""
    combined = " ".join(contributing_factors).lower()
    if "turbidity" in combined:
        return "turbidity_spike"
    if "ndwi" in combined or "shape" in combined:
        return "shape_anomaly"
    return "rapid_growth"


@router.get("/alerts/summary", response_model=AlertsSummaryResponse)
async def alerts_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertsSummaryResponse:
    """Return aggregated alert counts by severity and type."""
    try:
        unresolved_stmt = (
            select(func.count())
            .select_from(Alert)
            .where(Alert.resolved_at.is_(None))
        )
        unresolved_result = await db.execute(unresolved_stmt)
        total_unresolved = int(unresolved_result.scalar_one())

        severity_stmt = (
            select(Alert.severity, func.count())
            .group_by(Alert.severity)
        )
        severity_rows = (await db.execute(severity_stmt)).all()

        type_stmt = select(Alert.alert_type, func.count()).group_by(Alert.alert_type)
        type_rows = (await db.execute(type_stmt)).all()

        by_severity = {"watch": 0, "warning": 0, "emergency": 0}
        for severity, count in severity_rows:
            if severity in by_severity:
                by_severity[severity] = int(count)

        by_type = {
            "rapid_growth": 0,
            "turbidity_spike": 0,
            "shape_anomaly": 0,
        }
        for alert_type, count in type_rows:
            if alert_type in by_type:
                by_type[alert_type] = int(count)

        return AlertsSummaryResponse(
            total_unresolved=total_unresolved,
            by_severity=by_severity,
            by_type=by_type,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to build alerts summary")
        raise


@router.get("/alerts", response_model=list[AlertWithLakeResponse])
async def list_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    severity: Annotated[Optional[str], Query()] = None,
    resolved: Annotated[Optional[bool], Query()] = None,
) -> list[AlertWithLakeResponse]:
    """Return a paginated list of alerts across all lakes."""
    try:
        if severity is not None and severity not in VALID_SEVERITIES:
            raise HTTPException(
                status_code=422,
                detail=f"severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}",
            )

        stmt = (
            select(Alert, Lake.name)
            .join(Lake, Alert.lake_id == Lake.id)
            .order_by(Alert.triggered_at.desc())
            .offset(skip)
            .limit(limit)
        )

        if severity is not None:
            stmt = stmt.where(Alert.severity == severity)
        if resolved is True:
            stmt = stmt.where(Alert.resolved_at.isnot(None))
        elif resolved is False:
            stmt = stmt.where(Alert.resolved_at.is_(None))

        result = await db.execute(stmt)
        rows = result.all()
        return [_alert_with_lake_response(alert, lake_name) for alert, lake_name in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list alerts")
        raise


@router.get("/alerts/{alert_id}", response_model=AlertWithLakeResponse)
async def get_alert(
    alert_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertWithLakeResponse:
    """Return a single alert by UUID."""
    try:
        alert, lake_name = await _get_alert_with_lake_or_404(db, alert_id)
        return _alert_with_lake_response(alert, lake_name)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get alert %s", alert_id)
        raise


@router.post("/alerts/{alert_id}/resolve", response_model=AlertWithLakeResponse)
async def resolve_alert(
    alert_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlertWithLakeResponse:
    """Mark an alert as resolved."""
    try:
        alert, lake_name = await _get_alert_with_lake_or_404(db, alert_id)
        if alert.resolved_at is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Alert {alert_id} is already resolved",
            )

        alert.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)

        logger.info("Resolved alert %s for lake %s", alert_id, alert.lake_id)
        return _alert_with_lake_response(alert, lake_name)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to resolve alert %s", alert_id)
        raise


@router.post("/lakes/{lake_id}/analyze", response_model=LakeAnalyzeResponse)
async def analyze_lake(
    lake_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LakeAnalyzeResponse:
    """Run an immediate anomaly analysis and optionally create an alert."""
    try:
        lake = await db.get(Lake, lake_id)
        if lake is None:
            raise HTTPException(
                status_code=404,
                detail=f"Lake with id {lake_id} not found",
            )

        analysis = await asyncio.to_thread(
            fetch_and_analyze,
            str(lake_id),
            _sync_database_url(),
        )
        if analysis is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Fewer than {MIN_ZSCORE_HISTORY} observations available "
                    f"for lake {lake_id}"
                ),
            )

        alert_created = False
        if analysis.is_anomaly:
            area_delta_km2 = analysis.latest_area_km2 - analysis.mean_area_km2
            message = (
                "; ".join(analysis.contributing_factors)
                if analysis.contributing_factors
                else (
                    f"Anomaly detected for lake {lake_id}: "
                    f"z_score={analysis.z_score:.2f}, "
                    f"isolation={analysis.isolation_score:.3f}"
                )
            )
            alert = Alert(
                lake_id=lake_id,
                alert_type=_infer_alert_type(analysis.contributing_factors),
                severity=analysis.severity,
                area_delta_km2=area_delta_km2,
                anomaly_score=analysis.z_score,
                message=message,
            )
            db.add(alert)
            await db.commit()
            alert_created = True
            logger.info(
                "Created %s alert for lake %s from manual analysis",
                analysis.severity,
                lake_id,
            )

        return LakeAnalyzeResponse(
            lake_id=analysis.lake_id,
            latest_area_km2=analysis.latest_area_km2,
            mean_area_km2=analysis.mean_area_km2,
            std_area_km2=analysis.std_area_km2,
            z_score=analysis.z_score,
            isolation_score=analysis.isolation_score,
            is_anomaly=analysis.is_anomaly,
            severity=analysis.severity,
            contributing_factors=analysis.contributing_factors,
            alert_created=alert_created,
        )
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to analyze lake %s", lake_id)
        raise
