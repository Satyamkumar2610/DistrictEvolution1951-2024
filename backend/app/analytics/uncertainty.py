"""
Uncertainty Quantification: Bootstrap confidence intervals and error propagation.
"""

import math
import random

from app.config import get_settings
from app.schemas.common import UncertaintyBounds

settings = get_settings()


def calculate_bootstrap_ci(
    values: list[float],
    n_iterations: int | None = None,
    confidence: float | None = None,
    statistic: str = "mean",
) -> UncertaintyBounds:
    """
    Calculate bootstrap confidence interval for a statistic.

    Args:
        values: Sample values
        n_iterations: Number of bootstrap iterations
        confidence: Confidence level (0-1)
        statistic: Which statistic to bootstrap ("mean", "median")

    Returns:
        UncertaintyBounds with lower, upper, method, confidence
    """
    n_iterations = n_iterations or settings.bootstrap_iterations
    confidence = confidence or settings.confidence_level

    if len(values) < 2:
        point_est = values[0] if values else 0
        return UncertaintyBounds(
            lower=point_est,
            upper=point_est,
            method="insufficient_data",
            confidence=confidence,
        )

    # Seed RNG deterministically for reproducible results
    rng = random.Random(hash(tuple(round(v, 6) for v in values)))

    # Generate bootstrap samples
    bootstrap_stats = []
    n = len(values)

    for _ in range(n_iterations):
        # Sample with replacement
        sample = [rng.choice(values) for _ in range(n)]

        if statistic == "mean":
            stat = sum(sample) / len(sample)
        elif statistic == "median":
            sorted_sample = sorted(sample)
            mid = len(sorted_sample) // 2
            stat = sorted_sample[mid] if len(sorted_sample) % 2 else (sorted_sample[mid - 1] + sorted_sample[mid]) / 2
        else:
            stat = sum(sample) / len(sample)

        bootstrap_stats.append(stat)

    # Calculate percentiles
    alpha = 1 - confidence
    bootstrap_stats.sort()

    lower_idx = int(alpha / 2 * n_iterations)
    upper_idx = int((1 - alpha / 2) * n_iterations)

    return UncertaintyBounds(
        lower=bootstrap_stats[lower_idx],
        upper=bootstrap_stats[upper_idx - 1],
        method=f"bootstrap_{int(confidence * 100)}",
        confidence=confidence,
    )


def calculate_impact_uncertainty(
    pre_values: list[float],
    post_values: list[float],
    n_iterations: int | None = None,
    confidence: float | None = None,
) -> UncertaintyBounds:
    """
    Calculate confidence interval for the difference in means.

    Uses bootstrap to estimate uncertainty in the impact calculation.

    Args:
        pre_values: Pre-split period values
        post_values: Post-split period values
        n_iterations: Bootstrap iterations
        confidence: Confidence level

    Returns:
        UncertaintyBounds for the difference (post_mean - pre_mean)
    """
    n_iterations = n_iterations or settings.bootstrap_iterations
    confidence = confidence or settings.confidence_level

    if len(pre_values) < 2 or len(post_values) < 2:
        # Point estimate only
        pre_mean = sum(pre_values) / len(pre_values) if pre_values else 0
        post_mean = sum(post_values) / len(post_values) if post_values else 0
        diff = post_mean - pre_mean
        return UncertaintyBounds(
            lower=diff,
            upper=diff,
            method="insufficient_data",
            confidence=confidence,
        )

    # Seed RNG deterministically for reproducible results
    seed_data = tuple(round(v, 6) for v in pre_values) + tuple(round(v, 6) for v in post_values)
    rng = random.Random(hash(seed_data))

    # Bootstrap the difference
    differences = []

    for _ in range(n_iterations):
        # Resample both periods
        pre_sample = [rng.choice(pre_values) for _ in range(len(pre_values))]
        post_sample = [rng.choice(post_values) for _ in range(len(post_values))]

        pre_mean = sum(pre_sample) / len(pre_sample)
        post_mean = sum(post_sample) / len(post_sample)

        differences.append(post_mean - pre_mean)

    # Calculate percentiles
    alpha = 1 - confidence
    differences.sort()

    lower_idx = int(alpha / 2 * n_iterations)
    upper_idx = int((1 - alpha / 2) * n_iterations)

    return UncertaintyBounds(
        lower=differences[lower_idx],
        upper=differences[upper_idx - 1],
        method=f"bootstrap_diff_{int(confidence * 100)}",
        confidence=confidence,
    )


def propagate_harmonization_error(
    coverage_ratios: dict,
    child_uncertainties: dict,
) -> float:
    """
    Propagate uncertainty from child districts to harmonized parent.

    Uses variance propagation formula for weighted sums.

    Args:
        coverage_ratios: Dict[cdk] -> area weight
        child_uncertainties: Dict[cdk] -> variance or uncertainty

    Returns:
        Propagated uncertainty (standard error)
    """
    if not coverage_ratios or not child_uncertainties:
        return 0.0

    total_variance = 0.0

    for cdk, weight in coverage_ratios.items():
        child_var = child_uncertainties.get(cdk, 0)
        # Variance of weighted sum: Var(w*X) = w^2 * Var(X)
        total_variance += (weight**2) * child_var

    return math.sqrt(total_variance)
