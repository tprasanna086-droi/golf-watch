"""
Routes for lake observation data.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2.extras

from db.connection import get_db

router = APIRouter(prefix="/api/observations", tags=["observations"])


class ObservationCreate(BaseModel):
    lake_id: int
    observed_at: str  # YYYY-MM-DD
    area_ha: float
    ndwi_mean: float
    turbidity_index: float
    cloud_cover_pct: float | None = None
    source_tile: str | None = None


@router.post("", status_code=201)
def create_observation(body: ObservationCreate, conn=Depends(get_db)):
    """Insert a new lake observation and return the inserted row id."""
    # Validate date format
    try:
        date.fromisoformat(body.observed_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="observed_at must be a valid date in YYYY-MM-DD format")

    # Verify lake exists
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM lakes WHERE id = %s", (body.lake_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Lake with id {body.lake_id} not found")

    insert_sql = """
        INSERT INTO lake_observations
            (lake_id, observed_at, area_ha, ndwi_mean, turbidity_index, cloud_cover_pct, source_tile)
        VALUES
            (%(lake_id)s, %(observed_at)s, %(area_ha)s, %(ndwi_mean)s,
             %(turbidity_index)s, %(cloud_cover_pct)s, %(source_tile)s)
        RETURNING id;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(insert_sql, body.model_dump())
            row_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))

    return JSONResponse(status_code=201, content={"id": row_id})


@router.get("/{lake_id}/history")
def observation_history(
    lake_id: int,
    months: int = Query(12, ge=1, le=120, description="Number of months to look back"),
    conn=Depends(get_db),
):
    """Return time-series observations for a lake going back N months."""
    # Verify lake exists
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM lakes WHERE id = %s", (lake_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Lake with id {lake_id} not found")

    query = """
        SELECT observed_at, area_ha, ndwi_mean, turbidity_index
        FROM lake_observations
        WHERE lake_id = %(lake_id)s
          AND observed_at >= CURRENT_DATE - (%(months)s || ' months')::INTERVAL
        ORDER BY observed_at ASC
    """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, {"lake_id": lake_id, "months": months})
        rows = cur.fetchall()

    return [dict(row) for row in rows]
