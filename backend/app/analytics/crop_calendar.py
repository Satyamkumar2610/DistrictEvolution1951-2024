"""
Crop Calendar Detector Module.

Automatically detects peak sowing and harvest dates from NDVI time-series
curves. Flags early / late planting as risk indicators for yield analysis.

Methodology:
  1. Smooth monthly NDVI with Savitzky-Golay filter.
  2. Detect inflection points (green-up = sowing proxy, brown-down = harvest).
  3. Compare detected dates against reference crop calendar.
  4. Flag deviations as `early_sowing`, `late_sowing`, `early_harvest`, etc.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

try:
    from scipy.signal import savgol_filter
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


# ---------------------------------------------------------------------------
# Reference Crop Calendars (India, generalized)
# ---------------------------------------------------------------------------

# month number (1-12) for typical sowing and harvest
REFERENCE_CALENDAR: dict[str, dict[str, int]] = {
    "rice_kharif": {"sow": 6, "harvest": 11},
    "rice_rabi": {"sow": 11, "harvest": 4},
    "wheat": {"sow": 11, "harvest": 4},
    "maize_kharif": {"sow": 6, "harvest": 10},
    "cotton": {"sow": 5, "harvest": 11},
    "soyabean": {"sow": 6, "harvest": 10},
    "groundnut": {"sow": 6, "harvest": 10},
    "chickpea": {"sow": 10, "harvest": 3},
    "sugarcane": {"sow": 2, "harvest": 1},  # 12-month crop
    "mustard": {"sow": 10, "harvest": 3},
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CropPhase:
    """Detected phenological phase."""
    phase: str          # "green_up" (sowing proxy) or "senescence" (harvest proxy)
    month: int          # detected month (1-12)
    ndvi_value: float   # NDVI at the inflection


@dataclass
class CalendarDeviation:
    """A deviation from the reference crop calendar."""
    event: str                  # "early_sowing", "late_harvest", etc.
    detected_month: int
    reference_month: int
    deviation_months: int       # positive = late, negative = early
    risk_level: str             # "low", "medium", "high"
    description: str


@dataclass
class CropCalendarResult:
    """Full crop calendar detection result for one district-year."""
    cdk: str
    year: int
    crop: str | None
    detected_phases: list[CropPhase]
    peak_ndvi_month: int
    peak_ndvi_value: float
    growing_season_length: int  # months between green-up and senescence
    deviations: list[CalendarDeviation]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class CropCalendarDetector:
    """
    Detect crop phenological phases from monthly NDVI profiles.
    """

    def __init__(self, smooth_window: int = 5, smooth_poly: int = 2):
        self.smooth_window = smooth_window
        self.smooth_poly = smooth_poly

    def detect(
        self,
        monthly_ndvi: dict[int, float],
        cdk: str = "",
        year: int = 0,
        crop: str | None = None,
    ) -> CropCalendarResult:
        """
        Detect crop calendar from monthly NDVI values.

        Args:
            monthly_ndvi: {month(1-12): ndvi_value}
            cdk: District identifier.
            year: Observation year.
            crop: Optional crop name to compare against reference calendar.

        Returns:
            CropCalendarResult with detected phases and deviations.
        """
        warnings_list: list[str] = []

        # Need at least 10 months of data
        months = sorted(monthly_ndvi.keys())
        if len(months) < 10:
            warnings_list.append(f"Only {len(months)} months of NDVI data available.")

        # Build 12-month array (fill missing with interpolation)
        ndvi_array = np.zeros(12)
        for m in range(1, 13):
            ndvi_array[m - 1] = monthly_ndvi.get(m, 0.0)

        # Interpolate zeros
        for i in range(12):
            if ndvi_array[i] == 0:
                prev = ndvi_array[i - 1] if i > 0 else ndvi_array[11]
                nxt = ndvi_array[(i + 1) % 12]
                ndvi_array[i] = (prev + nxt) / 2

        # Smooth
        if SCIPY_OK and len(ndvi_array) >= self.smooth_window:
            smoothed = savgol_filter(
                ndvi_array, self.smooth_window, self.smooth_poly, mode="wrap"
            )
        else:
            smoothed = ndvi_array.copy()

        # Detect phases via first derivative
        phases = self._detect_phases(smoothed)

        # Peak NDVI
        peak_idx = int(np.argmax(smoothed))
        peak_month = peak_idx + 1
        peak_value = float(smoothed[peak_idx])

        # Growing season length
        green_ups = [p for p in phases if p.phase == "green_up"]
        senescences = [p for p in phases if p.phase == "senescence"]
        if green_ups and senescences:
            gs_length = (senescences[0].month - green_ups[0].month) % 12
            if gs_length == 0:
                gs_length = 12
        else:
            gs_length = 0

        # Compare to reference calendar
        deviations: list[CalendarDeviation] = []
        if crop and crop.lower() in REFERENCE_CALENDAR:
            ref = REFERENCE_CALENDAR[crop.lower()]
            deviations = self._check_deviations(phases, ref)

        return CropCalendarResult(
            cdk=cdk,
            year=year,
            crop=crop,
            detected_phases=phases,
            peak_ndvi_month=peak_month,
            peak_ndvi_value=round(peak_value, 4),
            growing_season_length=gs_length,
            deviations=deviations,
            warnings=warnings_list,
        )

    def _detect_phases(self, smoothed: np.ndarray) -> list[CropPhase]:
        """Find green-up and senescence inflection points."""
        phases: list[CropPhase] = []
        n = len(smoothed)

        # First derivative (circular)
        deriv = np.zeros(n)
        for i in range(n):
            deriv[i] = smoothed[(i + 1) % n] - smoothed[i]

        # Green-up: derivative goes from negative → positive
        # Senescence: derivative goes from positive → negative
        for i in range(n):
            prev_d = deriv[(i - 1) % n]
            curr_d = deriv[i]

            if prev_d <= 0 and curr_d > 0:
                phases.append(CropPhase(
                    phase="green_up",
                    month=i + 1,
                    ndvi_value=round(float(smoothed[i]), 4),
                ))
            elif prev_d >= 0 and curr_d < 0:
                phases.append(CropPhase(
                    phase="senescence",
                    month=i + 1,
                    ndvi_value=round(float(smoothed[i]), 4),
                ))

        return phases

    def _check_deviations(
        self,
        phases: list[CropPhase],
        reference: dict[str, int],
    ) -> list[CalendarDeviation]:
        """Compare detected phases to reference calendar."""
        deviations: list[CalendarDeviation] = []
        ref_sow = reference.get("sow", 0)
        ref_harvest = reference.get("harvest", 0)

        green_ups = [p for p in phases if p.phase == "green_up"]
        senescences = [p for p in phases if p.phase == "senescence"]

        # Find closest green-up to reference sowing
        if green_ups and ref_sow:
            closest_gu = min(green_ups, key=lambda p: self._circular_dist(p.month, ref_sow))
            dev = self._circular_diff(closest_gu.month, ref_sow)
            if abs(dev) >= 1:
                event = "late_sowing" if dev > 0 else "early_sowing"
                deviations.append(CalendarDeviation(
                    event=event,
                    detected_month=closest_gu.month,
                    reference_month=ref_sow,
                    deviation_months=dev,
                    risk_level=self._deviation_risk(abs(dev)),
                    description=f"Sowing detected in month {closest_gu.month}, "
                                f"reference is month {ref_sow} ({abs(dev)} months {'late' if dev > 0 else 'early'})",
                ))

        # Find closest senescence to reference harvest
        if senescences and ref_harvest:
            closest_sen = min(senescences, key=lambda p: self._circular_dist(p.month, ref_harvest))
            dev = self._circular_diff(closest_sen.month, ref_harvest)
            if abs(dev) >= 1:
                event = "late_harvest" if dev > 0 else "early_harvest"
                deviations.append(CalendarDeviation(
                    event=event,
                    detected_month=closest_sen.month,
                    reference_month=ref_harvest,
                    deviation_months=dev,
                    risk_level=self._deviation_risk(abs(dev)),
                    description=f"Harvest detected in month {closest_sen.month}, "
                                f"reference is month {ref_harvest} ({abs(dev)} months {'late' if dev > 0 else 'early'})",
                ))

        return deviations

    @staticmethod
    def _circular_dist(a: int, b: int) -> int:
        """Circular distance between two months."""
        d = abs(a - b)
        return min(d, 12 - d)

    @staticmethod
    def _circular_diff(detected: int, reference: int) -> int:
        """Signed circular difference (positive = detected is later)."""
        diff = detected - reference
        if diff > 6:
            diff -= 12
        elif diff < -6:
            diff += 12
        return diff

    @staticmethod
    def _deviation_risk(months: int) -> str:
        if months >= 3:
            return "high"
        elif months >= 2:
            return "medium"
        return "low"
