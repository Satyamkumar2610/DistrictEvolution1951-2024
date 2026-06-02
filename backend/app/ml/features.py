"""
Feature Aggregation Module for Yield Prediction.
Calculates historical temporal features (lags, moving averages) and
spatial climate anomalies strictly from available dataset features.
"""

from typing import Any

import numpy as np
import pandas as pd


class FeatureAggregator:
    """
    Computes advanced agronomic, temporal, and spatial features
    for yield prediction without synthetic weather approximations.
    """

    @staticmethod
    def enrich_panel_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a panel DataFrame (must contain 'cdk', 'year', 'yield_value')
        and computes lags, rolling averages, and climate anomalies per district.
        """
        if df.empty or "cdk" not in df.columns or "year" not in df.columns:
            return df

        df = df.sort_values(by=["cdk", "year"]).copy()

        # Temporal Yield Lags
        if "yield_value" in df.columns:
            df["yield_lag_1"] = df.groupby("cdk")["yield_value"].shift(1)
            df["yield_lag_2"] = df.groupby("cdk")["yield_value"].shift(2)

            # 3-Year Moving Average (excluding current year to prevent data leakage)
            df["yield_ma_3"] = df.groupby("cdk")["yield_lag_1"].transform(
                lambda x: x.rolling(window=3, min_periods=1).mean()
            )

        # Climate Anomalies (deviation from district historical mean)
        if "rainfall" in df.columns:
            district_mean_rain = df.groupby("cdk")["rainfall"].transform("mean")
            district_std_rain = df.groupby("cdk")["rainfall"].transform("std").replace(0, 1)
            df["rainfall_anomaly"] = (df["rainfall"] - district_mean_rain) / district_std_rain

        if "temperature" in df.columns:
            district_mean_temp = df.groupby("cdk")["temperature"].transform("mean")
            district_std_temp = df.groupby("cdk")["temperature"].transform("std").replace(0, 1)
            df["temp_anomaly"] = (df["temperature"] - district_mean_temp) / district_std_temp

        if "soil_moisture" in df.columns:
            district_mean_soil = df.groupby("cdk")["soil_moisture"].transform("mean")
            district_std_soil = df.groupby("cdk")["soil_moisture"].transform("std").replace(0, 1)
            df["soil_moisture_anomaly"] = (df["soil_moisture"] - district_mean_soil) / district_std_soil

        # Fill NaNs created by shifts with 0 or a sensible default
        df.fillna(0, inplace=True)

        return df

    @staticmethod
    def compute_ndvi_anomalies(ndvi_records: list[dict[str, Any]]) -> dict[int, float]:
        """
        Takes historical NDVI records for a district and computes the standardized anomaly for each year.
        Input format: [{'year': int, 'mean_ndvi': float}, ...]
        Returns: {year: anomaly_value}
        """
        if not ndvi_records:
            return {}

        years = [int(r["year"]) for r in ndvi_records]
        values = np.array([float(r["mean_ndvi"]) for r in ndvi_records])

        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val == 0:
            std_val = 1.0

        anomalies = (values - mean_val) / std_val
        return dict(zip(years, anomalies, strict=False))
