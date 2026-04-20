"""
PCA Composite Resilience Score.

Upgrades the 2-variable resilience formula (CV + retention) to an 8-variable
Principal Component Analysis composite that captures a much richer picture
of district agricultural resilience.

Variables:
    1. Yield CV (volatility)
    2. Retention Ratio (P10/Median — drought proxy)
    3. Crop Diversification Index (CDI)
    4. Soil Quality Score (organic carbon proxy)
    5. Yield Depletion Rate (5-year CAGR trend)
    6. Irrigation Coverage (%)
    7. Recovery Speed (avg years to recover from >20% yield drop)
    8. Input Efficiency (yield per unit NPK)

The first 2-3 principal components typically capture 70–85% of variance
and produce a single composite resilience score that is interpretable
through component loadings.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

RESILIENCE_VARIABLES = [
    "yield_cv",
    "retention_ratio",
    "cdi",
    "soil_quality",
    "yield_depletion_rate",
    "irrigation_pct",
    "recovery_speed",
    "input_efficiency",
]


@dataclass
class PCALoadings:
    """PCA component loadings."""
    component: int
    explained_variance_pct: float
    loadings: dict[str, float]  # variable -> loading weight


@dataclass
class DistrictResilience:
    """PCA resilience result for a single district."""
    cdk: str
    name: str | None
    resilience_score: float         # composite PCA score (0-1 rescaled)
    resilience_grade: str           # A/B/C/D/F
    raw_variables: dict[str, float] # the 8 input values
    component_scores: list[float]   # PC1, PC2, PC3 raw scores
    rank: int
    interpretation: str


@dataclass
class PCAResilienceReport:
    """Full PCA resilience analysis for a state/region."""
    region: str
    n_districts: int
    n_components_used: int
    total_variance_explained: float
    loadings: list[PCALoadings]
    district_results: list[DistrictResilience]
    mean_score: float
    variable_contributions: dict[str, float]  # which variables matter most
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class PCAResilienceAnalyzer:
    """
    Computes a composite resilience score using PCA on 8 district-level
    agricultural variables.
    """

    def __init__(self, n_components: int = 3):
        self.n_components = n_components

    def analyze(
        self,
        district_data: list[dict[str, Any]],
        region: str = "",
    ) -> PCAResilienceReport | None:
        """
        Run PCA resilience analysis.

        Args:
            district_data: List of dicts, each with 'cdk', 'name', and
                the 8 RESILIENCE_VARIABLES keys.
            region: Label for the region (state name, etc.)

        Returns:
            PCAResilienceReport or None if insufficient data.
        """
        if not SKLEARN_OK:
            logger.error("scikit-learn required for PCA resilience.")
            return None

        warnings_list: list[str] = []

        # Validate and fill missing
        valid_data: list[dict[str, Any]] = []
        for d in district_data:
            row: dict[str, Any] = {}
            for var in RESILIENCE_VARIABLES:
                val = d.get(var)
                if val is None or not np.isfinite(val):
                    row[var] = 0.0
                else:
                    row[var] = float(val)
            row["cdk"] = d.get("cdk", "unknown")
            row["name"] = d.get("name")
            valid_data.append(row)

        n = len(valid_data)
        if n < 5:
            return None

        # Build matrix
        X = np.array([
            [d[var] for var in RESILIENCE_VARIABLES]
            for d in valid_data
        ])

        # Flip variables where HIGHER is WORSE (so PCA direction is consistent)
        # yield_cv: higher = worse → flip
        # yield_depletion_rate: negative = worse → already correct direction
        # recovery_speed: higher = worse (more years to recover) → flip
        flip_cols = [
            RESILIENCE_VARIABLES.index("yield_cv"),
            RESILIENCE_VARIABLES.index("recovery_speed"),
        ]
        for col in flip_cols:
            X[:, col] = -X[:, col]

        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Handle NaN from zero-variance columns
        X_scaled = np.nan_to_num(X_scaled, nan=0.0)

        # PCA
        n_comp = min(self.n_components, n - 1, len(RESILIENCE_VARIABLES))
        pca = PCA(n_components=n_comp)
        scores = pca.fit_transform(X_scaled)

        # Build loadings
        loadings_list: list[PCALoadings] = []
        for i in range(n_comp):
            loadings_list.append(PCALoadings(
                component=i + 1,
                explained_variance_pct=round(float(pca.explained_variance_ratio_[i] * 100), 2),
                loadings={
                    var: round(float(pca.components_[i, j]), 4)
                    for j, var in enumerate(RESILIENCE_VARIABLES)
                },
            ))

        total_var = float(np.sum(pca.explained_variance_ratio_) * 100)

        # Composite score: weighted sum of PC scores by variance explained
        weights = pca.explained_variance_ratio_[:n_comp]
        composite = scores @ weights

        # Rescale to 0-1
        c_min, c_max = composite.min(), composite.max()
        if c_max - c_min > 1e-8:
            composite_norm = (composite - c_min) / (c_max - c_min)
        else:
            composite_norm = np.full_like(composite, 0.5)

        # Variable contributions (mean absolute loading × variance explained)
        var_contrib: dict[str, float] = {}
        for j, var in enumerate(RESILIENCE_VARIABLES):
            contrib = sum(
                abs(float(pca.components_[i, j])) * float(pca.explained_variance_ratio_[i])
                for i in range(n_comp)
            )
            var_contrib[var] = round(contrib, 4)

        # Build per-district results
        district_results: list[DistrictResilience] = []
        for i, d in enumerate(valid_data):
            score = float(composite_norm[i])
            grade = self._grade(score)
            interp = self._interpret(score, d, var_contrib)

            district_results.append(DistrictResilience(
                cdk=d["cdk"],
                name=d["name"],
                resilience_score=round(score, 4),
                resilience_grade=grade,
                raw_variables={var: d[var] for var in RESILIENCE_VARIABLES},
                component_scores=[round(float(scores[i, c]), 4) for c in range(n_comp)],
                rank=0,
                interpretation=interp,
            ))

        # Rank
        district_results.sort(key=lambda x: x.resilience_score, reverse=True)
        for i, dr in enumerate(district_results):
            dr.rank = i + 1

        mean_score = float(np.mean(composite_norm))

        if total_var < 60:
            warnings_list.append(
                f"Only {total_var:.1f}% variance explained by {n_comp} components — "
                f"results may not capture full resilience picture."
            )

        return PCAResilienceReport(
            region=region,
            n_districts=n,
            n_components_used=n_comp,
            total_variance_explained=round(total_var, 2),
            loadings=loadings_list,
            district_results=district_results,
            mean_score=round(mean_score, 4),
            variable_contributions=var_contrib,
            warnings=warnings_list,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        elif score >= 0.6:
            return "B"
        elif score >= 0.4:
            return "C"
        elif score >= 0.2:
            return "D"
        return "F"

    @staticmethod
    def _interpret(
        score: float,
        data: dict[str, Any],
        contributions: dict[str, float],
    ) -> str:
        """Generate a human-readable interpretation."""
        # Find top 2 contributing variables
        sorted_vars = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        top_vars = [v[0] for v in sorted_vars[:2]]

        if score >= 0.7:
            base = "Highly resilient district"
        elif score >= 0.4:
            base = "Moderately resilient district"
        else:
            base = "Low-resilience district"

        # Find weakness
        weaknesses = []
        if data.get("yield_cv", 0) > 30:
            weaknesses.append("high yield volatility")
        if data.get("retention_ratio", 1) < 0.6:
            weaknesses.append("poor drought retention")
        if data.get("cdi", 1) < 0.3:
            weaknesses.append("low crop diversification")
        if data.get("irrigation_pct", 100) < 30:
            weaknesses.append("limited irrigation coverage")

        if weaknesses:
            return f"{base}. Key weaknesses: {', '.join(weaknesses[:2])}. Resilience driven primarily by {', '.join(top_vars)}."
        return f"{base}. Score driven primarily by {', '.join(top_vars)}."
