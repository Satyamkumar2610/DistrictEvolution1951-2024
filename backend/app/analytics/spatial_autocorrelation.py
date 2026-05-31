"""
Spatial Autocorrelation Module — PySAL-backed.

Replaces simple contiguous-neighbor averaging with formal spatial statistics:
  - Moran's I — Global spatial autocorrelation (is yield clustered state-wide?)
  - Getis-Ord Gi* — Local hotspot detection (which districts form high/low clusters?)

Both statistics use Queen contiguity weights built from PostGIS neighbor queries.
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------
try:
    from esda.getisord import G_Local
    from esda.moran import Moran
    from libpysal.weights import W

    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    logger.warning(
        "PySAL (libpysal + esda) not installed — spatial autocorrelation disabled. "
        "Install with: pip install libpysal esda"
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MoranResult:
    """Global Moran's I result."""

    morans_i: float  # -1 to +1
    expected_i: float  # under null (≈ -1/(n-1))
    z_score: float
    p_value: float
    significant: bool  # at α = 0.05
    interpretation: str  # "clustered", "dispersed", "random"


@dataclass
class HotspotDistrict:
    """A single district's Gi* classification."""

    cdk: str
    name: str | None
    gi_star_z: float
    p_value: float
    cluster_type: str  # "hot_spot", "cold_spot", "not_significant"
    confidence_level: str  # "99%", "95%", "90%", "n/s"


@dataclass
class SpatialAutocorrelationReport:
    """Full spatial autocorrelation analysis."""

    variable: str
    year: int | None
    global_moran: MoranResult
    hotspots: list[HotspotDistrict]
    hot_count: int
    cold_count: int


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class SpatialAutocorrelationAnalyzer:
    """
    Computes global Moran's I and local Getis-Ord Gi* for agricultural metrics.

    Usage:
        analyzer = SpatialAutocorrelationAnalyzer()
        report = analyzer.analyze(
            district_values={"cdk_1": 2500, "cdk_2": 3100, ...},
            adjacency={"cdk_1": ["cdk_2", "cdk_3"], ...},
            district_names={"cdk_1": "Varanasi", ...},
            variable="rice_yield",
            year=2020,
        )
    """

    def analyze(
        self,
        district_values: dict[str, float],
        adjacency: dict[str, list[str]],
        district_names: dict[str, str] | None = None,
        variable: str = "yield",
        year: int | None = None,
    ) -> SpatialAutocorrelationReport | None:
        """
        Run Moran's I (global) and Gi* (local) analysis.

        Args:
            district_values: {cdk: metric_value} for all districts in the region.
            adjacency: {cdk: [neighbor_cdk, ...]} queen-contiguity map.
            district_names: Optional {cdk: human_name}.
            variable: Name of the metric being analyzed.
            year: Observation year.

        Returns:
            SpatialAutocorrelationReport or None if PySAL is unavailable.
        """
        if not PYSAL_AVAILABLE:
            logger.error("Cannot run spatial autocorrelation — PySAL missing.")
            return None

        cdks = sorted(district_values.keys())
        n = len(cdks)

        if n < 5:
            logger.warning(f"Only {n} districts — spatial stats unreliable.")
            return None

        cdk_to_idx = {c: i for i, c in enumerate(cdks)}
        y = np.array([district_values[c] for c in cdks], dtype=float)

        # Build PySAL weight matrix from adjacency dict
        neighbors: dict[int, list[int]] = {}
        for cdk in cdks:
            idx = cdk_to_idx[cdk]
            nbrs = [cdk_to_idx[nb] for nb in adjacency.get(cdk, []) if nb in cdk_to_idx]
            neighbors[idx] = nbrs if nbrs else [idx]  # self-loop fallback for islands

        w = W(neighbors)
        w.transform = "R"  # row-standardize

        # ----- Global Moran's I -----
        moran = Moran(y, w)
        moran_result = MoranResult(
            morans_i=round(float(moran.I), 4),
            expected_i=round(float(moran.EI), 4),
            z_score=round(float(moran.z_norm), 4),
            p_value=round(float(moran.p_norm), 4),
            significant=bool(moran.p_norm < 0.05),
            interpretation=self._interpret_moran(float(moran.I), float(moran.p_norm)),
        )

        # ----- Local Getis-Ord Gi* -----
        gi = G_Local(y, w, star=True)
        hotspots: list[HotspotDistrict] = []
        hot_count = 0
        cold_count = 0

        for i, cdk in enumerate(cdks):
            z = float(gi.Zs[i])
            p = float(gi.p_sim[i]) if hasattr(gi, "p_sim") else float(gi.p_norm[i])

            cluster_type, conf = self._classify_hotspot(z, p)
            if cluster_type == "hot_spot":
                hot_count += 1
            elif cluster_type == "cold_spot":
                cold_count += 1

            hotspots.append(
                HotspotDistrict(
                    cdk=cdk,
                    name=district_names.get(cdk) if district_names else None,
                    gi_star_z=round(z, 4),
                    p_value=round(p, 4),
                    cluster_type=cluster_type,
                    confidence_level=conf,
                )
            )

        # Sort hotspots by absolute z-score descending
        hotspots.sort(key=lambda h: abs(h.gi_star_z), reverse=True)

        return SpatialAutocorrelationReport(
            variable=variable,
            year=year,
            global_moran=moran_result,
            hotspots=hotspots,
            hot_count=hot_count,
            cold_count=cold_count,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _interpret_moran(i_val: float, p_val: float) -> str:
        if p_val >= 0.05:
            return "random"
        return "clustered" if i_val > 0 else "dispersed"

    @staticmethod
    def _classify_hotspot(z: float, p: float) -> tuple[str, str]:
        """Classify a Gi* result into hot/cold spot with confidence."""
        if p < 0.01:
            conf = "99%"
        elif p < 0.05:
            conf = "95%"
        elif p < 0.10:
            conf = "90%"
        else:
            return "not_significant", "n/s"

        return ("hot_spot" if z > 0 else "cold_spot"), conf
