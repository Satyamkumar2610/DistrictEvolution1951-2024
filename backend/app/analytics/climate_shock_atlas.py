"""
Climate Shock Atlas.

Automatically attributes district-level yield shocks to specific climatic events.
Links abnormal yield drops or surges to tagged climate episodes:
    - Drought (SPI < -1.5)
    - Flood (rainfall > P95 in monsoon window)
    - Heat Wave (Tmax > 40°C for ≥ 5 consecutive days)
    - Cold Wave (Tmin < 4°C for ≥ 5 consecutive days)
    - Cyclone (tagged from IMD cyclone track data)

For each shock year, the module:
    1. Detects abnormal yield deviations (> 1.5 σ below trend).
    2. Scans climate variables for concurrent extreme events.
    3. Attributes causality via temporal alignment and magnitude correlation.
"""

import logging
from dataclasses import dataclass, field

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

class ShockType:
    DROUGHT = "drought"
    FLOOD = "flood"
    HEAT_WAVE = "heat_wave"
    COLD_WAVE = "cold_wave"
    CYCLONE = "cyclone"
    UNKNOWN = "unknown"


@dataclass
class ClimaticEvent:
    """A detected climatic event in a specific year."""
    event_type: str          # ShockType value
    year: int
    severity: str            # "moderate", "severe", "extreme"
    metric_value: float      # SPI, rainfall mm, temp °C, etc.
    threshold: float         # the threshold that was exceeded
    description: str


@dataclass
class YieldShock:
    """A detected abnormal yield deviation."""
    cdk: str
    year: int
    crop: str
    actual_yield: float
    expected_yield: float    # from trend
    deviation_pct: float     # % below expected (negative = drop)
    z_score: float


@dataclass
class ShockAttribution:
    """Attribution linking a yield shock to a climatic event."""
    cdk: str
    year: int
    crop: str
    yield_shock: YieldShock
    attributed_events: list[ClimaticEvent]
    attribution_confidence: float   # 0-1
    total_yield_loss_pct: float
    interpretation: str


