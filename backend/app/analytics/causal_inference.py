"""
Causal Inference Module for Climate Impacts.

Moves beyond simple correlation to estimate the causal impact (Average Treatment Effect)
of climate shocks on crop yields, controlling for confounding variables like district area
and historical yield trends.

Methodology:
- Treatment (T): Presence of a climate shock (1) or absence (0).
- Outcome (Y): Crop yield deviation.
- Confounders (W): Historical yield trend, district crop area.
- Estimator: Ordinary Least Squares (OLS) with covariates.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

try:
    from scipy import stats as scipy_stats

    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


@dataclass
class CausalImpactResult:
    """The estimated causal impact of a climate shock on yield."""

    shock_type: str
    target_crop: str
    average_treatment_effect: float  # Estimated absolute yield loss in kg/ha
    ate_percentage: float  # % loss relative to baseline
    p_value: float
    is_significant: bool
    confidence_interval_lower: float
    confidence_interval_upper: float
    sample_size: int
    treated_count: int
    control_count: int


class CausalInferenceEngine:
    """
    Estimates causal impacts of climate anomalies using robust regression controlling
    for potential confounders.
    """

    def __init__(self, significance_alpha: float = 0.05):
        self.alpha = significance_alpha

    def estimate_shock_impact(
        self,
        crop: str,
        shock_type: str,
        yields: list[float],
        treatments: list[int],
        covariates: list[list[float]],
    ) -> CausalImpactResult | None:
        """
        Estimate the Average Treatment Effect (ATE) of a shock.

        Args:
            crop: The crop being analyzed.
            shock_type: The type of climate shock (e.g., "drought", "flood").
            yields: List of crop yields (the Outcome Y).
            treatments: List of binary indicators 1 (shock) or 0 (no shock).
            covariates: Matrix of confounding variables (e.g., [trend, area]).

        Returns:
            CausalImpactResult or None if insufficient data.
        """
        if not SCIPY_OK:
            logger.warning("SciPy is required for causal inference.")
            return None

        n = len(yields)
        treated = sum(treatments)
        control = n - treated

        # Need sufficient data in both treatment and control groups
        if n < 10 or treated < 2 or control < 2:
            logger.info(
                f"Insufficient data for causal inference on {shock_type}. N={n}, Treated={treated}, Control={control}"
            )
            return None

        Y = np.array(yields, dtype=float)
        T = np.array(treatments, dtype=float)
        W = np.array(covariates, dtype=float) if covariates else np.zeros((n, 0))

        # Build design matrix X: [Intercept, Treatment, Covariate1, ...]
        X = np.column_stack((np.ones(n), T, W))

        # OLS estimation: beta = (X^T X)^-1 X^T Y
        try:
            # Add small ridge penalty to prevent singular matrix
            ridge_penalty = 1e-8 * np.eye(X.shape[1])
            ridge_penalty[0, 0] = 0  # Don't penalize intercept

            XtX_inv = np.linalg.inv(X.T @ X + ridge_penalty)
            beta = XtX_inv @ X.T @ Y

            # The treatment effect is the coefficient on T (index 1)
            ate = float(beta[1])

            # Calculate standard errors and p-values
            residuals = Y - (X @ beta)
            sigma_sq = np.sum(residuals**2) / (n - X.shape[1])
            var_beta = sigma_sq * np.diag(XtX_inv)
            se_ate = np.sqrt(var_beta[1])

            # t-statistic and p-value
            t_stat = ate / se_ate if se_ate > 0 else 0
            df = n - X.shape[1]
            p_val = float(2 * (1 - scipy_stats.t.cdf(abs(t_stat), df)))

            # 95% Confidence Interval
            t_crit = scipy_stats.t.ppf(1 - self.alpha / 2, df)
            ci_lower = float(ate - t_crit * se_ate)
            ci_upper = float(ate + t_crit * se_ate)

            # Baseline yield (intercept + mean of covariates)
            baseline = float(beta[0])
            if W.shape[1] > 0:
                baseline += float(np.sum(beta[2:] * np.mean(W, axis=0)))

            ate_pct = (ate / baseline * 100) if baseline > 0 else 0.0

            return CausalImpactResult(
                shock_type=shock_type,
                target_crop=crop,
                average_treatment_effect=round(ate, 2),
                ate_percentage=round(ate_pct, 2),
                p_value=round(p_val, 4),
                is_significant=p_val < self.alpha,
                confidence_interval_lower=round(ci_lower, 2),
                confidence_interval_upper=round(ci_upper, 2),
                sample_size=n,
                treated_count=treated,
                control_count=control,
            )

        except np.linalg.LinAlgError:
            logger.error("Linear algebra error during OLS estimation (singular matrix).")
            return None
        except Exception as e:
            logger.error(f"Error in causal inference: {e}")
            return None
