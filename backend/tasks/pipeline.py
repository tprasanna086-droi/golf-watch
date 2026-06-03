"""
Full GLOF pipeline task — processes one satellite tile for one lake.

Steps: load → preprocess → segment → polygonise → detect change → score → alert.
"""

import logging
import os
from pathlib import Path

import numpy as np
import psycopg2
import rasterio.transform
from dotenv import load_dotenv

from tasks.celery_app import celery_app
from ml.preprocess import (
    load_sentinel2_bands,
    build_input_tensor,
    compute_ndwi,
    compute_turbidity,
    tile_image,
)
from ml.unet import get_unet_model, run_inference, mask_to_polygon
from ml.change_detection import compute_feature_vector
from ml.anomaly import fit_isolation_forest, score_observation, classify_alert_level
from alerts_dispatch import dispatch_alert

# Load .env from backend root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)


def _get_db_connection():
    """Create a raw psycopg2 connection from DATABASE_URL."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _stitch_masks(tiles_with_masks, full_shape, tile_size, overlap):
    """
    Reconstruct a full-image probability mask by averaging overlapping tiles.

    Args:
        tiles_with_masks: list of (mask_2d, row_offset, col_offset)
        full_shape: (H, W) of the padded image
        tile_size: size of each tile
        overlap: overlap between tiles

    Returns:
        (H, W) float32 averaged probability mask
    """
    h, w = full_shape
    accum = np.zeros((h, w), dtype=np.float32)
    count = np.zeros((h, w), dtype=np.float32)

    for mask, row, col in tiles_with_masks:
        r_end = min(row + tile_size, h)
        c_end = min(col + tile_size, w)
        mh = r_end - row
        mw = c_end - col
        accum[row:r_end, col:c_end] += mask[:mh, :mw]
        count[row:r_end, col:c_end] += 1.0

    # Avoid division by zero
    count = np.maximum(count, 1.0)
    return accum / count


@celery_app.task(name="tasks.run_lake_pipeline")
def run_lake_pipeline(lake_id: int, tif_path: str, observed_at: str):
    """
    Full pipeline for one lake + one satellite tile.

    Args:
        lake_id: Database ID of the lake.
        tif_path: Path to the Sentinel-2 GeoTIFF (3-band: green, nir, swir).
        observed_at: Date string YYYY-MM-DD.

    Returns:
        dict with lake_id, observed_at, area_ha, ndwi_mean,
        turbidity_index, alert_level, observation_id.
    """
    alert_level = None
    observation_id = None

    try:
        # ──────────────────────────────────────────────
        # 1. Load bands from GeoTIFF
        # ──────────────────────────────────────────────
        logger.info("Loading bands from %s", tif_path)
        bands = load_sentinel2_bands(tif_path)

        # ──────────────────────────────────────────────
        # 2. Build 5-channel input tensor (green, nir, swir, ndwi, turbidity)
        # ──────────────────────────────────────────────
        input_tensor = build_input_tensor(bands)  # (5, H, W)

        # ──────────────────────────────────────────────
        # 3. Tile the tensor into overlapping 256×256 patches
        # ──────────────────────────────────────────────
        tile_size = 256
        overlap = 32
        tiles = tile_image(input_tensor, tile_size=tile_size, overlap=overlap)
        logger.info("Split into %d tiles", len(tiles))

        # ──────────────────────────────────────────────
        # 4. Load U-Net model (no pretrained weights in worker)
        # ──────────────────────────────────────────────
        model = get_unet_model(pretrained=False)

        # ──────────────────────────────────────────────
        # 5. Run inference on each tile
        # ──────────────────────────────────────────────
        tiles_with_masks = []
        for tile_arr, row_off, col_off in tiles:
            prob_mask = run_inference(model, tile_arr, device="cpu")
            tiles_with_masks.append((prob_mask, row_off, col_off))

        # ──────────────────────────────────────────────
        # 6. Stitch tiles back into full-image mask
        # ──────────────────────────────────────────────
        _, orig_h, orig_w = input_tensor.shape
        # Compute padded dimensions (same logic as tile_image)
        step = tile_size - overlap
        pad_h = (step - (orig_h % step)) % step + overlap
        pad_w = (step - (orig_w % step)) % step + overlap
        full_h, full_w = orig_h + pad_h, orig_w + pad_w

        full_mask = _stitch_masks(tiles_with_masks, (full_h, full_w), tile_size, overlap)
        # Crop back to original size
        full_mask = full_mask[:orig_h, :orig_w]

        # ──────────────────────────────────────────────
        # 7. Extract polygons from the mask
        # ──────────────────────────────────────────────
        # Dummy 1×1 degree Affine transform (will wire real transforms later)
        dummy_transform = rasterio.transform.from_bounds(
            0, 0, 1, 1, orig_w, orig_h
        )
        polygons = mask_to_polygon(full_mask, dummy_transform, threshold=0.5)
        logger.info("Extracted %d polygons", len(polygons))

        # ──────────────────────────────────────────────
        # 8. Compute area_ha from the largest polygon
        # ──────────────────────────────────────────────
        if polygons:
            largest = max(polygons, key=lambda p: p.area)
            # Placeholder hectare conversion (will calibrate with real CRS later)
            area_ha = largest.area * 1e10
        else:
            area_ha = 0.0

        # ──────────────────────────────────────────────
        # 9. Compute ndwi_mean
        # ──────────────────────────────────────────────
        ndwi = compute_ndwi(bands["green"], bands["nir"])
        ndwi_mean = float(np.mean(ndwi))

        # ──────────────────────────────────────────────
        # 10. Compute turbidity_index
        # ──────────────────────────────────────────────
        turbidity = compute_turbidity(bands["nir"], bands["swir"])
        turbidity_index = float(np.mean(turbidity))

        # ──────────────────────────────────────────────
        # 11. Insert observation into lake_observations
        # ──────────────────────────────────────────────
        conn = _get_db_connection()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lake_observations
                        (lake_id, observed_at, area_ha, ndwi_mean,
                         turbidity_index, cloud_cover_pct, source_tile)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (lake_id, observed_at, area_ha, ndwi_mean,
                     turbidity_index, None, tif_path),
                )
                observation_id = cur.fetchone()[0]
            conn.commit()

            # ──────────────────────────────────────────
            # 12. Fetch the previous observation
            # ──────────────────────────────────────────
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT area_ha, ndwi_mean, turbidity_index
                    FROM lake_observations
                    WHERE lake_id = %s AND observed_at < %s
                    ORDER BY observed_at DESC
                    LIMIT 1;
                    """,
                    (lake_id, observed_at),
                )
                prev = cur.fetchone()

            # ──────────────────────────────────────────
            # 13. Change detection + anomaly scoring
            # ──────────────────────────────────────────
            if prev:
                prev_area, prev_ndwi, prev_turbidity = prev

                # Use largest polygon for shape irregularity (or a dummy circle)
                poly_t2 = polygons[0] if polygons else None

                if poly_t2:
                    # a. Compute feature vector
                    fv = compute_feature_vector(
                        area_t1=prev_area,
                        area_t2=area_ha,
                        ndwi_t1=prev_ndwi,
                        ndwi_t2=ndwi_mean,
                        turbidity_t1=prev_turbidity,
                        turbidity_t2=turbidity_index,
                        polygon_t2=poly_t2,
                    )

                    # b. 2-sample bootstrap IsolationForest
                    #    (placeholder — will replace with rolling model)
                    prev_fv = {
                        "area_delta_pct": 0.0,
                        "ndwi_delta": 0.0,
                        "turbidity_delta": 0.0,
                        "shape_irregularity": 1.0,
                    }
                    iso_model = fit_isolation_forest([prev_fv, fv])
                    anomaly_score = score_observation(iso_model, fv)

                    # c. Classify alert level
                    alert_level = classify_alert_level(
                        anomaly_score, fv["area_delta_pct"]
                    )

                    # d. Insert alert if triggered
                    if alert_level is not None:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO alerts
                                    (lake_id, anomaly_score, area_delta_pct,
                                     alert_level, message)
                                VALUES (%s, %s, %s, %s, %s)
                                RETURNING id;
                                """,
                                (
                                    lake_id,
                                    anomaly_score,
                                    fv["area_delta_pct"],
                                    alert_level,
                                    f"Lake {lake_id}: {alert_level} — "
                                    f"area Δ {fv['area_delta_pct']:.1f}%, "
                                    f"anomaly score {anomaly_score:.3f}",
                                ),
                            )
                            alert_db_id = cur.fetchone()[0]
                        conn.commit()
                        logger.warning(
                            "ALERT [%s] for lake %d: score=%.3f, area_delta=%.1f%%",
                            alert_level, lake_id, anomaly_score, fv["area_delta_pct"],
                        )

                        try:
                            dispatch_alert(
                                lake_id=lake_id,
                                lake_name=str(lake_id),  # placeholder
                                district="Nepal",         # placeholder
                                alert_level=alert_level,
                                area_delta_pct=fv["area_delta_pct"],
                                anomaly_score=anomaly_score,
                                alert_db_id=alert_db_id
                            )
                        except Exception as dispatch_err:
                            logger.error("Failed to dispatch SMS alert: %s", dispatch_err)

        finally:
            conn.close()

        # ──────────────────────────────────────────────
        # 14. Return summary dict
        # ──────────────────────────────────────────────
        result = {
            "lake_id": lake_id,
            "observed_at": observed_at,
            "area_ha": round(area_ha, 4),
            "ndwi_mean": round(ndwi_mean, 6),
            "turbidity_index": round(turbidity_index, 6),
            "alert_level": alert_level or "none",
            "observation_id": observation_id,
        }
        logger.info("Pipeline complete for lake %d: %s", lake_id, result)
        return result

    except Exception:
        logger.exception("Pipeline FAILED for lake %d, tile %s", lake_id, tif_path)
        raise
