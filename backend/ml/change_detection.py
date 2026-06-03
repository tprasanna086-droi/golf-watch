"""
Temporal change detection utilities.

Computes deltas between consecutive observations and assembles
feature vectors for the anomaly detection pipeline.
"""

import math

from shapely.geometry import Polygon


def compute_area_delta(area_t1: float, area_t2: float) -> float:
    """
    Returns percentage change: (area_t2 - area_t1) / (area_t1 + 1e-8) * 100
    """
    return (area_t2 - area_t1) / (area_t1 + 1e-8) * 100.0


def compute_shape_irregularity(polygon: Polygon) -> float:
    """
    Polsby-Popper score = 4π * area / perimeter²
    Lower score = more irregular = potentially unstable boundary.
    Returns float in [0, 1]. Requires a shapely polygon.
    """
    area = polygon.area
    perimeter = polygon.length

    if perimeter == 0:
        return 0.0

    score = (4.0 * math.pi * area) / (perimeter ** 2)
    # Clamp to [0, 1] in case of floating-point edge cases
    return max(0.0, min(1.0, score))


def compute_feature_vector(
    area_t1: float,
    area_t2: float,
    ndwi_t1: float,
    ndwi_t2: float,
    turbidity_t1: float,
    turbidity_t2: float,
    polygon_t2: Polygon,
) -> dict:
    """
    Assembles the feature vector used by the anomaly scorer.

    Returns:
        {
          area_delta_pct:      float,
          ndwi_delta:          float,   # ndwi_t2 - ndwi_t1
          turbidity_delta:     float,   # turbidity_t2 - turbidity_t1
          shape_irregularity:  float,
        }
    """
    return {
        "area_delta_pct": compute_area_delta(area_t1, area_t2),
        "ndwi_delta": ndwi_t2 - ndwi_t1,
        "turbidity_delta": turbidity_t2 - turbidity_t1,
        "shape_irregularity": compute_shape_irregularity(polygon_t2),
    }
