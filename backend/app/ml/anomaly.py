"""
Score glacial lake observations for anomalous growth using Z-score and Isolation Forest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 24
MIN_ZSCORE_HISTORY = 3
MIN_ISOLATION_HISTORY = 6


@dataclass
class LakeAnomalyResult:
    """Anomaly assessment for a single lake observation series."""

    lake_id: str
    latest_area_km2: float
    mean_area_km2: float
    std_area_km2: float
    z_score: float
    isolation_score: float
    is_anomaly: bool
    severity: str
    contributing_factors: list[str] = field(default_factory=list)


def compute_z_score(history: list[float], latest: float) -> float:
    """
    Compute the Z-score of ``latest`` relative to ``history``.

    Returns 0.0 when ``history`` has fewer than three values or zero standard deviation.
    """
    if len(history) < MIN_ZSCORE_HISTORY:
        return 0.0

    values = np.asarray(history, dtype=np.float64)
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    if std <= 0.0:
        return 0.0
    return float((latest - mean) / std)


def compute_isolation_score(history: list[float]) -> float:
    """
    Fit IsolationForest on area history and score the latest value.

    Returns the negated ``decision_function`` output for the most recent point so that
    larger values indicate stronger anomalies. Returns 0.0 when fewer than six values
    are available.
    """
    if len(history) < MIN_ISOLATION_HISTORY:
        return 0.0

    values = np.asarray(history, dtype=np.float64).reshape(-1, 1)
    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(values)

    latest = values[-1:]
    decision = float(model.decision_function(latest)[0])
    return float(-decision)


def determine_severity(z_score: float, isolation_score: float) -> str:
    """
    Map Z-score and isolation score to a severity label.

    Returns one of ``none``, ``watch``, ``warning``, or ``emergency``.
    """
    if z_score > 5.0 or isolation_score > 0.3:
        return "emergency"
    if z_score > 3.5 or isolation_score > 0.2:
        return "warning"
    if z_score > 2.5 or isolation_score > 0.1:
        return "watch"
    return "none"


def _tail_history(values: list[float], limit: int = HISTORY_LIMIT) -> list[float]:
    """Return the last ``limit`` values from a chronological series."""
    if len(values) <= limit:
        return list(values)
    return list(values[-limit:])


def _build_contributing_factors(
    z_score: float,
    latest_area: float,
    mean_area: float,
    turbidity_history: list[float],
    ndwi_history: list[float],
) -> list[str]:
    """Build human-readable anomaly factor descriptions."""
    factors: list[str] = []

    if z_score > 2.5:
        delta = latest_area - mean_area
        factors.append(
            f"Rapid area growth: {delta:+.2f} km² vs historical mean"
        )

    if len(turbidity_history) >= MIN_ZSCORE_HISTORY:
        turbidity = np.asarray(turbidity_history, dtype=np.float64)
        latest_turbidity = float(turbidity[-1])
        mean_turbidity = float(turbidity[:-1].mean())
        std_turbidity = float(turbidity[:-1].std(ddof=1)) if len(turbidity) > 2 else 0.0
        if std_turbidity > 0.0 and latest_turbidity > mean_turbidity + 2.0 * std_turbidity:
            factors.append("Turbidity spike detected")

    if len(ndwi_history) >= MIN_ZSCORE_HISTORY:
        ndwi = np.asarray(ndwi_history, dtype=np.float64)
        latest_ndwi = float(ndwi[-1])
        mean_ndwi = float(ndwi[:-1].mean())
        std_ndwi = float(ndwi[:-1].std(ddof=1)) if len(ndwi) > 2 else 0.0
        if std_ndwi > 0.0 and latest_ndwi > mean_ndwi + 1.0 * std_ndwi:
            factors.append("NDWI increase suggests expanding water body")

    return factors


def analyze_lake(
    lake_id: str,
    area_history: list[float],
    turbidity_history: list[float],
    ndwi_history: list[float],
) -> LakeAnomalyResult:
    """
    Analyze the last 24 observations and classify lake growth anomaly severity.
    """
    areas = _tail_history(area_history)
    turbidity = _tail_history(turbidity_history)
    ndwi = _tail_history(ndwi_history)

    latest_area = float(areas[-1])
    reference_areas = areas[:-1] if len(areas) > 1 else areas

    mean_area = float(np.mean(reference_areas)) if reference_areas else latest_area
    std_area = (
        float(np.std(reference_areas, ddof=1))
        if len(reference_areas) > 1
        else 0.0
    )

    z_score = compute_z_score(reference_areas, latest_area)
    isolation_score = compute_isolation_score(areas)
    severity = determine_severity(z_score, isolation_score)

    contributing_factors = _build_contributing_factors(
        z_score,
        latest_area,
        mean_area,
        turbidity,
        ndwi,
    )

    result = LakeAnomalyResult(
        lake_id=lake_id,
        latest_area_km2=latest_area,
        mean_area_km2=mean_area,
        std_area_km2=std_area,
        z_score=z_score,
        isolation_score=isolation_score,
        is_anomaly=severity != "none",
        severity=severity,
        contributing_factors=contributing_factors,
    )

    logger.info(
        "Lake %s anomaly analysis: severity=%s z_score=%.3f isolation=%.3f",
        lake_id,
        severity,
        z_score,
        isolation_score,
    )
    return result


def _sync_database_url(database_url: str) -> str:
    """Convert async SQLAlchemy URLs to psycopg2-compatible URLs."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def fetch_and_analyze(
    lake_id: str,
    database_url: str,
) -> Optional[LakeAnomalyResult]:
    """
    Load recent observations from the database and run anomaly analysis.

    Returns None when fewer than three observations exist for the lake.
    """
    try:
        conn = psycopg2.connect(_sync_database_url(database_url))
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT area_km2, turbidity_index, ndwi_mean
                    FROM lake_observations
                    WHERE lake_id = %s
                      AND area_km2 IS NOT NULL
                    ORDER BY observed_at ASC
                    LIMIT %s
                    """,
                    (lake_id, HISTORY_LIMIT),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        if len(rows) < MIN_ZSCORE_HISTORY:
            logger.info(
                "Lake %s has %d observations; need at least %d for analysis",
                lake_id,
                len(rows),
                MIN_ZSCORE_HISTORY,
            )
            return None

        area_history = [float(row["area_km2"]) for row in rows]
        turbidity_history = [
            float(row["turbidity_index"])
            if row["turbidity_index"] is not None
            else 0.0
            for row in rows
        ]
        ndwi_history = [
            float(row["ndwi_mean"]) if row["ndwi_mean"] is not None else 0.0
            for row in rows
        ]

        return analyze_lake(lake_id, area_history, turbidity_history, ndwi_history)
    except Exception:
        logger.exception("Failed to fetch and analyze lake %s", lake_id)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    rng = np.random.default_rng(42)
    area_history = list(rng.normal(1.0, 0.05, 20))
    area_history[-1] = 3.5
    turbidity_history = [0.5] * 20
    ndwi_history = [0.3] * 20

    result = analyze_lake(
        lake_id="test-lake",
        area_history=area_history,
        turbidity_history=turbidity_history,
        ndwi_history=ndwi_history,
    )

    print(f"severity: {result.severity}")
    print(f"z_score: {result.z_score:.3f}")
    print(f"isolation_score: {result.isolation_score:.3f}")
    print(f"factors: {result.contributing_factors}")

    assert result.severity == "emergency", (
        f"Expected emergency severity, got {result.severity}"
    )
    print("Anomaly scorer self-test passed")
