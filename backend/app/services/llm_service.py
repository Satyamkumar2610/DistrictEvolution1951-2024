"""
LLM Service for generating human-readable, contextual insights from raw analytics data.
Uses the Anthropic API (if configured) to interpret model outputs.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore[assignment]


class LLMService:
    """Service to generate natural language narratives from structured analytics data."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if genai and self.api_key:
            genai.configure(api_key=self.api_key)
            # Use gemini-1.5-flash for fast, contextual insights
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None

    async def _generate_narrative(self, system_prompt: str, user_prompt: str) -> str | None:
        """Helper to call Gemini and return the text string."""
        if not self.model:
            return None

        try:
            # Combining system prompt into the context for Gemini
            full_prompt = f"{system_prompt}\n\nDATA:\n{user_prompt}"

            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=256,
                    temperature=0.3,
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Failed to generate LLM narrative: {e}")
            return None

    async def generate_climate_shock_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative for the Climate Shock Atlas."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert agricultural analyst. You are given a JSON report containing yield "
            "data and climate shocks (like droughts or floods) for a specific district. "
            "Write a concise, 2-3 sentence paragraph explaining the district's vulnerability to climate shocks "
            "and what the data means for a farmer or policymaker. Be specific, reference the numbers, "
            "and do not use formatting like bold or bullet points."
        )

        # Strip some verbose fields to save tokens
        clean_report = {
            "district": report.get("name"),
            "crop": report.get("crop"),
            "total_shock_years": report.get("total_shock_years"),
            "avg_loss_per_shock_pct": report.get("avg_loss_per_shock_pct"),
            "most_damaging_event_type": report.get("most_damaging_event_type"),
        }

        return await self._generate_narrative(system_prompt, json.dumps(clean_report))

    async def generate_forecast_validation_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative explaining the forecast model's historical backtesting performance."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert data scientist explaining a forecasting model's performance to an agricultural stakeholder. "
            "You are given a JSON report containing backtesting metrics (MAPE, bias, directional accuracy) "
            "for predicting crop yields. Write a concise, 2-3 sentence paragraph explaining if the model is reliable, "
            "if it tends to over/under predict, and what this means. "
            "Be specific, reference the metrics, and do not use formatting like bold or bullet points."
        )

        clean_report = {
            "district": report.get("cdk"),  # Using cdk as proxy if name not present at top level
            "crop": report.get("crop"),
            "metrics": report.get("metrics"),
        }

        return await self._generate_narrative(system_prompt, json.dumps(clean_report))

    async def generate_yield_frontier_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative for the Yield Frontier (SFA) analysis."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert agricultural economist. You are given a JSON report summarizing a "
            "Stochastic Frontier Analysis (SFA) for a specific crop across districts in a state. "
            "Write a concise, 2-3 sentence paragraph explaining the 'Technical Efficiency' of the state, "
            "the gap between observed yields and the theoretical frontier, and what it implies about farming practices. "
            "Be specific, reference the numbers, and do not use formatting like bold or bullet points."
        )

        clean_report = {
            "crop": report.get("crop"),
            "year": report.get("year"),
            "model_stats": report.get("model_stats"),
        }

        return await self._generate_narrative(system_prompt, json.dumps(clean_report))

    async def generate_resilience_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative for the PCA Resilience Composite analysis."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert agricultural resilience analyst. You are given a JSON report summarizing a "
            "PCA Composite Resilience Index computed across districts in a state. The index combines 8 variables: "
            "yield volatility (CV), drought retention, crop diversification (CDI), soil quality proxy, "
            "yield growth rate (CAGR), irrigation percentage, recovery speed after shocks, and input efficiency. "
            "Write a concise, 2-3 sentence paragraph interpreting the state's resilience profile, "
            "highlighting which factors drive resilience and which are weak points. "
            "Be specific, reference the numbers, and do not use formatting like bold or bullet points."
        )

        # Extract top and bottom districts for context
        districts = report.get("district_results", [])
        top_3 = districts[:3] if districts else []
        bottom_3 = districts[-3:] if len(districts) > 3 else []

        clean_report = {
            "region": report.get("region"),
            "n_districts": report.get("n_districts"),
            "mean_score": report.get("mean_score"),
            "total_variance_explained": report.get("total_variance_explained"),
            "variable_contributions": report.get("variable_contributions"),
            "top_resilient": [{"name": d.get("name"), "score": d.get("resilience_score"), "grade": d.get("grade")} for d in top_3],
            "least_resilient": [{"name": d.get("name"), "score": d.get("resilience_score"), "grade": d.get("grade")} for d in bottom_3],
        }

        return await self._generate_narrative(system_prompt, json.dumps(clean_report))

    async def generate_anomaly_context_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative hypothesizing root causes for detected anomalies."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert agricultural data analyst investigating anomalous data points. "
            "You are given a JSON report containing anomalies detected by an Isolation Forest model "
            "in a district's agricultural time series. The anomalies represent years where the combination "
            "of yield, area, and production deviated significantly from the district's historical pattern. "
            "Write a concise, 2-3 sentence paragraph hypothesizing why these anomalies may have occurred. "
            "Consider factors like climate events, policy changes, market shifts, or data quality issues. "
            "Be specific about the years and metrics, and do not use formatting like bold or bullet points."
        )

        return await self._generate_narrative(system_prompt, json.dumps(report))
