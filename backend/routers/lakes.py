"""
Routes for glacial lake data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg2.extras

from db.connection import get_db

router = APIRouter(prefix="/api/lakes", tags=["lakes"])

# Map risk_class to sort priority (critical first)
RISK_ORDER = """
    CASE risk_class
        WHEN 'critical' THEN 1
        WHEN 'high'     THEN 2
        WHEN 'moderate' THEN 3
        WHEN 'low'      THEN 4
        ELSE 5
    END
"""


@router.get("")
def list_lakes(
    basin: str | None = Query(None, description="Filter by basin name"),
    risk_class: str | None = Query(None, description="Filter by risk class"),
    conn=Depends(get_db),
):
    """Return all lakes, optionally filtered by basin and/or risk_class."""
    query = f"""
        SELECT id, name, district, basin, lat, lon, initial_area_ha, risk_class
        FROM lakes
        WHERE 1=1
    """
    params = {}

    if basin:
        query += " AND basin = %(basin)s"
        params["basin"] = basin

    if risk_class:
        if risk_class not in ("low", "moderate", "high", "critical"):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid risk_class '{risk_class}'. Must be one of: low, moderate, high, critical",
            )
        query += " AND risk_class = %(risk_class)s"
        params["risk_class"] = risk_class

    query += f" ORDER BY {RISK_ORDER}, name"

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        lakes = cur.fetchall()

    return [dict(row) for row in lakes]


@router.get("/{lake_id}")
def get_lake(lake_id: int, conn=Depends(get_db)):
    """Return a single lake with its last 24 observations."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Fetch lake
        cur.execute(
            """
            SELECT id, name, district, basin, lat, lon, initial_area_ha, risk_class
            FROM lakes WHERE id = %(lake_id)s
            """,
            {"lake_id": lake_id},
        )
        lake = cur.fetchone()

        if not lake:
            raise HTTPException(status_code=404, detail=f"Lake with id {lake_id} not found")

        # Fetch last 24 observations
        cur.execute(
            """
            SELECT observed_at, area_ha, ndwi_mean, turbidity_index
            FROM lake_observations
            WHERE lake_id = %(lake_id)s
            ORDER BY observed_at DESC
            LIMIT 24
            """,
            {"lake_id": lake_id},
        )
        observations = cur.fetchall()

    result = dict(lake)
    result["observations"] = [dict(row) for row in observations]
    return result
