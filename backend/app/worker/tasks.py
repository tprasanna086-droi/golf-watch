"""
Celery tasks for Sentinel-2 ingestion, observations, and anomaly checks.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import numpy as np
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from app.pipeline.band_math import (
    compute_ndwi,
    compute_shape_irregularity,
    compute_turbidity,
    estimate_area_km2,
    extract_water_mask,
)
from app.pipeline.sentinel_fetcher import (
    download_tile_as_array,
    fetch_sentinel2_tile,
    initialize_gee,
)
from app.services.sms import load_sms_config, send_alert_sms
from app.worker.celery_app import celery_app

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

logger = logging.getLogger(__name__)

BAND_GREEN = 0
BAND_NIR = 2
BAND_SWIR = 3
DEFAULT_PIXEL_SCALE_M = 10


def _sync_database_url() -> str:
    """Return a psycopg2-compatible DATABASE_URL."""
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://glof:glof@localhost:5432/glofwatch",
    )
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _get_db_connection() -> psycopg2.extensions.connection:
    """Open a synchronous PostgreSQL connection."""
    return psycopg2.connect(_sync_database_url())


def _fetch_lake(lake_id: str) -> dict[str, Any]:
    """Load lake metadata required for imagery fetch and area estimation."""
    lake_uuid = UUID(lake_id)
    conn = _get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, latitude, longitude
                FROM lakes
                WHERE id = %s
                """,
                (str(lake_uuid),),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Lake with id {lake_id} not found")
            return dict(row)
    finally:
        conn.close()


def _insert_observation(
    lake_id: str,
    observed_at: str,
    area_km2: float,
    ndwi_mean: float,
    turbidity_index: float,
    shape_irregularity: float,
    cloud_cover_pct: Optional[float],
    sentinel_tile_id: Optional[str],
) -> None:
    """Insert a new lake_observations row."""
    conn = _get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lake_observations (
                        lake_id,
                        observed_at,
                        area_km2,
                        ndwi_mean,
                        turbidity_index,
                        shape_irregularity,
                        cloud_cover_pct,
                        sentinel_tile_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        lake_id,
                        observed_at,
                        area_km2,
                        ndwi_mean,
                        turbidity_index,
                        shape_irregularity,
                        cloud_cover_pct,
                        sentinel_tile_id,
                    ),
                )
    finally:
        conn.close()


def _severity_from_z_score(z_score: float) -> str:
    """Map a Z-score to alert severity tiers."""
    if z_score > 5.0:
        return "emergency"
    if z_score > 3.5:
        return "warning"
    return "watch"


@celery_app.task(
    bind=True,
    max_retries=3,
    name="glof_watch.tasks.process_lake_observation",
)
def process_lake_observation(
    self: Any,
    lake_id: str,
    date_start: str,
    date_end: str,
) -> dict[str, Any]:
    """
    Fetch Sentinel-2 imagery for one lake, derive metrics, and store an observation.
    """
    try:
        logger.info(
            "Processing observation for lake %s (%s to %s)",
            lake_id,
            date_start,
            date_end,
        )

        lake = _fetch_lake(lake_id)
        logger.info("Loaded lake %s (%s)", lake_id, lake["name"])

        initialize_gee(
            os.getenv("GEE_SERVICE_ACCOUNT", ""),
            os.getenv("GEE_KEY_FILE", ""),
        )
        logger.info("GEE initialized for lake %s", lake_id)

        tile = fetch_sentinel2_tile(
            latitude=float(lake["latitude"]),
            longitude=float(lake["longitude"]),
            date_start=date_start,
            date_end=date_end,
        )
        logger.info(
            "Fetched Sentinel-2 composite for lake %s (%d scenes)",
            lake_id,
            tile["image_count"],
        )

        array = download_tile_as_array(
            tile["image"],
            tile["region"],
            scale=DEFAULT_PIXEL_SCALE_M,
        )
        logger.info("Downloaded tile array for lake %s with shape %s", lake_id, array.shape)

        green = array[:, :, BAND_GREEN]
        nir = array[:, :, BAND_NIR]
        swir = array[:, :, BAND_SWIR]

        ndwi = compute_ndwi(green, nir)
        turbidity = compute_turbidity(swir, nir)
        water_mask = extract_water_mask(ndwi, threshold=0.0)
        shape_irregularity = compute_shape_irregularity(water_mask)
        area_km2 = estimate_area_km2(
            water_mask,
            latitude=float(lake["latitude"]),
            scale_m=DEFAULT_PIXEL_SCALE_M,
        )
        ndwi_mean = float(np.mean(ndwi))
        turbidity_index = float(np.mean(turbidity))

        logger.info(
            "Derived metrics for lake %s: area_km2=%.4f, ndwi_mean=%.4f, "
            "turbidity_index=%.4f, shape_irregularity=%.4f",
            lake_id,
            area_km2,
            ndwi_mean,
            turbidity_index,
            shape_irregularity,
        )

        sentinel_tile_id = f"S2_{date_start}_{date_end}_{tile['image_count']}scenes"
        _insert_observation(
            lake_id=lake_id,
            observed_at=date_end,
            area_km2=area_km2,
            ndwi_mean=ndwi_mean,
            turbidity_index=turbidity_index,
            shape_irregularity=shape_irregularity,
            cloud_cover_pct=float(tile["cloud_filter_pct"]),
            sentinel_tile_id=sentinel_tile_id,
        )
        logger.info("Inserted observation for lake %s on %s", lake_id, date_end)

        return {
            "lake_id": lake_id,
            "observed_at": date_end,
            "area_km2": area_km2,
            "ndwi_mean": ndwi_mean,
            "turbidity_index": turbidity_index,
            "shape_irregularity": shape_irregularity,
        }
    except Exception as exc:
        logger.exception(
            "process_lake_observation failed for lake %s (attempt %s)",
            lake_id,
            self.request.retries,
        )
        countdown = 60 * (2**self.request.retries)
        raise self.retry(exc=exc, countdown=countdown) from exc


