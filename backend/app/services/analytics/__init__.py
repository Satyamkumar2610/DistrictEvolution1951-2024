"""
Advanced Analytics Package.
Decomposed into domain-specific modules for maintainability.
"""

from .base import BaseAnalyticsService as BaseAnalyticsService
from .crop_diversity import CropDiversityService
from .spatial_analytics import SpatialAnalyticsService
from .split_impact import SplitImpactService
from .yield_analysis import YieldAnalysisService

__all__ = [
    "AdvancedAnalyticsService",
    "BaseAnalyticsService",
    "CropDiversityService",
    "SpatialAnalyticsService",
    "SplitImpactService",
    "YieldAnalysisService",
]

# Re-export a unified class for backward compatibility until the router is fully refactored,
# or we can refactor the router to use specific services.


class AdvancedAnalyticsService(YieldAnalysisService, CropDiversityService, SplitImpactService, SpatialAnalyticsService):
    """
    Unified Analytics Service facade.
    Combines all domain-specific analytics services.
    """

    pass
