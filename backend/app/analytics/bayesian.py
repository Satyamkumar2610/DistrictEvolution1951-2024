"""
Bayesian Hierarchical Model for Short-series Fallback.
Provides calibrated uncertainty bounds and robust trend estimation
for agricultural districts with < 10 years of data.
"""

import logging
from typing import Any

try:
    import arviz as az
    import numpy as np
    import pymc as pm
    PYMC_AVAILABLE = True
except ImportError:
    PYMC_AVAILABLE = False
    logging.warning("PyMC is not installed. Bayesian state-space models will fallback to linear.")

def bayesian_short_series_forecast(
    years: list[int],
    values: list[float],
    forecast_horizon: int = 5,
    regional_mean_trend: float = 0.0,
    regional_trend_std: float = 0.1
) -> dict[str, Any]:
    """
    Fit a Bayesian hierarchical state-space trend model using PyMC.
    Borrows strength from neighboring districts via `regional_mean_trend` prior.

    Args:
        years: List of observation years.
        values: Corresponding observed agricultural metrics.
        forecast_horizon: Number of years to project forward.
        regional_mean_trend: Prior mean for the temporal slope (borrowed from state/neighbors).
        regional_trend_std: Prior uncertainty for the slope.

    Returns:
        Dictionary containing forecast means and 90% HDI bounds.
    """
    if not PYMC_AVAILABLE or len(values) < 3:
        # Graceful fallback if PyMC fails or too little data to even compile
        return _linear_fallback(years, values, forecast_horizon)

    try:
        # Normalize years to start at t=0
        t = np.array(years)
        t_normalized = t - t[0]
        y = np.array(values)

        with pm.Model():
            # Priors
            intercept = pm.Normal("intercept", mu=np.mean(y), sigma=np.std(y) * 2)
            slope = pm.Normal("slope", mu=regional_mean_trend, sigma=regional_trend_std)
            sigma = pm.HalfNormal("sigma", sigma=np.std(y))

            # Expected value
            mu = intercept + slope * t_normalized

            # Likelihood
            pm.Normal("obs", mu=mu, sigma=sigma, observed=y)

            # Forecasting (out-of-sample)
            t_future = np.arange(1, forecast_horizon + 1) + t_normalized[-1]
            future_mu = intercept + slope * t_future
            pm.Deterministic("forecast_mu", future_mu)

            # Inference
            trace = pm.sample(
                1000,
                tune=1000,
                cores=1,
                progressbar=False,
                return_inferencedata=True,
                compute_convergence_checks=False
            )

        # Extract posterior predictive 90% HDI for forecasts
        forecast_samples = trace.posterior["forecast_mu"].values
        # shape is (chain, draws, time) => reshape to (chain*draws, time)
        forecast_samples = forecast_samples.reshape(-1, forecast_horizon)

        forecast_means = np.mean(forecast_samples, axis=0)
        hdi_bounds = az.hdi(forecast_samples, hdi_prob=0.90)

        future_years = [years[-1] + i for i in range(1, forecast_horizon + 1)]

        forecasts = []
        for i, year in enumerate(future_years):
            forecasts.append({
                "year": year,
                "projected_value": round(float(forecast_means[i]), 4),
                "lower_bound": round(float(hdi_bounds[i][0]), 4),
                "upper_bound": round(float(hdi_bounds[i][1]), 4)
            })

        return {
            "method": "bayesian_state_space",
            "borrowed_regional_strength": True,
            "forecasts": forecasts
        }

    except Exception as e:
        logging.error(f"Bayesian modeling failed: {e}. Falling back to linear.")
        return _linear_fallback(years, values, forecast_horizon)

def _linear_fallback(years: list[int], values: list[float], horizon: int) -> dict[str, Any]:
    """Simple linear extrapolation fallback."""
    from app.analytics.statistics import get_analyzer
    stats = get_analyzer()
    trend = stats.linear_trend(values)

    last_year = years[-1] if years else 0
    last_val = values[-1] if values else 0.0

    forecasts = []
    slope = trend.slope if trend.significant else 0.0

    for i in range(1, horizon + 1):
        future_year = last_year + i
        projected = last_val + (slope * i)

        # Simple ±10% dummy bounds for the linear fallback
        forecasts.append({
            "year": future_year,
            "projected_value": round(projected, 4),
            "lower_bound": round(projected * 0.9, 4),
            "upper_bound": round(projected * 1.1, 4)
        })

    return {
        "method": "linear_extrapolation",
        "borrowed_regional_strength": False,
        "forecasts": forecasts
    }
