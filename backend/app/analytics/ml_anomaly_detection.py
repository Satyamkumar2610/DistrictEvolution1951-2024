"""
ML-based Anomaly Detection Module.

Provides two advanced detectors that supplement the rule-based checks in
anomaly_detection.py:

1. **Isolation Forest** — Catches multivariate anomalies by jointly examining
   yield, area, production, rainfall, and input usage. Flags unusual
   *combinations* that simple Z-score thresholds miss.

2. **LSTM Autoencoder** — Detects complex temporal deviations by learning
   a compressed representation of "normal" district time-series behaviour.
   Years that reconstruct poorly are flagged as temporally anomalous.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

try:
    import tensorflow as tf  # noqa: F401
    TF_OK = True
except ImportError:
    TF_OK = False
    logger.info("TensorFlow not installed — LSTM autoencoder detector unavailable.")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MLAnomaly:
    """An anomaly detected by an ML model."""
    year: int
    anomaly_score: float        # lower = more anomalous for IsoForest, higher recon error for LSTM
    is_anomaly: bool
    method: str                 # "isolation_forest" | "lstm_autoencoder"
    features_used: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class MLAnomalyReport:
    """Combined ML anomaly scan result."""
    cdk: str
    isolation_forest_anomalies: list[MLAnomaly]
    lstm_anomalies: list[MLAnomaly]
    total_ml_anomalies: int


# ---------------------------------------------------------------------------
# 1. Isolation Forest Detector
# ---------------------------------------------------------------------------

class IsolationForestDetector:
    """
    Multivariate anomaly detector using Isolation Forest.

    Input: a matrix of (year × feature) observations for a single district,
    where features might include yield, area, production, rainfall, NPK usage.
    """

    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state

    def detect(
        self,
        yearly_features: dict[int, dict[str, float]],
        feature_names: list[str] | None = None,
    ) -> list[MLAnomaly]:
        """
        Run Isolation Forest on the multi-feature district data.

        Args:
            yearly_features: {year: {feature: value}}
            feature_names: ordered list of features to include.
                           If None, auto-detected from first year.

        Returns:
            List of MLAnomaly for each flagged year.
        """
        if not SKLEARN_OK:
            logger.warning("scikit-learn unavailable — skipping Isolation Forest.")
            return []

        if len(yearly_features) < 6:
            return []

        years = sorted(yearly_features.keys())

        # Resolve feature names
        if feature_names is None:
            feature_names = sorted(
                {k for feats in yearly_features.values() for k in feats}
            )

        if not feature_names:
            return []

        # Build matrix
        X = np.array([
            [yearly_features[yr].get(f, 0.0) for f in feature_names]
            for yr in years
        ])

        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Fit
        model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        preds = model.fit_predict(X_scaled)
        scores = model.decision_function(X_scaled)

        anomalies: list[MLAnomaly] = []
        for i, yr in enumerate(years):
            if preds[i] == -1:  # anomaly
                anomalies.append(MLAnomaly(
                    year=yr,
                    anomaly_score=round(float(scores[i]), 4),
                    is_anomaly=True,
                    method="isolation_forest",
                    features_used=feature_names,
                    details=f"Multivariate outlier detected (score={scores[i]:.3f})",
                ))

        return anomalies


# ---------------------------------------------------------------------------
# 2. LSTM Autoencoder Detector
# ---------------------------------------------------------------------------

class LSTMAutoencoderDetector:
    """
    Temporal anomaly detector using an LSTM Autoencoder.

    The autoencoder learns to reconstruct "normal" sequences of agricultural
    observations. Years where reconstruction error exceeds a threshold are
    flagged as temporally anomalous — indicating deviation from learned patterns.
    """

    def __init__(
        self,
        sequence_length: int = 5,
        latent_dim: int = 8,
        threshold_percentile: float = 95.0,
        epochs: int = 50,
    ):
        self.sequence_length = sequence_length
        self.latent_dim = latent_dim
        self.threshold_percentile = threshold_percentile
        self.epochs = epochs

    def detect(
        self,
        yearly_features: dict[int, dict[str, float]],
        feature_names: list[str] | None = None,
    ) -> list[MLAnomaly]:
        """
        Train LSTM autoencoder and detect temporal anomalies.

        Args:
            yearly_features: {year: {feature: value}}
            feature_names: ordered feature list.

        Returns:
            List of MLAnomaly for flagged years.
        """
        if not TF_OK:
            logger.info("TensorFlow unavailable — skipping LSTM autoencoder.")
            return []

        years = sorted(yearly_features.keys())
        n = len(years)

        if n < self.sequence_length + 3:
            return []

        if feature_names is None:
            feature_names = sorted(
                {k for feats in yearly_features.values() for k in feats}
            )

        if not feature_names:
            return []

        num_features = len(feature_names)

        # Build time-ordered matrix
        data = np.array([
            [yearly_features[yr].get(f, 0.0) for f in feature_names]
            for yr in years
        ])

        # Normalize
        mean = data.mean(axis=0)
        std = data.std(axis=0)
        std[std == 0] = 1.0
        data_norm = (data - mean) / std

        # Create sliding-window sequences
        sequences = []
        seq_year_end = []  # which year ends each sequence
        for i in range(n - self.sequence_length + 1):
            sequences.append(data_norm[i : i + self.sequence_length])
            seq_year_end.append(years[i + self.sequence_length - 1])

        X = np.array(sequences)  # (num_seqs, seq_len, num_features)

        # Build autoencoder
        model = self._build_autoencoder(self.sequence_length, num_features)
        model.fit(X, X, epochs=self.epochs, batch_size=max(1, len(X) // 4), verbose=0)

        # Reconstruction errors
        X_pred = model.predict(X, verbose=0)
        errors = np.mean(np.abs(X - X_pred), axis=(1, 2))  # MAE per sequence

        # Threshold
        threshold = float(np.percentile(errors, self.threshold_percentile))

        anomalies: list[MLAnomaly] = []
        for _i, (err, yr) in enumerate(zip(errors, seq_year_end, strict=False)):
            if err > threshold:
                anomalies.append(MLAnomaly(
                    year=yr,
                    anomaly_score=round(float(err), 4),
                    is_anomaly=True,
                    method="lstm_autoencoder",
                    features_used=feature_names,
                    details=f"Temporal sequence deviation (recon_error={err:.3f}, threshold={threshold:.3f})",
                ))

        return anomalies

    def _build_autoencoder(self, seq_len: int, num_features: int) -> Any:
        """Construct a simple LSTM autoencoder."""
        from tensorflow import keras
        from tensorflow.keras import layers  # type: ignore[attr-defined]

        # Encoder
        inputs = keras.Input(shape=(seq_len, num_features))
        encoded = layers.LSTM(self.latent_dim, activation="relu")(inputs)
        # Decoder
        decoded = layers.RepeatVector(seq_len)(encoded)
        decoded = layers.LSTM(self.latent_dim, activation="relu", return_sequences=True)(decoded)
        outputs = layers.TimeDistributed(layers.Dense(num_features))(decoded)

        model = keras.Model(inputs, outputs)
        model.compile(optimizer="adam", loss="mse")
        return model


# ---------------------------------------------------------------------------
# Combined Scanner
# ---------------------------------------------------------------------------

def run_ml_anomaly_scan(
    cdk: str,
    yearly_features: dict[int, dict[str, float]],
    feature_names: list[str] | None = None,
    use_isolation_forest: bool = True,
    use_lstm: bool = True,
) -> MLAnomalyReport:
    """
    Run all ML-based anomaly detectors on a district's multi-feature time series.

    Args:
        cdk: District identifier.
        yearly_features: {year: {feature_name: value}}.
        feature_names: Feature subset to use.
        use_isolation_forest: Whether to run IsoForest.
        use_lstm: Whether to run LSTM autoencoder.

    Returns:
        MLAnomalyReport combining results from both detectors.
    """
    iso_anomalies: list[MLAnomaly] = []
    lstm_anomalies: list[MLAnomaly] = []

    if use_isolation_forest:
        detector = IsolationForestDetector()
        iso_anomalies = detector.detect(yearly_features, feature_names)

    if use_lstm:
        detector_lstm = LSTMAutoencoderDetector()
        lstm_anomalies = detector_lstm.detect(yearly_features, feature_names)

    return MLAnomalyReport(
        cdk=cdk,
        isolation_forest_anomalies=iso_anomalies,
        lstm_anomalies=lstm_anomalies,
        total_ml_anomalies=len(iso_anomalies) + len(lstm_anomalies),
    )
