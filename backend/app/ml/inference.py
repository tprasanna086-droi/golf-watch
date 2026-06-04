"""
Run U-Net inference on Sentinel-2 tiles and prepare observation records for the database.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import psycopg2
import rasterio.features
from dotenv import load_dotenv
from rasterio.transform import Affine
from shapely.geometry import MultiPolygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.ml.unet import load_unet, predict_mask
from app.pipeline.band_math import (
    compute_ndwi,
    compute_shape_irregularity,
    compute_turbidity,
    estimate_area_km2,
    normalize_bands,
)
from app.pipeline.sentinel_fetcher import (
    download_tile_as_array,
    fetch_sentinel2_tile,
    initialize_gee,
)

logger = logging.getLogger(__name__)

BAND_GREEN = 0
BAND_NIR = 2
BAND_SWIR = 3
SPECTRAL_CHANNEL_COUNT = 4

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

METERS_PER_DEGREE_LAT = 111_320.0


@dataclass
class LakeInferenceResult:
    """Outputs from a single lake U-Net inference run."""

    lake_id: str
    observed_at: str
    area_km2: float
    ndwi_mean: float
    turbidity_index: float
    shape_irregularity: float
    mask_array: np.ndarray
    mask_geojson: dict[str, Any]
    sentinel_tile_id: str
    cloud_cover_pct: float


def mask_to_geojson(
    mask: np.ndarray,
    latitude: float,
    longitude: float,
    scale_m: int = 10,
) -> dict[str, Any]:
    """
    Vectorize a binary mask to a GeoJSON MultiPolygon in WGS84.

    Pixel coordinates are mapped with a simple affine transform centered on the
    given latitude and longitude, using ``scale_m`` metres per pixel.
    """
    binary = (np.asarray(mask) > 0).astype(np.uint8)
    if not np.any(binary):
        return {"type": "MultiPolygon", "coordinates": []}

    height, width = binary.shape
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))
    pixel_width_deg = scale_m / meters_per_degree_lon
    pixel_height_deg = scale_m / METERS_PER_DEGREE_LAT

    transform = Affine(
        pixel_width_deg,
        0.0,
        longitude - (width / 2.0) * pixel_width_deg,
        0.0,
        -pixel_height_deg,
        latitude + (height / 2.0) * pixel_height_deg,
    )

    polygons: list[BaseGeometry] = []
    for geometry, value in rasterio.features.shapes(
        binary,
        mask=binary.astype(bool),
        transform=transform,
    ):
        if value == 1:
            polygons.append(shape(geometry))

    if not polygons:
        return {"type": "MultiPolygon", "coordinates": []}

    merged = unary_union(polygons)
    if merged.geom_type == "Polygon":
        merged = MultiPolygon([merged])
    elif merged.geom_type == "GeometryCollection":
        polygon_parts = [
            geom for geom in merged.geoms if geom.geom_type in ("Polygon", "MultiPolygon")
        ]
        if not polygon_parts:
            return {"type": "MultiPolygon", "coordinates": []}
        merged = unary_union(polygon_parts)
        if merged.geom_type == "Polygon":
            merged = MultiPolygon([merged])

    return mapping(merged)


def run_inference(
    lake_id: str,
    latitude: float,
    longitude: float,
    date_start: str,
    date_end: str,
    model_path: str,
    device: str = "cpu",
    scale_m: int = 10,
) -> LakeInferenceResult:
    """
    Fetch Sentinel-2 data, run U-Net segmentation, and compute lake metrics.
    """
    try:
        initialize_gee(
            os.getenv("GEE_SERVICE_ACCOUNT", ""),
            os.getenv("GEE_KEY_FILE", ""),
        )

        tile = fetch_sentinel2_tile(
            latitude=latitude,
            longitude=longitude,
            date_start=date_start,
            date_end=date_end,
        )
        array = download_tile_as_array(
            tile["image"],
            tile["region"],
            scale=scale_m,
        )

        if array.shape[2] < SPECTRAL_CHANNEL_COUNT:
            raise ValueError(
                f"Expected at least {SPECTRAL_CHANNEL_COUNT} spectral bands, "
                f"got shape {array.shape}"
            )

        spectral = array[:, :, :SPECTRAL_CHANNEL_COUNT]
        normalized = normalize_bands(spectral)

        model = load_unet(model_path, device=device)
        inference_start = time.perf_counter()
        mask = predict_mask(model, normalized, device=device)
        inference_seconds = time.perf_counter() - inference_start
        logger.info(
            "U-Net inference for lake %s completed in %.2f s (mask shape %s)",
            lake_id,
            inference_seconds,
            mask.shape,
        )

        green = spectral[:, :, BAND_GREEN]
        nir = spectral[:, :, BAND_NIR]
        swir = spectral[:, :, BAND_SWIR]
        ndwi = compute_ndwi(green, nir)
        turbidity = compute_turbidity(swir, nir)

        lake_pixels = mask > 0
        if np.any(lake_pixels):
            ndwi_mean = float(ndwi[lake_pixels].mean())
            turbidity_index = float(turbidity[lake_pixels].mean())
        else:
            ndwi_mean = 0.0
            turbidity_index = 0.0

        area_km2 = estimate_area_km2(mask, latitude=latitude, scale_m=scale_m)
        shape_irregularity = compute_shape_irregularity(mask)
        mask_geojson = mask_to_geojson(
            mask,
            latitude=latitude,
            longitude=longitude,
            scale_m=scale_m,
        )

        sentinel_tile_id = (
            f"S2_{date_start}_{date_end}_{tile['image_count']}scenes"
        )

        return LakeInferenceResult(
            lake_id=lake_id,
            observed_at=date_end,
            area_km2=area_km2,
            ndwi_mean=ndwi_mean,
            turbidity_index=turbidity_index,
            shape_irregularity=shape_irregularity,
            mask_array=mask.astype(np.uint8, copy=False),
            mask_geojson=mask_geojson,
            sentinel_tile_id=sentinel_tile_id,
            cloud_cover_pct=float(tile["cloud_filter_pct"]),
        )
    except Exception:
        logger.exception("Inference failed for lake %s", lake_id)
        raise


def _sync_database_url(database_url: str) -> str:
    """Convert async SQLAlchemy URLs to psycopg2-compatible URLs."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def save_observation_to_db(
    result: LakeInferenceResult,
    database_url: str,
) -> str:
    """
    Insert a lake_observations row and return the new observation UUID.
    """
    try:
        geometry = shape(result.mask_geojson)
        mask_wkt: str | None = geometry.wkt if not geometry.is_empty else None

        conn = psycopg2.connect(_sync_database_url(database_url))
        try:
            with conn:
                with conn.cursor() as cur:
                    if mask_wkt:
                        cur.execute(
                            """
                            INSERT INTO lake_observations (
                                lake_id,
                                observed_at,
                                area_km2,
                                ndwi_mean,
                                turbidity_index,
                                shape_irregularity,
                                mask_geom,
                                cloud_cover_pct,
                                sentinel_tile_id
                            )
                            VALUES (
                                %s, %s, %s, %s, %s, %s,
                                ST_SetSRID(ST_GeomFromText(%s), 4326),
                                %s, %s
                            )
                            RETURNING id
                            """,
                            (
                                result.lake_id,
                                result.observed_at,
                                result.area_km2,
                                result.ndwi_mean,
                                result.turbidity_index,
                                result.shape_irregularity,
                                mask_wkt,
                                result.cloud_cover_pct,
                                result.sentinel_tile_id,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO lake_observations (
                                lake_id,
                                observed_at,
                                area_km2,
                                ndwi_mean,
                                turbidity_index,
                                shape_irregularity,
                                mask_geom,
                                cloud_cover_pct,
                                sentinel_tile_id
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s)
                            RETURNING id
                            """,
                            (
                                result.lake_id,
                                result.observed_at,
                                result.area_km2,
                                result.ndwi_mean,
                                result.turbidity_index,
                                result.shape_irregularity,
                                result.cloud_cover_pct,
                                result.sentinel_tile_id,
                            ),
                        )
                    observation_id = cur.fetchone()[0]
        finally:
            conn.close()

        observation_uuid = str(observation_id)
        logger.info(
            "Saved observation %s for lake %s (area_km2=%.4f)",
            observation_uuid,
            result.lake_id,
            result.area_km2,
        )
        return observation_uuid
    except Exception:
        logger.exception(
            "Failed to save observation for lake %s to database",
            result.lake_id,
        )
        raise


def _last_n_days_range(days: int) -> tuple[str, str]:
    """Return ISO date strings for a range ending today."""
    today = date.today()
    start = today - timedelta(days=days)
    return start.isoformat(), today.isoformat()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    model_path = os.getenv("MODEL_PATH")
    database_url = os.getenv("DATABASE_URL")
    lake_id = os.getenv("LAKE_ID", "")

    if not model_path:
        raise SystemExit("MODEL_PATH environment variable is required")

    imja_lat = 27.8975
    imja_lon = 86.9175
    date_start, date_end = _last_n_days_range(90)

    inference_result = run_inference(
        lake_id=lake_id,
        latitude=imja_lat,
        longitude=imja_lon,
        date_start=date_start,
        date_end=date_end,
        model_path=model_path,
        device=os.getenv("INFERENCE_DEVICE", "cpu"),
    )

    print(f"lake_id: {inference_result.lake_id}")
    print(f"observed_at: {inference_result.observed_at}")
    print(f"area_km2: {inference_result.area_km2:.6f}")
    print(f"ndwi_mean: {inference_result.ndwi_mean:.6f}")
    print(f"turbidity_index: {inference_result.turbidity_index:.6f}")
    print(f"shape_irregularity: {inference_result.shape_irregularity:.6f}")
    print(f"sentinel_tile_id: {inference_result.sentinel_tile_id}")
    print(f"cloud_cover_pct: {inference_result.cloud_cover_pct:.2f}")
    print(f"mask_geojson_type: {inference_result.mask_geojson.get('type')}")

    if database_url:
        if not lake_id:
            logger.warning("LAKE_ID is not set; database insert may fail foreign key check")
        observation_id = save_observation_to_db(inference_result, database_url)
        print(f"observation_id: {observation_id}")
    else:
        logger.info("DATABASE_URL not set; skipping database insert")
