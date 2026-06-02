"""
Tests for the Autonomous LLM Agent (ToolRegistry + agent_query).
"""

import pytest

from app.services.llm_service import (
    AnalyticsTool,
    LLMService,
    ToolRegistry,
    get_tool_registry,
)


# ---------------------------------------------------------------------------
# ToolRegistry Unit Tests
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """Tests for the ToolRegistry singleton."""

    def test_register_and_list(self):
        registry = ToolRegistry()

        async def dummy_tool(**kwargs):
            return {"result": "ok"}

        tool = AnalyticsTool(
            name="test_tool",
            description="A test tool",
            parameter_schema={"param1": {"type": "string"}},
            execute=dummy_tool,
        )
        registry.register(tool)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"
        assert tools[0]["description"] == "A test tool"

    def test_get_existing_tool(self):
        registry = ToolRegistry()

        async def dummy_tool(**kwargs):
            return {"result": "ok"}

        tool = AnalyticsTool(
            name="get_test",
            description="desc",
            parameter_schema={},
            execute=dummy_tool,
        )
        registry.register(tool)
        assert registry.get("get_test") is not None
        assert registry.get("get_test").name == "get_test"

    def test_get_missing_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_tool_names_property(self):
        registry = ToolRegistry()

        async def dummy(**kwargs):
            return {}

        registry.register(AnalyticsTool("a", "desc_a", {}, dummy))
        registry.register(AnalyticsTool("b", "desc_b", {}, dummy))
        assert set(registry.tool_names) == {"a", "b"}

    def test_global_singleton_exists(self):
        """The module-level get_tool_registry() should return a ToolRegistry."""
        registry = get_tool_registry()
        assert isinstance(registry, ToolRegistry)


# ---------------------------------------------------------------------------
# LLMService.agent_query Tests (without Gemini API key)
# ---------------------------------------------------------------------------


class TestLLMAgentQueryNoAPI:
    """Tests for agent_query when no LLM API key is configured (model=None)."""

    def test_init_without_api_key(self):
        service = LLMService()
        assert service.registry is not None

    @pytest.mark.asyncio
    async def test_agent_query_no_model_no_tools(self):
        service = LLMService()
        # Ensure the registry on this service instance is empty
        service.registry = ToolRegistry()

        result = await service.agent_query("What is the best crop?")
        assert "answer" in result
        assert "tool_calls" in result
        assert result["error"] is None
        # Without a model, _generate_narrative returns None
        assert result["answer"] == "Unable to generate an answer."

    @pytest.mark.asyncio
    async def test_agent_query_no_model_with_tools(self):
        """When model is None but tools are registered, should still return gracefully."""
        service = LLMService()
        service.registry = ToolRegistry()

        async def dummy(**kwargs):
            return {"data": 42}

        service.registry.register(
            AnalyticsTool("dummy", "A dummy tool", {}, dummy)
        )

        result = await service.agent_query("Analyze rice yield")
        assert "answer" in result
        # Without a model, the agent can't decide which tool to call,
        # so it should return a fallback message
        assert result["error"] is None
