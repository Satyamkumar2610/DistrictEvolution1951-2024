"""
Spatio-Temporal Panel Model using XGBoost.
Trains across multiple districts simultaneously to learn complex,
non-linear responses to climate shocks.
"""

import logging

import numpy as np
import pandas as pd

try:
    import xgboost as xgb
    from sklearn.metrics import r2_score
    from sklearn.model_selection import TimeSeriesSplit

    XGB_AVAILABLE = True
except Exception as e:
    XGB_AVAILABLE = False
    logging.warning(f"xgboost or scikit-learn is not available ({e}). PanelForecaster will not work.")

logger = logging.getLogger(__name__)


class PanelForecaster:
    """
    XGBoost-based forecaster utilizing Spatio-Temporal Panel data.
    """

    def __init__(self) -> None:
        if not XGB_AVAILABLE:
            raise ImportError("XGBoost or Scikit-Learn not installed.")

        self.model = xgb.XGBRegressor(
            n_estimators=100, learning_rate=0.05, max_depth=5, subsample=0.8, colsample_bytree=0.8, random_state=42
        )

        self.features = [
            "yield_lag_1",
            "yield_lag_2",
            "yield_ma_3",
            "rainfall",
            "temperature",
            "soil_moisture",
            "rainfall_anomaly",
            "temp_anomaly",
            "soil_moisture_anomaly",
            "crop_area",
        ]

        self.cv_scores: list[float] = []
        self.feature_importances: dict[str, float] = {}
        self._is_fitted = False

    def fit(self, df: pd.DataFrame) -> None:
        """
        Fits the XGBoost model using TimeSeriesSplit to prevent data leakage.
        """
        if df.empty:
            raise ValueError("Empty dataframe provided for training.")

        # Ensure df is sorted chronologically for TimeSeriesSplit
        df = df.sort_values("year").copy()

        # Drop rows with NaN in target or essential features
        df = df.dropna(subset=["yield_value"] + self.features)

        if len(df) < 20:
            logger.warning("Very small dataset for panel modeling. Results may be unreliable.")

        X = df[self.features]
        y = df["yield_value"]

        # TimeSeriesSplit cross-validation
        # We split by index (which is sorted by year), ensuring training is always on past data
        n_splits = min(3, max(2, len(df) // 20))
        tscv = TimeSeriesSplit(n_splits=n_splits)
        scores = []

        for train_index, test_index in tscv.split(X):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

            self.model.fit(X_train, y_train)
            preds = self.model.predict(X_test)
            r2 = r2_score(y_test, preds)
            scores.append(r2)

        # Refit on all data for production use
        self.model.fit(X, y)
        self.cv_scores = scores

        # Map feature importances
        importance_vals = self.model.feature_importances_
        self.feature_importances = {feat: float(imp) for feat, imp in zip(self.features, importance_vals, strict=False)}
        self._is_fitted = True
        logger.info(f"Panel model fitted. CV R2 scores: {scores}")

    def predict(self, df_target: pd.DataFrame) -> np.ndarray:
        """
        Predicts yield for the target features.
        """
        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before calling predict.")

        df_target = df_target.copy()

        # Ensure all features exist, filling missing ones with 0.0
        for f in self.features:
            if f not in df_target.columns:
                df_target[f] = 0.0

        X_test = df_target[self.features]
        # XGBoost predict returns a numpy array
        return self.model.predict(X_test)
