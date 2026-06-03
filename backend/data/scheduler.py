"""
Celery beat scheduler configuration.

Periodically queries lakes from the database, fetches the latest satellite
images, and triggers the anomaly detection pipelines.
"""

import logging
import os

from celery.schedules import crontab
import psycopg2
import psycopg2.extras

from tasks.celery_app import celery_app
from data.gee_fetcher import fetch_latest_tile_for_lake

logger = logging.getLogger("scheduler")


def get_all_lake_coords() -> list[dict]:
    """
    Queries the lakes table and returns a list of dicts:
    [{"id": int, "lat": float, "lon": float, "name": str}, ...]
    Uses DATABASE_URL from environment.
    """
    database_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, lat, lon, name FROM lakes;")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


@celery_app.task(name="tasks.run_monthly_pipeline")
def run_monthly_pipeline():
    """
    Scheduled task — runs on the 1st of every month.
    Steps:
    1. Fetch all lake coords from DB
    2. For each lake, call fetch_latest_tile_for_lake()
    3. For each result, dispatch run_lake_pipeline.delay(lake_id, tif_path, observed_at)
    4. Log progress: "Dispatched pipeline for lake {name} ({id})"
    5. On any per-lake error: log and continue (don't fail entire batch)
    6. Return summary: {"dispatched": N, "failed": M}
    """
    logger.info("Starting monthly GLOF pipeline runs...")
    
    try:
        lakes = get_all_lake_coords()
    except Exception as e:
        logger.error("Failed to query lakes from database: %s", e)
        raise

    dispatched = 0
    failed = 0

    for lake in lakes:
        lake_id = lake["id"]
        lake_name = lake["name"]
        lat = lake["lat"]
        lon = lake["lon"]

        try:
            logger.info("Fetching latest Sentinel-2 tile for %s (%d)...", lake_name, lake_id)
            fetch_result = fetch_latest_tile_for_lake(
                lake_id=lake_id,
                lat=lat,
                lon=lon,
            )
            
            # Send task to the Celery queue by name to avoid import loops
            celery_app.send_task(
                "tasks.run_lake_pipeline",
                args=[
                    fetch_result["lake_id"],
                    fetch_result["tif_path"],
                    fetch_result["observed_at"],
                ],
            )
            
            logger.info("Dispatched pipeline for lake %s (%d)", lake_name, lake_id)
            dispatched += 1
        except Exception as e:
            logger.error("Failed to fetch image or dispatch pipeline for lake %s (%d): %s", lake_name, lake_id, e)
            failed += 1
            continue

    logger.info("Monthly GLOF pipeline completed. Dispatched: %d, Failed: %d", dispatched, failed)
    return {"dispatched": dispatched, "failed": failed}


CELERYBEAT_SCHEDULE = {
    "monthly-glof-pipeline": {
        "task": "tasks.run_monthly_pipeline",
        "schedule": crontab(day_of_month="1", hour="2", minute="0"),
        # Runs at 02:00 Nepal time on the 1st of every month
    }
}

# Register schedule on the celery_app
celery_app.conf.beat_schedule = CELERYBEAT_SCHEDULE
celery_app.conf.timezone = "Asia/Kathmandu"
