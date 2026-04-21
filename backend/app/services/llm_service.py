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
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


class LLMService:
    """Service to generate natural language narratives from structured analytics data."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key) if anthropic and self.api_key else None

    async def _generate_narrative(self, system_prompt: str, user_prompt: str) -> str | None:
        """Helper to call Claude and return the text string."""
        if not self.client:
            return None

        try:
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",  # Fast model for inline narratives
                max_tokens=256,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.warning(f"Failed to generate LLM narrative: {e}")
            return None

    async def generate_climate_shock_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative for the Climate Shock Atlas."""
        if not self.client:
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
        if not self.client:
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
        if not self.client:
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