@celery_app.task(name="glof_watch.tasks.run_monthly_pipeline")
def run_monthly_pipeline() -> dict[str, int]:
    """
    Dispatch process_lake_observation for every lake for the current month to date.
    """
    today = date.today()
    date_start = today.replace(day=1).isoformat()
    date_end = today.isoformat()

    logger.info(
        "Starting monthly pipeline for %s through %s",
        date_start,
        date_end,
    )

    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM lakes")
            lake_rows = cur.fetchall()
    finally:
        conn.close()

    dispatched = 0
    for (lake_uuid,) in lake_rows:
        process_lake_observation.delay(str(lake_uuid), date_start, date_end)
        dispatched += 1

    logger.info("Monthly pipeline dispatched %d lake observation jobs", dispatched)
    return {"jobs_dispatched": dispatched}


@celery_app.task(name="glof_watch.tasks.check_anomalies")
def check_anomalies(lake_id: str) -> dict[str, Any]:
    """
    Detect rapid area growth from recent observations and create alerts when needed.
    """
    logger.info("Checking anomalies for lake %s", lake_id)

    conn = _get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT area_km2, observed_at
                FROM lake_observations
                WHERE lake_id = %s AND area_km2 IS NOT NULL
                ORDER BY observed_at DESC
                LIMIT 24
                """,
                (lake_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if len(rows) < 3:
        logger.info(
            "Lake %s has fewer than 3 observations with area_km2; skipping anomaly check",
            lake_id,
        )
        return {"lake_id": lake_id, "z_score": None, "alert_created": False}

    areas = np.array([float(row["area_km2"]) for row in rows], dtype=np.float64)
    latest_area = float(areas[0])
    historical = areas[1:]
    mean_area = float(np.mean(historical))
    std_area = float(np.std(historical, ddof=1))

    if std_area <= 0.0:
        logger.info("Lake %s area history has zero variance; skipping alert", lake_id)
        return {"lake_id": lake_id, "z_score": 0.0, "alert_created": False}

    z_score = float((latest_area - mean_area) / std_area)
    logger.info("Lake %s latest area Z-score: %.3f", lake_id, z_score)

    if z_score <= 2.5:
        return {"lake_id": lake_id, "z_score": z_score, "alert_created": False}

    severity = _severity_from_z_score(z_score)
    previous_area = float(areas[1]) if len(areas) > 1 else mean_area
    area_delta_km2 = latest_area - previous_area
    message = (
        f"Rapid growth detected for lake {lake_id}: area {latest_area:.4f} km² "
        f"(Z-score {z_score:.2f}, Δ {area_delta_km2:+.4f} km² vs prior observation)"
    )

    conn = _get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts (
                        lake_id,
                        alert_type,
                        severity,
                        area_delta_km2,
                        anomaly_score,
                        message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        lake_id,
                        "rapid_growth",
                        severity,
                        area_delta_km2,
                        z_score,
                        message,
                    ),
                )
    finally:
        conn.close()

    logger.warning("Created %s alert for lake %s (Z-score %.3f)", severity, lake_id, z_score)
    return {"lake_id": lake_id, "z_score": z_score, "alert_created": True}


def _parse_contributing_factors(message: Optional[str]) -> list[str]:
    """Split a stored alert message into contributing factor lines."""
    if not message or not message.strip():
        return ["GLOF risk threshold exceeded"]
    parts = [part.strip() for part in message.split(";") if part.strip()]
    return parts if parts else [message.strip()]


def _fetch_alert_for_sms(alert_id: str) -> dict[str, Any]:
    """Load alert fields and lake name required for SMS dispatch."""
    alert_uuid = UUID(alert_id)
    conn = _get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.lake_id,
                    a.severity,
                    a.area_delta_km2,
                    a.anomaly_score,
                    a.message,
                    a.sms_sent,
                    l.name AS lake_name
                FROM alerts a
                JOIN lakes l ON l.id = a.lake_id
                WHERE a.id = %s
                """,
                (str(alert_uuid),),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Alert with id {alert_id} not found")
            return dict(row)
    finally:
        conn.close()


