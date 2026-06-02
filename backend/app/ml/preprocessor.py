"""
Harmonization Preprocessor for Yield Panel Data.
Adjusts historical parent data to smoothly align with child boundary definitions,
creating stationary time-series for ML training.
"""

import logging

import pandas as pd

from app.repositories.lineage_repo import LineageRepository

logger = logging.getLogger(__name__)


class HarmonizationPreprocessor:
    """
    Retroactively adjusts parent yields and areas to match the geography
    of the children, ensuring no structural breaks in the training data.
    """

    def __init__(self, lineage_repo: LineageRepository):
        self.repo = lineage_repo

    async def harmonize_panel(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes a panel dataframe and synthesizes pre-split data for child districts
        based on post-split area ratios and parent historical yields.
        """
        if df.empty or "cdk" not in df.columns or "year" not in df.columns:
            return df

        try:
            history = await self.repo.get_district_history()
        except Exception as e:
            logger.error(f"Failed to fetch district history: {e}")
            return df

        df = df.copy()
        synthetic_records = []

        for event in history:
            parent_cdk = event.parent_cdk
            child_cdk = event.child_cdk
            split_year = event.split_year

            # Find the first few years of post-split area to calculate geographic ratio
            post_split = df[(df["year"] >= split_year) & (df["year"] <= split_year + 3)]
            parent_post = post_split[post_split["cdk"] == parent_cdk]["crop_area"].mean()
            child_post = post_split[post_split["cdk"] == child_cdk]["crop_area"].mean()

            if pd.isna(parent_post) or pd.isna(child_post) or (parent_post + child_post) == 0:
                continue

            # Ratio of child geography to parent geography
            ratio = child_post / (parent_post + child_post)

            # Identify pre-split parent records
            pre_split_parent = df[(df["cdk"] == parent_cdk) & (df["year"] < split_year)]

            if pre_split_parent.empty:
                continue

            # Create synthetic pre-split records for the child
            # Yield (rate) is assumed equal to parent. Area (absolute) is scaled by ratio.
            child_synthetic = pre_split_parent.copy()
            child_synthetic["cdk"] = child_cdk

            if "crop_area" in child_synthetic.columns:
                child_synthetic["crop_area"] = child_synthetic["crop_area"] * ratio

            # Scale production if it exists
            if "production" in child_synthetic.columns:
                child_synthetic["production"] = child_synthetic["production"] * ratio

            synthetic_records.append(child_synthetic)

        if synthetic_records:
            df = pd.concat([df] + synthetic_records, ignore_index=True)

        # Drop duplicates if multiple events created the same child-year, keep the latest
        df = df.drop_duplicates(subset=["cdk", "year"], keep="last")
        return df.sort_values(by=["cdk", "year"]).reset_index(drop=True)
