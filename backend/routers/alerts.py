"""
Routes for GLOF alert data.
"""

from fastapi import APIRouter, Depends, Query
import psycopg2.extras

from db.connection import get_db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

ALERTS_BASE_QUERY = """
    SELECT
        a.id,
        a.lake_id,
        l.name  AS lake_name,
        l.lat,
        l.lon,
        a.triggered_at,
        a.anomaly_score,
        a.area_delta_pct,
        a.alert_level,
        a.message
    FROM alerts a
    JOIN lakes l ON l.id = a.lake_id
"""


@router.get("")
def list_alerts(
    level: str | None = Query(None, description="Filter by alert level: watch, warning, emergency"),
    limit: int = Query(20, ge=1, le=200, description="Max results"),
    conn=Depends(get_db),
):
    """Return recent alerts joined with lake info."""
    query = ALERTS_BASE_QUERY + " WHERE 1=1"
    params: dict = {}

    if level:
        if level not in ("watch", "warning", "emergency"):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=f"Invalid level '{level}'. Must be one of: watch, warning, emergency",
            )
        query += " AND a.alert_level = %(level)s"
        params["level"] = level

    query += " ORDER BY a.triggered_at DESC LIMIT %(limit)s"
    params["limit"] = limit

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        alerts = cur.fetchall()

    return [dict(row) for row in alerts]


@router.get("/active")
def active_alerts(conn=Depends(get_db)):
    """Return alerts from the last 30 days."""
    query = (
        ALERTS_BASE_QUERY
        + " WHERE a.triggered_at >= NOW() - INTERVAL '30 days'"
        + " ORDER BY a.triggered_at DESC"
    )

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query)
        alerts = cur.fetchall()

    return [dict(row) for row in alerts]
