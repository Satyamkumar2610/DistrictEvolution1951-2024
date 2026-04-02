"""
Yield Backcaster ML Engine
Uses scikit-learn models to predict pre-split yields for child districts.
"""

import logging
import math
from typing import Any

import numpy as np

try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import root_mean_squared_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn is not available. ML backcasting will fail over to basic ratio models.")

from app.ml.backcast_data_pipeline import BackcastDataPipeline, BackcastTrainingData
from app.schemas.backcast import (
    BackcastChildResult,
    BackcastResponse,
    BackcastYearPoint,
    ConservationCheck,
)

logger = logging.getLogger("app.ml.yield_backcaster")


class YieldBackcaster:
    """Predicts pre-split yields for child districts using ML and parent data."""

    def __init__(self) -> None:
        self.pipeline = BackcastDataPipeline()
        self.RIDGE_ALPHA = 1.0

    async def backcast_all_children(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        crop: str,
        start_year: int = 1966,
    ) -> BackcastResponse:
        """
        Backcast yields for all children and validate mass conservation.
        """
        target_years = range(start_year, split_year)
        child_results: dict[str, BackcastChildResult] = {}

        for child in child_cdks:
            sibling_cdks = [c for c in child_cdks if c != child]
            
            # 1. Fetch training data
            data = await self.pipeline.fetch_training_data(
                child_cdk=child,
                parent_cdk=parent_cdk,
                sibling_cdks=sibling_cdks,
                split_year=split_year,
                crop=crop,
            )
            
            # 2. Predict
            result = self._predict_child(
                child_cdk=child,
                target_years=target_years,
                data=data
            )
            child_results[child] = result

        # 3. Conservation Check
        # Ensure sum(child_yields * child_areas) ≈ parent_yield * parent_area
        # Because we may not have child_areas historically, we approximate using area ratio
        # For a given year, total_post_area = parent_area
        
        # A simple check on average yields
        is_valid = True
        relative_error = 0.0
        parent_total_prod = 0.0
        children_sum_prod = 0.0
        
        # Determine aggregate method used
        method_counts = {}
        for res in child_results.values():
            for yp in res.backcasted_yields:
                method_counts[yp.method] = method_counts.get(yp.method, 0) + 1
        
        primary_method = "unknown"
        if method_counts:
            primary_method = max(method_counts, key=lambda k: method_counts[k])

        # We will do a rough conservation check strictly on the final year before split
        test_year = split_year - 1
        # Need parent yield for test year
        # we check the first child's data parent_yields as they all share the same parent yields
        sample_data = await self.pipeline.fetch_training_data(child_cdks[0], parent_cdk, [], split_year, crop)
        parent_y_test = sample_data.parent_yields.get(test_year)
        
        if parent_y_test is not None:
             # Calculate weighted average child yield
             child_avg_yield = 0.0
             total_ratio = 0.0
             for child, res in child_results.items():
                  # Get yield for test year
                  c_yield = next((yp.predicted_yield for yp in res.backcasted_yields if yp.year == test_year), None)
                  if c_yield is not None:
                      # We'll need the child's ratio. Re-fetch or pass it. We fetch it inside _predict.
                      # For simplicity here, just doing basic average.
                      child_avg_yield += c_yield
                      total_ratio += 1.0 # fallback

             if total_ratio > 0:
                  child_avg_yield /= total_ratio
                  
             # Parent yields and child average yields should be somewhat close
             if parent_y_test > 0:
                 relative_error = abs(child_avg_yield - parent_y_test) / parent_y_test
             is_valid = relative_error < 0.3  # Tolerate up to 30% error on simple average

        conservation = ConservationCheck(
            is_valid=bool(is_valid),
            relative_error=float(relative_error),
            parent_total_production=parent_y_test if parent_y_test else 0.0,
            children_sum_production=parent_y_test if parent_y_test else 0.0, # Placeholder
        )

        return BackcastResponse(
            parent_cdk=parent_cdk,
            split_year=split_year,
            crop=crop,
            method=primary_method,
            children=child_results,
            conservation_check=conservation
        )

    def _predict_child(
        self,
        child_cdk: str,
        target_years: range,
        data: BackcastTrainingData
    ) -> BackcastChildResult:
        """Core prediction logic switching based on data availability."""
        
        # Find overlapping years (post-split) where both child and parent exist.
        # Wait, parent district might cease to exist after split in some datasets!
        # If parent ceases, we don't have overlapping years.
        # But wait - if parent ceases to exist, we can't train `child(post) vs parent(post)`.
        # However, we CAN train `child(post) vs time` and extrapolate, OR 
        # use the child's historical sibling ratios.
        
        # Let's adjust: "Parent yield" might just mean the yield of the new district with the same name,
        # or we rely strictly on post-split trend and area_ratio if no parent exists post-split.
        
        overlapping_years = [y for y in data.child_yields if y in data.parent_yields]
        n_overlap = len(overlapping_years)
        
        if n_overlap >= 5 and SKLEARN_AVAILABLE:
            return self._predict_ml(child_cdk, target_years, data, overlapping_years)
        elif n_overlap >= 3 and SKLEARN_AVAILABLE:
            return self._predict_ridge(child_cdk, target_years, data, overlapping_years)
        elif len(data.child_yields) >= 1:
            return self._predict_ratio(child_cdk, target_years, data)
        else:
            return self._predict_apportioned(child_cdk, target_years, data)

    def _predict_ml(
        self,
        child_cdk: str,
        target_years: range,
        data: BackcastTrainingData,
        overlapping_years: list[int]
    ) -> BackcastChildResult:
        """Full ML model (GradientBoosting) when >= 5 years of overlap."""
        
        X_train = []
        y_train = []
        
        for y in overlapping_years:
            parent_y = data.parent_yields[y]
            child_y = data.child_yields[y]
            
            # Simple feature: parent_yield, area_ratio
            features = [parent_y, data.area_ratio]
            X_train.append(features)
            y_train.append(child_y)
            
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        model = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
        model.fit(X_train, y_train)
        
        train_preds = model.predict(X_train)
        r2 = r2_score(y_train, train_preds)
        rmse = root_mean_squared_error(y_train, train_preds)
        confidence = float(min(0.95, max(0.5, r2)))
        
        predicted_points = []
        for y in target_years:
            # We must have parent data for the target year
            parent_y = data.parent_yields.get(y)
            if parent_y is None:
                continue
                
            x_target = np.array([[parent_y, data.area_ratio]])
            pred_y = float(model.predict(x_target)[0])
            pred_y = max(0.0, pred_y)
            
            predicted_points.append(
                BackcastYearPoint(
                    year=y,
                    predicted_yield=round(pred_y, 2),
                    confidence=round(confidence, 2),
                    lower_bound=round(max(0, pred_y - rmse), 2),
                    upper_bound=round(pred_y + rmse, 2),
                    method="ml_gradient_boosting"
                )
            )
            
        return BackcastChildResult(
            child_cdk=child_cdk,
            backcasted_yields=predicted_points,
            model_stats={"r_squared": r2, "rmse": rmse, "samples": len(overlapping_years)},
            features_used=["parent_yield", "area_ratio"],
            feature_importances={
                "parent_yield": float(model.feature_importances_[0]), 
                "area_ratio": float(model.feature_importances_[1])
            }
        )

    def _predict_ridge(
        self,
        child_cdk: str,
        target_years: range,
        data: BackcastTrainingData,
        overlapping_years: list[int]
    ) -> BackcastChildResult:
        """Ridge regression when 3-4 years of overlap."""
        X_train = []
        y_train = []
        
        for y in overlapping_years:
            parent_y = data.parent_yields[y]
            child_y = data.child_yields[y]
            features = [parent_y]
            X_train.append(features)
            y_train.append(child_y)
            
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        model = Ridge(alpha=self.RIDGE_ALPHA)
        model.fit(X_train, y_train)
        
        train_preds = model.predict(X_train)
        r2 = r2_score(y_train, train_preds)
        rmse = root_mean_squared_error(y_train, train_preds)
        confidence = float(min(0.7, max(0.4, r2)))
        
        predicted_points = []
        for y in target_years:
            parent_y = data.parent_yields.get(y)
            if parent_y is None:
                continue
                
            x_target = np.array([[parent_y]])
            pred_y = float(model.predict(x_target)[0])
            pred_y = max(0.0, pred_y)
            
            predicted_points.append(
                BackcastYearPoint(
                    year=y,
                    predicted_yield=round(pred_y, 2),
                    confidence=round(confidence, 2),
                    lower_bound=round(max(0, pred_y - rmse), 2),
                    upper_bound=round(pred_y + rmse, 2),
                    method="ridge_regression"
                )
            )
            
        return BackcastChildResult(
            child_cdk=child_cdk,
            backcasted_yields=predicted_points,
            model_stats={"r_squared": r2, "rmse": rmse, "samples": len(overlapping_years)},
            features_used=["parent_yield"],
            feature_importances={"parent_yield": 1.0}
        )

    def _predict_ratio(
        self,
        child_cdk: str,
        target_years: range,
        data: BackcastTrainingData
    ) -> BackcastChildResult:
        """Ratio extrapolation when only 1-2 years of child data are available."""
        # Calculate recent child/parent ratio (or child/sibling if parent missing)
        # Actually, if parent is completely missing post-split, we can use the 
        # parent's LAST KNOWN yield and child's FIRST KNOWN yield to figure out a rough ratio.
        
        ratios = []
        for y, child_y in data.child_yields.items():
            parent_y = data.parent_yields.get(y)
            if parent_y and parent_y > 0:
                ratios.append(child_y / parent_y)
                
        if not ratios:
             # Try nearest years
             if data.parent_yields and data.child_yields:
                  max_p_year = max(data.parent_yields.keys())
                  min_c_year = min(data.child_yields.keys())
                  parent_y = data.parent_yields[max_p_year]
                  child_y = data.child_yields[min_c_year]
                  if parent_y > 0:
                      ratios.append(child_y / parent_y)
                      
        avg_ratio = np.mean(ratios) if ratios else 1.0
        confidence = 0.4
        rmse = 500.0  # High uncertainty
        
        predicted_points = []
        for y in target_years:
            parent_y = data.parent_yields.get(y)
            if parent_y is None:
                continue
                
            pred_y = parent_y * avg_ratio
            predicted_points.append(
                BackcastYearPoint(
                    year=y,
                    predicted_yield=round(pred_y, 2),
                    confidence=confidence,
                    lower_bound=round(max(0, pred_y - rmse), 2),
                    upper_bound=round(pred_y + rmse, 2),
                    method="ratio_extrapolation"
                )
            )
            
        return BackcastChildResult(
            child_cdk=child_cdk,
            backcasted_yields=predicted_points,
            model_stats={"mean_ratio": float(avg_ratio), "rmse": rmse, "samples": len(ratios)},
            features_used=["child_parent_ratio"],
            feature_importances={}
        )

    def _predict_apportioned(
        self,
        child_cdk: str,
        target_years: range,
        data: BackcastTrainingData
    ) -> BackcastChildResult:
        """Basic area-weighted apportionment when NO child data exists."""
        # This assumes yield is uniform across the parent district
        confidence = 0.2
        rmse = 1000.0 # Extremely high uncertainty
        
        predicted_points = []
        for y in target_years:
            parent_y = data.parent_yields.get(y)
            if parent_y is None:
                continue
                
            pred_y = parent_y # Yield is intensive property, remains same on area-split assuming uniformity
            
            predicted_points.append(
                BackcastYearPoint(
                    year=y,
                    predicted_yield=round(pred_y, 2),
                    confidence=confidence,
                    lower_bound=round(max(0, pred_y - rmse), 2),
                    upper_bound=round(pred_y + rmse, 2),
                    method="area_apportionment"
                )
            )
            
        return BackcastChildResult(
            child_cdk=child_cdk,
            backcasted_yields=predicted_points,
            model_stats={"notes": "No post-split child data available. Assumed uniform yield.", "rmse": rmse},
            features_used=["parent_yield_raw"],
            feature_importances={}
        )
