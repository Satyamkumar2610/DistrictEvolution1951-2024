"""
Stochastic Frontier Analysis (SFA) for Yield Gap / Frontier estimation.

Replaces the static P95 percentile approach with a proper econometric
frontier model that defines true technical inefficiency boundaries.

Model:
    ln(y_i) = X_i·β + v_i − u_i

Where:
    y_i  = observed yield for district i
    X_i  = input vector (rainfall, NPK, irrigation %, soil quality)
    v_i  ~ N(0, σ²_v)  — symmetric noise (weather shocks, measurement error)
    u_i  ~ |N(0, σ²_u)| — one-sided inefficiency term (≥ 0)

The frontier ŷ* = exp(X_i·β + v_i) represents what a fully-efficient
district *would* produce given the same inputs. The technical efficiency
TE_i = exp(-u_i) ∈ (0, 1].
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    from scipy.optimize import minimize
    from scipy.stats import norm

    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SFADistrictResult:
    """SFA result for a single district."""

    cdk: str
    name: str | None
    observed_yield: float
    frontier_yield: float  # what a fully-efficient district would produce
    technical_efficiency: float  # TE ∈ (0, 1] — 1.0 = on the frontier
    inefficiency_score: float  # u_i estimate
    yield_gap_kg_ha: float  # frontier - observed
    yield_gap_pct: float  # gap as % of frontier
    efficiency_rank: int


@dataclass
class SFAModelStats:
    """Global model statistics."""

    n_districts: int
    sigma_v: float  # noise std
    sigma_u: float  # inefficiency std
    lambda_ratio: float  # σ_u / σ_v — higher = more inefficiency dominance
    gamma: float  # σ²_u / (σ²_u + σ²_v) — proportion of variance from inefficiency
    log_likelihood: float
    mean_te: float  # average technical efficiency across districts
    features_used: list[str]


@dataclass
class SFAReport:
    """Complete Stochastic Frontier Analysis report."""

    crop: str
    year: int | None
    model_stats: SFAModelStats
    district_results: list[SFADistrictResult]
    frontier_interpretation: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core SFA Engine
# ---------------------------------------------------------------------------


class StochasticFrontierAnalyzer:
    """
    Estimates production frontier using Maximum Likelihood Estimation (MLE)
    of the composed error model (Aigner, Lovell & Schmidt, 1977).
    """

    def analyze(
        self,
        district_data: list[dict[str, Any]],
        yield_key: str = "yield",
        feature_keys: list[str] | None = None,
        crop: str = "",
        year: int | None = None,
    ) -> SFAReport | None:
        """
        Run SFA on cross-sectional district data.

        Args:
            district_data: List of dicts, each with 'cdk', 'name', yield_key,
                and optional feature columns.
            yield_key: Key for the yield variable.
            feature_keys: Input variable keys (rainfall, npk, irrigation_pct, etc.).
            crop: Crop name for labeling.
            year: Observation year.

        Returns:
            SFAReport or None if insufficient data.
        """
        warnings_list: list[str] = []

        # Filter valid data
        valid = [d for d in district_data if d.get(yield_key, 0) > 0]
        if len(valid) < 10:
            return None

        n = len(valid)
        y = np.array([d[yield_key] for d in valid], dtype=float)
        ln_y = np.log(y)

        if not SCIPY_OK:
            warnings_list.append("SciPy unavailable — using quantile frontier fallback.")
            return self._fallback_frontier_report(valid, y, crop, year, warnings_list)

        # Build feature matrix (or intercept-only)
        if feature_keys:
            X = np.column_stack([np.array([d.get(k, 0.0) for d in valid], dtype=float) for k in feature_keys])
            # Log-transform positive features for Cobb-Douglas form
            X = np.log(np.maximum(X, 1e-6))
            # Add intercept
            X = np.column_stack([np.ones(n), X])
            used_features = ["intercept"] + feature_keys
        else:
            X = np.ones((n, 1))
            used_features = ["intercept"]
            warnings_list.append("No input features provided — intercept-only model.")

        k = X.shape[1]  # number of parameters

        # ----- MLE Estimation -----
        result = self._fit_mle(ln_y, X, k)
        if result is None:
            warnings_list.append("MLE optimization failed — using fallback estimates.")
            result = self._fallback_estimates(ln_y, X, k)

        beta, sigma_v, sigma_u = result

        # ----- Compute per-district results -----
        epsilon = ln_y - X @ beta  # composed error = v_i - u_i
        sigma_sq = sigma_v**2 + sigma_u**2
        sigma = np.sqrt(sigma_sq)
        lam = sigma_u / sigma_v if sigma_v > 1e-8 else 1.0

        # Conditional expectation of u_i given epsilon_i (JLMS estimator)
        mu_star = -epsilon * sigma_u**2 / sigma_sq
        sigma_star = sigma_u * sigma_v / sigma

        # E[u_i | epsilon_i]
        ratio = mu_star / sigma_star
        phi_ratio = norm.pdf(ratio)
        Phi_ratio = norm.cdf(ratio)
        Phi_ratio = np.maximum(Phi_ratio, 1e-10)  # prevent division by zero

        u_hat = mu_star + sigma_star * (phi_ratio / Phi_ratio)
        te = np.exp(-u_hat)  # technical efficiency

        # Frontier yield = observed / TE
        frontier_yields = y / te

        gamma = sigma_u**2 / sigma_sq if sigma_sq > 1e-8 else 0.0

        # Log-likelihood
        ll = self._log_likelihood(ln_y, X, beta, sigma_v, sigma_u)

        # Build district results
        district_results = []
        for i, d in enumerate(valid):
            district_results.append(
                SFADistrictResult(
                    cdk=d.get("cdk", f"d_{i}"),
                    name=d.get("name"),
                    observed_yield=round(float(y[i]), 1),
                    frontier_yield=round(float(frontier_yields[i]), 1),
                    technical_efficiency=round(float(te[i]), 4),
                    inefficiency_score=round(float(u_hat[i]), 4),
                    yield_gap_kg_ha=round(float(frontier_yields[i] - y[i]), 1),
                    yield_gap_pct=round(float((1 - te[i]) * 100), 1),
                    efficiency_rank=0,  # filled below
                )
            )

        # Rank by TE descending
        district_results.sort(key=lambda x: x.technical_efficiency, reverse=True)
        for i, dr in enumerate(district_results):
            dr.efficiency_rank = i + 1

        mean_te = float(np.mean(te))

        # Interpretation
        if gamma > 0.7:
            interp = (
                f"Inefficiency dominates ({gamma:.0%} of variance). "
                f"Average TE is {mean_te:.1%} — significant room for improvement "
                f"through technology adoption and practice upgrades."
            )
        elif gamma > 0.3:
            interp = (
                f"Mixed variance ({gamma:.0%} from inefficiency). "
                f"Average TE is {mean_te:.1%} — moderate scope for frontier convergence."
            )
        else:
            interp = (
                f"Noise dominates ({1 - gamma:.0%} of variance). "
                f"Average TE is {mean_te:.1%} — most districts are near-efficient; "
                f"yield differences are largely explained by external shocks."
            )

        return SFAReport(
            crop=crop,
            year=year,
            model_stats=SFAModelStats(
                n_districts=n,
                sigma_v=round(float(sigma_v), 4),
                sigma_u=round(float(sigma_u), 4),
                lambda_ratio=round(float(lam), 4),
                gamma=round(float(gamma), 4),
                log_likelihood=round(float(ll), 2),
                mean_te=round(mean_te, 4),
                features_used=used_features,
            ),
            district_results=district_results,
            frontier_interpretation=interp,
            warnings=warnings_list,
        )

    def _fallback_frontier_report(
        self,
        valid: list[dict[str, Any]],
        y: np.ndarray,
        crop: str,
        year: int | None,
        warnings_list: list[str],
    ) -> SFAReport:
        """
        Non-parametric fallback when SciPy isn't available.

        Uses the max of observed p95 and max yield as the frontier, then
        computes technical efficiency as observed/frontier.
        """
        n = len(valid)
        frontier = float(max(np.percentile(y, 95), np.max(y)))
        frontier = max(frontier, 1e-6)

        te = np.clip(y / frontier, 1e-6, 1.0)
        u_hat = -np.log(te)
        frontier_yields = np.full_like(y, frontier, dtype=float)

        district_results: list[SFADistrictResult] = []
        for i, d in enumerate(valid):
            district_results.append(
                SFADistrictResult(
                    cdk=d.get("cdk", f"d_{i}"),
                    name=d.get("name"),
                    observed_yield=round(float(y[i]), 1),
                    frontier_yield=round(float(frontier_yields[i]), 1),
                    technical_efficiency=round(float(te[i]), 4),
                    inefficiency_score=round(float(u_hat[i]), 4),
                    yield_gap_kg_ha=round(float(frontier_yields[i] - y[i]), 1),
                    yield_gap_pct=round(float((1 - te[i]) * 100), 1),
                    efficiency_rank=0,
                )
            )

        district_results.sort(key=lambda x: x.technical_efficiency, reverse=True)
        for i, dr in enumerate(district_results):
            dr.efficiency_rank = i + 1

        mean_te = float(np.mean(te))
        residual = frontier_yields - y
        sigma = max(float(np.std(residual)), 1e-6)

        return SFAReport(
            crop=crop,
            year=year,
            model_stats=SFAModelStats(
                n_districts=n,
                sigma_v=round(sigma, 4),
                sigma_u=round(sigma, 4),
                lambda_ratio=1.0,
                gamma=0.5,
                log_likelihood=0.0,
                mean_te=round(mean_te, 4),
                features_used=["intercept"],
            ),
            district_results=district_results,
            frontier_interpretation=(
                f"Approximate quantile frontier used (p95={frontier:.1f} kg/ha). Average TE is {mean_te:.1%}."
            ),
            warnings=warnings_list,
        )

    # ------------------------------------------------------------------
    # MLE internals
    # ------------------------------------------------------------------
    def _fit_mle(self, ln_y: np.ndarray, X: np.ndarray, k: int) -> tuple[np.ndarray, float, float] | None:
        """Maximize the normal/half-normal composed error log-likelihood."""
        try:
            # Initial OLS estimates
            beta_ols = np.linalg.lstsq(X, ln_y, rcond=None)[0]
            resid = ln_y - X @ beta_ols
            sigma_init = float(np.std(resid))

            # Pack: [beta_0, ..., beta_k, ln(sigma_v), ln(sigma_u)]
            x0 = np.concatenate([beta_ols, [np.log(sigma_init * 0.7), np.log(sigma_init * 0.7)]])

            def neg_ll(params):
                beta = params[:k]
                sv = np.exp(params[k])
                su = np.exp(params[k + 1])
                return -self._log_likelihood(ln_y, X, beta, sv, su)

            res = minimize(neg_ll, x0, method="Nelder-Mead", options={"maxiter": 5000})

            if res.success or res.fun < 1e15:
                beta = res.x[:k]
                sigma_v = np.exp(res.x[k])
                sigma_u = np.exp(res.x[k + 1])
                return beta, float(sigma_v), float(sigma_u)

            return None
        except Exception as e:
            logger.warning(f"SFA MLE failed: {e}")
            return None

    def _fallback_estimates(self, ln_y: np.ndarray, X: np.ndarray, k: int) -> tuple[np.ndarray, float, float]:
        """OLS-based fallback when MLE doesn't converge."""
        beta = np.linalg.lstsq(X, ln_y, rcond=None)[0]
        resid = ln_y - X @ beta
        sigma = float(np.std(resid))
        return beta, sigma * 0.7, sigma * 0.7

    @staticmethod
    def _log_likelihood(
        ln_y: np.ndarray,
        X: np.ndarray,
        beta: np.ndarray,
        sigma_v: float,
        sigma_u: float,
    ) -> float:
        """Normal/half-normal composed error log-likelihood."""
        n = len(ln_y)
        epsilon = ln_y - X @ beta
        sigma_sq = sigma_v**2 + sigma_u**2
        sigma = np.sqrt(sigma_sq)
        lam = sigma_u / sigma_v if sigma_v > 1e-8 else 1.0

        ll = (
            -n / 2 * np.log(2 * np.pi)
            - n * np.log(sigma)
            + np.sum(np.log(2 * norm.cdf(-epsilon * lam / sigma)))
            - np.sum(epsilon**2) / (2 * sigma_sq)
        )
        return float(ll)
