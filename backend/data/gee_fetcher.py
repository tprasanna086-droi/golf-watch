"""
Google Earth Engine (GEE) imagery fetcher for Sentinel-2.

Downloads green, nir, and swir bands for a buffer area around a glacial lake
using direct pixel queries to avoid Drive latency.
"""

import datetime
import logging
import os
from pathlib import Path

import ee
from google.oauth2 import service_account

logger = logging.getLogger("gee_fetcher")


def initialize_gee():
    """
    Initializes the GEE Python API using a service account.
    Reads GEE_SERVICE_ACCOUNT and GEE_KEY_FILE from environment variables.
    If either is missing, falls back to ee.Initialize() (uses gcloud credentials).
    Logs success or failure.
    """
    gee_service_account = os.getenv("GEE_SERVICE_ACCOUNT")
    gee_key_file = os.getenv("GEE_KEY_FILE")

    try:
        if gee_service_account and gee_key_file and os.path.exists(gee_key_file):
            logger.info("Initializing GEE with Service Account: %s", gee_service_account)
            credentials = service_account.Credentials.from_service_account_file(
                gee_key_file,
                scopes=["https://www.googleapis.com/auth/earthengine"],
            )
            ee.Initialize(credentials=credentials)
        else:
            logger.info("GEE service account credentials not fully set. Falling back to local credentials.")
            ee.Initialize()
        logger.info("GEE initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize GEE: %s", e)
        raise RuntimeError(f"GEE initialization failed: {e}") from e


def get_sentinel2_collection(
    lat: float,
    lon: float,
    buffer_m: int = 5000,
    start_date: str = None,
    end_date: str = None,
) -> ee.ImageCollection:
    """
    Returns a Sentinel-2 L2A ImageCollection filtered to:
    - A buffer_m metre radius around the given lat/lon point
    - Cloud cover < 20% (CLOUDY_PIXEL_PERCENTAGE property)
    - Date range: start_date to end_date (YYYY-MM-DD strings)
    - If start_date is None, default to 90 days ago
    - If end_date is None, default to today
    - Bands selected: B3 (green), B8 (nir), B11 (swir)
    """
    today = datetime.date.today()
    if not end_date:
        end_date = today.isoformat()
    if not start_date:
        start_date = (today - datetime.timedelta(days=90)).isoformat()

    point = ee.Geometry.Point([lon, lat])
    region = point.buffer(buffer_m)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B3", "B8", "B11"])
    )

    return collection


def export_tile_to_geotiff(
    image: ee.Image,
    region: ee.Geometry,
    output_path: str,
    scale: int = 20,
) -> str:
    """
    Downloads a single GEE image as a GeoTIFF to output_path.
    Uses ee.data.getPixels() for small tiles (avoid Drive export latency).
    Bands: B3, B8, B11 in that order.
    Scale: 20m (matches SWIR resolution).
    Returns output_path on success.
    Raises RuntimeError on failure.
    """
    try:
        logger.info("Fetching pixels from GEE for output: %s", output_path)
        params = {
            "image": image,
            "fileFormat": "GeoTIFF",
            "region": region,
            "scale": scale,
            "bands": ["B3", "B8", "B11"],
        }
        pixel_bytes = ee.data.getPixels(params)
        
        # Write bytes directly to target file
        with open(output_path, "wb") as f:
            f.write(pixel_bytes)
            
        logger.info("Successfully exported tile to %s", output_path)
        return output_path
    except Exception as e:
        logger.error("Failed to export GeoTIFF via getPixels: %s", e)
        raise RuntimeError(f"Failed to export GeoTIFF: {e}") from e


def fetch_latest_tile_for_lake(
    lake_id: int,
    lat: float,
    lon: float,
    output_dir: str = None,
) -> dict:
    """
    High-level function called by the Celery task.
    Steps:
    1. Call initialize_gee()
    2. Create output_dir if it doesn't exist
    3. Get collection for this lat/lon, last 90 days
    4. Sort by system:time_start descending, take the most recent image
    5. Get the image date as a string (YYYY-MM-DD)
    6. Define region as a 5km buffer around the point
    7. Export to {output_dir}/lake_{lake_id}_{date}.tif
    8. Return {"tif_path": path, "observed_at": date, "lake_id": lake_id}
    If collection is empty, raise ValueError("No cloud-free tiles found
    for lake {lake_id} in the last 90 days")
    """
    initialize_gee()

    if not output_dir:
        output_dir = os.getenv("TILE_OUTPUT_DIR", "/tmp/glof_tiles")

    os.makedirs(output_dir, exist_ok=True)

    collection = get_sentinel2_collection(lat, lon)
    size = collection.size().getInfo()

    if size == 0:
        raise ValueError(
            f"No cloud-free tiles found for lake {lake_id} in the last 90 days"
        )

    # Sort descending and get first image
    latest_image = collection.sort("system:time_start", False).first()

    # Get observation date
    date_ms = latest_image.get("system:time_start").getInfo()
    observed_date = datetime.datetime.fromtimestamp(
        date_ms / 1000.0, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d")

    # Define region and output path
    point = ee.Geometry.Point([lon, lat])
    region = point.buffer(5000)
    
    filename = f"lake_{lake_id}_{observed_date}.tif"
    output_path = os.path.join(output_dir, filename)

    export_tile_to_geotiff(latest_image, region, output_path)

    return {
        "tif_path": output_path,
        "observed_at": observed_date,
        "lake_id": lake_id,
    }
