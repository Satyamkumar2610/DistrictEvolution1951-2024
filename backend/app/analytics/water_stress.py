"""
Water Stress Module — Irrigation Efficiency & Groundwater Depletion.

Integrates India-WRIS groundwater depth data and PMFBY crop insurance claims
to map surface vs. groundwater stress and flag unsustainable aquifers.

Data Sources:
    - India-WRIS: Pre/post-monsoon groundwater levels (mbgl)
    - PMFBY / PMKSY: Crop insurance claim rates as a proxy for climate damage
    - Existing agri_metrics: Irrigated area percentages
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    from scipy import stats as scipy_stats
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GroundwaterStatus:
    """Groundwater health for a single district."""
    cdk: str
    name: str | None
    pre_monsoon_depth_m: float     # depth to water table (mbgl) — higher = worse
    post_monsoon_depth_m: float
    recharge_m: float              # post - pre (positive = recharged)
    depletion_trend_m_yr: float    # annual rate of depth increase (positive = depleting)
    category: str                  # "Safe", "Semi-Critical", "Critical", "Over-Exploited"
    years_to_critical: float | None  # estimated years until over-exploited at current rate


@dataclass
class IrrigationProfile:
    """Irrigation mix for a district."""
    cdk: str
    net_irrigated_pct: float       # % of cropped area irrigated
    canal_pct: float               # % irrigated by canal/surface
    groundwater_pct: float         # % irrigated by tube/bore wells
    other_pct: float               # sprinkler, drip, tanks, etc.
    dependency_risk: str           # "High GW Dependency", "Balanced", "Surface Dominant"


@dataclass
class WaterStressAlert:
    """Water stress alert for a district."""
    cdk: str
    name: str | None
    stress_score: float            # 0-100 composite
    stress_level: str              # "Low", "Moderate", "High", "Critical"
    factors: list[str]
    recommendation: str


@dataclass
class WaterStressReport:
    """Complete water stress analysis for a region."""
    region: str
    n_districts: int
    groundwater_statuses: list[GroundwaterStatus]
    irrigation_profiles: list[IrrigationProfile]
    stress_alerts: list[WaterStressAlert]
    over_exploited_count: int
    critical_count: int
    high_gw_dependency_count: int
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CGWB classification thresholds (India Central Ground Water Board)
# ---------------------------------------------------------------------------

CGWB_THRESHOLDS = {
    # depth_mbgl ranges for pre-monsoon
    "safe": 8.0,
    "semi_critical": 15.0,
    "critical": 25.0,
    # above 25m = over-exploited
}


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class WaterStressAnalyzer:
    """
    Analyses groundwater depletion, irrigation dependency, and composite
    water stress risk for agricultural districts.
    """

    def classify_groundwater(
        self,
        cdk: str,
        name: str | None,
        pre_monsoon_depths: dict[int, float],
        post_monsoon_depths: dict[int, float],
    ) -> GroundwaterStatus:
        """
        Classify groundwater health using time-series depth data.

        Args:
            cdk: District identifier.
            name: District name.
            pre_monsoon_depths: {year: depth_mbgl}
            post_monsoon_depths: {year: depth_mbgl}
        """
        years = sorted(set(pre_monsoon_depths.keys()) & set(post_monsoon_depths.keys()))

        if not years:
            return GroundwaterStatus(
                cdk=cdk, name=name,
                pre_monsoon_depth_m=0, post_monsoon_depth_m=0,
                recharge_m=0, depletion_trend_m_yr=0,
                category="Unknown", years_to_critical=None,
            )

        latest_year = years[-1]
        pre_latest = pre_monsoon_depths[latest_year]
        post_latest = post_monsoon_depths[latest_year]
        recharge = pre_latest - post_latest  # positive = water table rose

        # Depletion trend (linear regression on pre-monsoon depths)
        if len(years) >= 3 and SCIPY_OK:
            y_arr = np.array(years, dtype=float)
            d_arr = np.array([pre_monsoon_depths[y] for y in years], dtype=float)
            slope, _, _, _, _ = scipy_stats.linregress(y_arr, d_arr)
            trend = float(slope)  # m/year deepening
        else:
            trend = 0.0

        # Classify using CGWB thresholds
        if pre_latest <= CGWB_THRESHOLDS["safe"]:
            category = "Safe"
        elif pre_latest <= CGWB_THRESHOLDS["semi_critical"]:
            category = "Semi-Critical"
        elif pre_latest <= CGWB_THRESHOLDS["critical"]:
            category = "Critical"
        else:
            category = "Over-Exploited"

        # Years to critical (if trending worse)
        years_to_crit = None
        if trend > 0.05 and pre_latest < CGWB_THRESHOLDS["critical"]:
            remaining = CGWB_THRESHOLDS["critical"] - pre_latest
            years_to_crit = remaining / trend

        return GroundwaterStatus(
            cdk=cdk,
            name=name,
            pre_monsoon_depth_m=round(pre_latest, 2),
            post_monsoon_depth_m=round(post_latest, 2),
            recharge_m=round(recharge, 2),
            depletion_trend_m_yr=round(trend, 3),
            category=category,
            years_to_critical=round(years_to_crit, 1) if years_to_crit else None,
        )

    def classify_irrigation(
        self,
        cdk: str,
        net_irrigated_pct: float,
        canal_pct: float,
        groundwater_pct: float,
        other_pct: float,
    ) -> IrrigationProfile:
        """Classify irrigation dependency risk."""
        if groundwater_pct > 70:
            risk = "High GW Dependency"
        elif groundwater_pct > 40 and canal_pct < 30:
            risk = "Moderate GW Dependency"
        elif canal_pct > 60:
            risk = "Surface Dominant"
        else:
            risk = "Balanced"

        return IrrigationProfile(
            cdk=cdk,
            net_irrigated_pct=round(net_irrigated_pct, 1),
            canal_pct=round(canal_pct, 1),
            groundwater_pct=round(groundwater_pct, 1),
            other_pct=round(other_pct, 1),
            dependency_risk=risk,
        )

    def compute_stress_alert(
        self,
        gw: GroundwaterStatus,
        irr: IrrigationProfile | None,
        pmfby_claim_rate: float = 0.0,
    ) -> WaterStressAlert:
        """
        Compute composite water stress score and alert.

        Args:
            gw: Groundwater status.
            irr: Irrigation profile (optional).
            pmfby_claim_rate: PMFBY crop insurance claim rate (0-1).
        """
        score = 0.0
        factors: list[str] = []

        # Groundwater depth component (0-40 points)
        if gw.category == "Over-Exploited":
            score += 40
            factors.append(f"Over-exploited aquifer ({gw.pre_monsoon_depth_m}m depth)")
        elif gw.category == "Critical":
            score += 30
            factors.append(f"Critical groundwater ({gw.pre_monsoon_depth_m}m depth)")
        elif gw.category == "Semi-Critical":
            score += 15
            factors.append(f"Semi-critical groundwater levels")

        # Depletion trend (0-20 points)
        if gw.depletion_trend_m_yr > 0.5:
            score += 20
            factors.append(f"Rapid depletion ({gw.depletion_trend_m_yr:.1f} m/year)")
        elif gw.depletion_trend_m_yr > 0.2:
            score += 10
            factors.append(f"Moderate depletion trend")

        # GW dependency (0-20 points)
        if irr and irr.groundwater_pct > 70:
            score += 20
            factors.append(f"Heavy groundwater dependency ({irr.groundwater_pct:.0f}%)")
        elif irr and irr.groundwater_pct > 50:
            score += 10

        # Low irrigation coverage (0-10 points)
        if irr and irr.net_irrigated_pct < 30:
            score += 10
            factors.append(f"Low irrigation coverage ({irr.net_irrigated_pct:.0f}%)")

        # PMFBY claims as climate damage proxy (0-10 points)
        if pmfby_claim_rate > 0.3:
            score += 10
            factors.append(f"High crop insurance claims ({pmfby_claim_rate:.0%})")
        elif pmfby_claim_rate > 0.15:
            score += 5

        score = min(100, score)

        # Classify
        if score >= 70:
            level = "Critical"
            rec = "Urgent intervention required: mandate drip irrigation, regulate bore wells, diversify to low-water crops."
        elif score >= 45:
            level = "High"
            rec = "Schedule water audit. Promote micro-irrigation. Monitor depletion trends quarterly."
        elif score >= 20:
            level = "Moderate"
            rec = "Continue monitoring. Encourage efficient irrigation practices."
        else:
            level = "Low"
            rec = "Water resources adequate. Maintain current management practices."

        return WaterStressAlert(
            cdk=gw.cdk,
            name=gw.name,
            stress_score=round(score, 1),
            stress_level=level,
            factors=factors,
            recommendation=rec,
        )

    def build_regional_report(
        self,
        groundwater_data: list[dict[str, Any]],
        irrigation_data: list[dict[str, Any]],
        pmfby_data: dict[str, float] | None = None,
        region: str = "",
    ) -> WaterStressReport:
        """
        Build a comprehensive water stress report for a region.

        Args:
            groundwater_data: List of dicts with 'cdk', 'name',
                'pre_monsoon_depths', 'post_monsoon_depths'.
            irrigation_data: List of dicts with 'cdk', 'net_irrigated_pct',
                'canal_pct', 'groundwater_pct', 'other_pct'.
            pmfby_data: {cdk: claim_rate}
            region: Region label.
        """
        warnings: list[str] = []
        gw_statuses: list[GroundwaterStatus] = []
        irr_profiles: list[IrrigationProfile] = []
        alerts: list[WaterStressAlert] = []

        # Index irrigation data by cdk
        irr_map: dict[str, IrrigationProfile] = {}
        for d in irrigation_data:
            irr = self.classify_irrigation(
                d["cdk"], d.get("net_irrigated_pct", 0),
                d.get("canal_pct", 0), d.get("groundwater_pct", 0),
                d.get("other_pct", 0)
            )
            irr_profiles.append(irr)
            irr_map[d["cdk"]] = irr

        # Process groundwater
        for d in groundwater_data:
            gw = self.classify_groundwater(
                d["cdk"], d.get("name"),
                d.get("pre_monsoon_depths", {}),
                d.get("post_monsoon_depths", {}),
            )
            gw_statuses.append(gw)

            pmfby_rate = pmfby_data.get(d["cdk"], 0.0) if pmfby_data else 0.0
            alert = self.compute_stress_alert(gw, irr_map.get(d["cdk"]), pmfby_rate)
            alerts.append(alert)

        # Sort alerts by stress score descending
        alerts.sort(key=lambda a: a.stress_score, reverse=True)

        over_exploited = sum(1 for g in gw_statuses if g.category == "Over-Exploited")
        critical = sum(1 for g in gw_statuses if g.category == "Critical")
        high_gw_dep = sum(1 for i in irr_profiles if i.dependency_risk == "High GW Dependency")

        return WaterStressReport(
            region=region,
            n_districts=len(gw_statuses),
            groundwater_statuses=gw_statuses,
            irrigation_profiles=irr_profiles,
            stress_alerts=alerts,
            over_exploited_count=over_exploited,
            critical_count=critical,
            high_gw_dependency_count=high_gw_dep,
            warnings=warnings,
        )
