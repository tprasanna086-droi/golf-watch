"""
Anomaly detection and alert classification.

Uses scikit-learn IsolationForest to score observations and
rule-based thresholds to classify alert levels.
"""

import numpy as np
from sklearn.ensemble import IsolationForest


FEATURE_KEYS = ["area_delta_pct", "ndwi_delta", "turbidity_delta", "shape_irregularity"]


def fit_isolation_forest(feature_vectors: list[dict]) -> IsolationForest:
    """
    Trains an IsolationForest on a list of feature vector dicts.
    Uses contamination=0.05, n_estimators=100, random_state=42.
    Returns the fitted model.
    """
    X = np.array([[fv[k] for k in FEATURE_KEYS] for fv in feature_vectors])

    model = IsolationForest(
        contamination=0.05,
        n_estimators=100,
        random_state=42,
    )
    model.fit(X)
    return model


def score_observation(model: IsolationForest, feature_vector: dict) -> float:
    """
    Scores a single feature vector.
    Returns anomaly score in [0, 1] where higher = more anomalous.
    Maps IsolationForest decision_function output: score = 1 - (df + 0.5)
    clamped to [0, 1].
    """
    X = np.array([[feature_vector[k] for k in FEATURE_KEYS]])
    df = model.decision_function(X)[0]
    score = 1.0 - (df + 0.5)
    return float(max(0.0, min(1.0, score)))


def classify_alert_level(anomaly_score: float, area_delta_pct: float) -> str | None:
    """
    Returns 'watch', 'warning', or 'emergency' based on:
    - emergency: anomaly_score > 0.8 OR area_delta_pct > 50
    - warning:   anomaly_score > 0.6 OR area_delta_pct > 25
    - watch:     anomaly_score > 0.4 OR area_delta_pct > 10
    - None:      below all thresholds (return None)
    """
    if anomaly_score > 0.8 or area_delta_pct > 50:
        return "emergency"
    if anomaly_score > 0.6 or area_delta_pct > 25:
        return "warning"
    if anomaly_score > 0.4 or area_delta_pct > 10:
        return "watch"
    return None