def _fetch_latest_area_km2(lake_id: str) -> float:
    """Return the most recent observed lake area, or 0.0 if none exists."""
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT area_km2
                FROM lake_observations
                WHERE lake_id = %s AND area_km2 IS NOT NULL
                ORDER BY observed_at DESC
                LIMIT 1
                """,
                (lake_id,),
            )
            row = cur.fetchone()
            if row is None or row[0] is None:
                return 0.0
            return float(row[0])
    finally:
        conn.close()


def _mark_alert_sms_sent(alert_id: str) -> None:
    """Set sms_sent=true on the alert row."""
    conn = _get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE alerts
                    SET sms_sent = TRUE
                    WHERE id = %s
                    """,
                    (alert_id,),
                )
    finally:
        conn.close()


@celery_app.task(name="glof_watch.tasks.dispatch_sms_alert")
def dispatch_sms_alert(alert_id: str) -> dict[str, Any]:
    """
    Load an alert from the database and dispatch Twilio SMS notifications.

    Updates ``sms_sent`` when at least one message is delivered successfully.
    """
    logger.info("Dispatching SMS for alert %s", alert_id)

    try:
        alert = _fetch_alert_for_sms(alert_id)
    except ValueError as exc:
        logger.error("%s", exc)
        raise

    if alert.get("sms_sent"):
        logger.info("Alert %s already has sms_sent=true; skipping dispatch", alert_id)
        return {
            "alert_id": alert_id,
            "sms_sent": False,
            "message_sids": [],
            "skipped": "already_sent",
        }

    severity = str(alert.get("severity") or "watch")
    lake_name = str(alert["lake_name"])
    area_delta_km2 = float(alert.get("area_delta_km2") or 0.0)
    z_score = float(alert.get("anomaly_score") or 0.0)
    contributing_factors = _parse_contributing_factors(alert.get("message"))

    area_km2 = _fetch_latest_area_km2(str(alert["lake_id"]))
    if area_km2 == 0.0:
        logger.warning(
            "No area_km2 observation for lake %s; using delta-only area estimate",
            alert["lake_id"],
        )
        area_km2 = max(area_delta_km2, 0.0)

    try:
        config = load_sms_config()
    except ValueError as exc:
        logger.error("SMS config error for alert %s: %s", alert_id, exc)
        raise

    message_sids = send_alert_sms(
        config=config,
        lake_name=lake_name,
        severity=severity,
        area_km2=area_km2,
        area_delta_km2=area_delta_km2,
        z_score=z_score,
        contributing_factors=contributing_factors,
    )

    if not message_sids:
        logger.info(
            "No SMS sent for alert %s (severity %s, min_severity %s)",
            alert_id,
            severity,
            config.min_severity,
        )
        return {
            "alert_id": alert_id,
            "sms_sent": False,
            "message_sids": [],
            "skipped": "below_min_severity_or_send_failed",
        }

    _mark_alert_sms_sent(alert_id)
    logger.info(
        "SMS dispatch succeeded for alert %s (%d message(s))",
        alert_id,
        len(message_sids),
    )
    return {
        "alert_id": alert_id,
        "sms_sent": True,
        "message_sids": message_sids,
    }
