"""
LLM Service for generating human-readable, contextual insights from raw analytics data.

Supports two modes:
  1. **Narrative Generation** — static prompt → text output (original behaviour).
  2. **Autonomous Agent** — the LLM is given a registry of internal analytics tools
     and can decide which tools to invoke to answer a complex user query.
"""

import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Tool Registry for Autonomous Agent
# ---------------------------------------------------------------------------


@dataclass
class AnalyticsTool:
    """Descriptor for a callable analytics tool the agent can invoke."""

    name: str
    description: str
    parameter_schema: dict[str, Any]  # JSON-Schema-style {param: {type, description}}
    execute: Callable[..., Awaitable[dict[str, Any]]]


class ToolRegistry:
    """Registry of analytics tools available to the autonomous agent."""

    def __init__(self) -> None:
        self._tools: dict[str, AnalyticsTool] = {}

    def register(self, tool: AnalyticsTool) -> None:
        """Register a tool for the agent to use."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> AnalyticsTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable manifest of all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameter_schema,
            }
            for t in self._tools.values()
        ]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


# Module-level singleton so services can register tools at import time.
_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry."""
    return _tool_registry


class LLMService:
    """Service to generate natural language narratives from structured analytics data."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model: Any = None
        if genai and self.api_key:
            genai.configure(api_key=self.api_key)
            # Use gemini-1.5-flash for fast, contextual insights
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.registry = get_tool_registry()

    async def _generate_narrative(self, system_prompt: str, user_prompt: str) -> str | None:
        """Helper to call Gemini and return the text string."""
        if not self.model or not genai:
            return None

        try:
            # Combining system prompt into the context for Gemini
            full_prompt = f"{system_prompt}\n\nDATA:\n{user_prompt}"

            response = await self.model.generate_content_async(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=256,
                    temperature=0.3,
                ),
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
            "top_resilient": [
                {"name": d.get("name"), "score": d.get("resilience_score"), "grade": d.get("grade")} for d in top_3
            ],
            "least_resilient": [
                {"name": d.get("name"), "score": d.get("resilience_score"), "grade": d.get("grade")} for d in bottom_3
            ],
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

    async def generate_backcast_narrative(self, report: dict[str, Any]) -> str | None:
        """Generate a narrative interpreting yield backcast model results and conservation checks."""
        if not self.model:
            return None

        system_prompt = (
            "You are an expert data scientist explaining an ML yield backcasting model to an agricultural stakeholder. "
            "You are given a JSON report containing the model's predictions for how a parent district's historical yield "
            "was disaggregated into its child districts. "
            "Write a concise, 2-3 sentence paragraph explaining which ML method was used, whether the model's "
            "conservation check passed (i.e. if the child yields sum correctly to the parent yield), and what "
            "level of confidence we have in the results. "
            "Be specific, reference the method and conservation error percentage, and do not use formatting like bold or bullet points."
        )

        clean_report = {
            "parent_district": report.get("parent_cdk"),
            "crop": report.get("crop"),
            "primary_method": report.get("method"),
            "conservation_check": report.get("conservation_check"),
        }

        return await self._generate_narrative(system_prompt, json.dumps(clean_report))

    # ------------------------------------------------------------------
    # Autonomous Agent Mode
    # ------------------------------------------------------------------

    async def agent_query(
        self,
        user_question: str,
        context: dict[str, Any] | None = None,
        max_tool_rounds: int = 3,
    ) -> dict[str, Any]:
        """
        Answer a complex user question by autonomously selecting and executing
        analytics tools, then synthesising the results into a final answer.

        Returns a dict with:
            - "answer": str — the final natural-language answer
            - "tool_calls": list[dict] — log of tools invoked and their results
            - "error": str | None — error message if something went wrong
        """
        tool_call_log: list[dict[str, Any]] = []
        tool_results_context: list[dict[str, Any]] = []

        available_tools = self.registry.list_tools()

        if not available_tools:
            # No tools registered — fall back to plain narrative
            answer = await self._generate_narrative(
                "You are an agricultural data analyst. Answer the user's question "
                "using the provided context data.",
                json.dumps({"question": user_question, "context": context or {}}),
            )
            return {"answer": answer or "Unable to generate an answer.", "tool_calls": [], "error": None}

        # Build the agent system prompt with tool descriptions
        tools_description = json.dumps(available_tools, indent=2)
        system_prompt = (
            "You are an autonomous agricultural analytics agent. "
            "You have access to the following tools:\n"
            f"{tools_description}\n\n"
            "When you need to call a tool, respond with EXACTLY this JSON format "
            "(and nothing else):\n"
            '{"tool": "<tool_name>", "args": {<arguments>}}\n\n'
            "When you have enough information to answer the user, respond with "
            "EXACTLY this JSON format:\n"
            '{"answer": "<your final answer>"}\n\n'
            "Always respond with valid JSON only. No markdown, no extra text."
        )

        conversation = f"User question: {user_question}"
        if context:
            conversation += f"\nContext: {json.dumps(context, default=str)}"

        for _round in range(max_tool_rounds):
            raw = await self._generate_narrative(system_prompt, conversation)
            if not raw:
                break

            # Parse the agent's response
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # If the model returned plain text, treat it as the final answer
                return {"answer": raw, "tool_calls": tool_call_log, "error": None}

            # Check if the agent decided to give a final answer
            if "answer" in parsed:
                return {"answer": parsed["answer"], "tool_calls": tool_call_log, "error": None}

            # Otherwise, execute the requested tool
            tool_name = parsed.get("tool")
            tool_args = parsed.get("args", {})
            tool = self.registry.get(tool_name) if tool_name else None

            if tool is None:
                conversation += f"\nSystem: Tool '{tool_name}' not found. Available: {self.registry.tool_names}"
                continue

            try:
                result = await tool.execute(**tool_args)
                tool_call_log.append({"tool": tool_name, "args": tool_args, "result": result})
                tool_results_context.append({"tool": tool_name, "result": result})
                conversation += f"\nTool result ({tool_name}): {json.dumps(result, default=str)}"
            except Exception as e:
                error_msg = f"Tool '{tool_name}' failed: {e}"
                logger.warning(error_msg)
                tool_call_log.append({"tool": tool_name, "args": tool_args, "error": str(e)})
                conversation += f"\nSystem: {error_msg}"

        # If we exhausted rounds without a final answer, synthesise one
        if tool_results_context:
            synthesis_prompt = (
                "Based on the tool results below, provide a concise, data-backed answer "
                "to the user's question. Respond in plain text (no JSON).\n\n"
                f"Question: {user_question}\n"
                f"Tool results: {json.dumps(tool_results_context, default=str)}"
            )
            answer = await self._generate_narrative(
                "You are an expert agricultural analyst.", synthesis_prompt
            )
        else:
            answer = "I was unable to gather sufficient data to answer your question."

        return {"answer": answer or "Unable to generate an answer.", "tool_calls": tool_call_log, "error": None}