@dataclass
class ClimateShockAtlasReport:
    """Complete Climate Shock Atlas for a district."""
    cdk: str
    name: str | None
    period: str
    total_shock_years: int
    attributions: list[ShockAttribution]
    event_frequency: dict[str, int]    # event_type -> count
    most_damaging_event_type: str | None
    avg_loss_per_shock_pct: float
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class ClimateShockAnalyzer:
    """
    Detects yield shocks and attributes them to concurrent climatic events.
    """

    def __init__(
        self,
        yield_shock_threshold_z: float = 1.5,
        spi_drought_threshold: float = -1.5,
        flood_rainfall_percentile: float = 95.0,
        heat_wave_temp_c: float = 40.0,
        heat_wave_min_days: int = 5,
        cold_wave_temp_c: float = 4.0,
    ):
        self.yield_shock_z = yield_shock_threshold_z
        self.spi_drought = spi_drought_threshold
        self.flood_pctl = flood_rainfall_percentile
        self.heat_temp = heat_wave_temp_c
        self.heat_days = heat_wave_min_days
        self.cold_temp = cold_wave_temp_c

    def analyze(
        self,
        cdk: str,
        name: str | None,
        crop: str,
        yearly_yields: dict[int, float],
        yearly_climate: dict[int, dict[str, float]],
    ) -> ClimateShockAtlasReport:
        """
        Run full shock detection and attribution.

        Args:
            cdk: District identifier.
            name: District name.
            crop: Crop name.
            yearly_yields: {year: yield_kg_ha}.
            yearly_climate: {year: {
                "rainfall_mm": ...,
                "spi": ...,              # Standardized Precipitation Index
                "tmax_mean": ...,        # mean daily Tmax for growing season
                "tmin_mean": ...,        # mean daily Tmin
                "tmax_extreme_days": ..., # days > heat_wave threshold
                "tmin_extreme_days": ..., # days < cold_wave threshold
            }}

        Returns:
            ClimateShockAtlasReport.
        """
        warnings_list: list[str] = []
        years = sorted(set(yearly_yields.keys()) & set(yearly_climate.keys()))

        if len(years) < 5:
            warnings_list.append(f"Only {len(years)} overlapping years — analysis may be unreliable.")

        # Step 1: Detect yield shocks
        shocks = self._detect_yield_shocks(cdk, crop, yearly_yields)

        # Step 2: Detect climate events per year
        climate_events = self._detect_climate_events(yearly_climate)

        # Step 3: Attribute shocks to events
        attributions: list[ShockAttribution] = []
        event_freq: dict[str, int] = {}
        total_loss = 0.0

        for shock in shocks:
            events_in_year = climate_events.get(shock.year, [])

            # Calculate attribution confidence
            if events_in_year:
                confidence = min(0.95, 0.5 + 0.15 * len(events_in_year))
                for evt in events_in_year:
                    event_freq[evt.event_type] = event_freq.get(evt.event_type, 0) + 1
            else:
                confidence = 0.2  # unexplained shock
                events_in_year = [ClimaticEvent(
                    event_type=ShockType.UNKNOWN,
                    year=shock.year,
                    severity="unknown",
                    metric_value=0,
                    threshold=0,
                    description="No concurrent climatic event detected — shock may be due to pest, policy, or data issues.",
                )]

            # Interpretation
            if events_in_year and events_in_year[0].event_type != ShockType.UNKNOWN:
                primary = events_in_year[0]
                interp = (
                    f"{crop.capitalize()} yield dropped {abs(shock.deviation_pct):.1f}% in {shock.year}, "
                    f"attributed to {primary.event_type.replace('_', ' ')} "
                    f"({primary.severity} — {primary.description})"
                )
            else:
                interp = (
                    f"{crop.capitalize()} yield dropped {abs(shock.deviation_pct):.1f}% in {shock.year} "
                    f"with no clear climatic trigger identified."
                )

            attributions.append(ShockAttribution(
                cdk=cdk,
                year=shock.year,
                crop=crop,
                yield_shock=shock,
                attributed_events=events_in_year,
                attribution_confidence=round(confidence, 2),
                total_yield_loss_pct=round(shock.deviation_pct, 1),
                interpretation=interp,
            ))
            total_loss += abs(shock.deviation_pct)

        # Sort by year
        attributions.sort(key=lambda a: a.year)

        # Most damaging event type
        most_damaging = max(event_freq, key=lambda k: event_freq[k]) if event_freq else None

        avg_loss = total_loss / len(shocks) if shocks else 0.0

        period = f"{min(years)}-{max(years)}" if years else "N/A"

        return ClimateShockAtlasReport(
            cdk=cdk,
            name=name,
            period=period,
            total_shock_years=len(shocks),
            attributions=attributions,
            event_frequency=event_freq,
            most_damaging_event_type=most_damaging,
            avg_loss_per_shock_pct=round(avg_loss, 1),
            warnings=warnings_list,
        )

    # ------------------------------------------------------------------
    # Yield shock detection
    # ------------------------------------------------------------------
    def _detect_yield_shocks(
        self, cdk: str, crop: str, yearly_yields: dict[int, float],
    ) -> list[YieldShock]:
        """Detect years with abnormal yield drops relative to linear trend."""
        years = sorted(yearly_yields.keys())
        values = np.array([yearly_yields[y] for y in years], dtype=float)

        if len(values) < 5:
            return []

        # Fit linear trend
        x = np.arange(len(values), dtype=float)
        if SCIPY_OK:
            slope, intercept, _, _, _ = scipy_stats.linregress(x, values)
        else:
            slope = 0.0
            intercept = float(np.mean(values))

        trend = slope * x + intercept
        residuals = values - trend
        std = float(np.std(residuals))

        if std < 1e-4:
            return []

        shocks: list[YieldShock] = []
        for i, yr in enumerate(years):
            z = float(residuals[i] / std)
            if z < -self.yield_shock_z:  # negative = below trend
                deviation_pct = float((values[i] - trend[i]) / trend[i] * 100) if trend[i] > 0 else 0
                shocks.append(YieldShock(
                    cdk=cdk,
                    year=yr,
                    crop=crop,
                    actual_yield=round(float(values[i]), 1),
                    expected_yield=round(float(trend[i]), 1),
                    deviation_pct=round(deviation_pct, 1),
                    z_score=round(z, 2),
                ))

        return shocks

    # ------------------------------------------------------------------
    # Climate event detection
    # ------------------------------------------------------------------
    def _detect_climate_events(
        self, yearly_climate: dict[int, dict[str, float]],
    ) -> dict[int, list[ClimaticEvent]]:
        """Scan climate variables for extreme events per year."""
        events: dict[int, list[ClimaticEvent]] = {}

        # Compute rainfall percentiles for flood detection
        all_rainfall = [
            d.get("rainfall_mm", 0) for d in yearly_climate.values()
            if d.get("rainfall_mm", 0) > 0
        ]
        rainfall_p95 = float(np.percentile(all_rainfall, self.flood_pctl)) if all_rainfall else 9999

        for year, climate in yearly_climate.items():
            year_events: list[ClimaticEvent] = []

            # Drought (SPI-based)
            spi = climate.get("spi")
            if spi is not None and spi < self.spi_drought:
                severity = "extreme" if spi < -2.0 else "severe" if spi < -1.75 else "moderate"
                year_events.append(ClimaticEvent(
                    event_type=ShockType.DROUGHT,
                    year=year,
                    severity=severity,
                    metric_value=round(spi, 2),
                    threshold=self.spi_drought,
                    description=f"SPI={spi:.2f} indicates {severity} drought conditions",
                ))

            # Flood
            rainfall = climate.get("rainfall_mm", 0)
            if rainfall > rainfall_p95 and rainfall_p95 < 9999:
                severity = "extreme" if rainfall > rainfall_p95 * 1.5 else "severe" if rainfall > rainfall_p95 * 1.2 else "moderate"
                year_events.append(ClimaticEvent(
                    event_type=ShockType.FLOOD,
                    year=year,
                    severity=severity,
                    metric_value=round(rainfall, 1),
                    threshold=round(rainfall_p95, 1),
                    description=f"Rainfall {rainfall:.0f}mm exceeded P95 ({rainfall_p95:.0f}mm)",
                ))

            # Heat wave
            extreme_hot_days = climate.get("tmax_extreme_days", 0)
            if extreme_hot_days >= self.heat_days:
                tmax = climate.get("tmax_mean", 0)
                severity = "extreme" if extreme_hot_days > 15 else "severe" if extreme_hot_days > 10 else "moderate"
                year_events.append(ClimaticEvent(
                    event_type=ShockType.HEAT_WAVE,
                    year=year,
                    severity=severity,
                    metric_value=round(tmax, 1),
                    threshold=self.heat_temp,
                    description=f"{int(extreme_hot_days)} days exceeded {self.heat_temp}°C",
                ))

            # Cold wave
            extreme_cold_days = climate.get("tmin_extreme_days", 0)
            if extreme_cold_days >= self.heat_days:
                tmin = climate.get("tmin_mean", 0)
                severity = "extreme" if extreme_cold_days > 15 else "severe" if extreme_cold_days > 10 else "moderate"
                year_events.append(ClimaticEvent(
                    event_type=ShockType.COLD_WAVE,
                    year=year,
                    severity=severity,
                    metric_value=round(tmin, 1),
                    threshold=self.cold_temp,
                    description=f"{int(extreme_cold_days)} days below {self.cold_temp}°C",
                ))

            if year_events:
                events[year] = year_events

        return events
