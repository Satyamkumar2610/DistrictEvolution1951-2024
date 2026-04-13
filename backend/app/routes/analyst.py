"""
AI Analyst SSE endpoint.

Provides a streaming Server-Sent Events endpoint for the Claude-powered
agricultural analyst. Uses an agentic loop that continues calling tools
until Claude issues an end_turn stop reason.
"""

from __future__ import annotations

import json
import os

import anthropic
import asyncpg
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.system_prompt import SYSTEM_PROMPT
from app.ai.tool_schemas import TOOL_SCHEMAS
from app.tools.compare import compare_metrics
from app.tools.lineage import get_lineage
from app.tools.metrics import query_metric

router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap")

TOOL_HANDLERS = {
    "query_metric": query_metric,
    "get_lineage": get_lineage,
    "compare_metrics": compare_metrics,
}

MAX_TOOL_LOOPS = 8


class AnalystRequest(BaseModel):
    """Request body for the analyst endpoint."""

    query: str
    context: dict = {}


def _get_client() -> anthropic.AsyncAnthropic | None:
    """Create an Anthropic client if the API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.AsyncAnthropic(api_key=api_key)


@router.post("/api/analyst")
async def analyst(req: AnalystRequest):
    """
    SSE streaming endpoint for the AI agricultural analyst.

    Accepts a natural language query, runs a Claude agentic loop
    with tool calls, and streams text deltas back as SSE events.
    """
    client = _get_client()
    if client is None:
        return StreamingResponse(
            _error_stream("AI analyst unavailable: ANTHROPIC_API_KEY not configured"),
            media_type="text/event-stream",
        )

    async def stream():
        messages = [{"role": "user", "content": req.query}]

        # Agentic loop: continue until stop_reason == "end_turn"
        for _loop in range(MAX_TOOL_LOOPS):
            try:
                async with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                ) as s:
                    # Stream text deltas to the client
                    async for event in s:
                        if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                            yield f"data: {json.dumps({'type': 'text', 'delta': event.delta.text})}\n\n"

                    msg = await s.get_final_message()

            except anthropic.APIError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # End of conversation
            if msg.stop_reason == "end_turn":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Tool use — execute tools and feed results back
            if msg.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": msg.content})

                tool_results = []
                conn = await asyncpg.connect(DATABASE_URL)
                try:
                    for block in msg.content:
                        if block.type == "tool_use":
                            handler = TOOL_HANDLERS.get(block.name)
                            if handler is None:
                                tool_results.append(
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": block.id,
                                        "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                                    }
                                )
                                continue

                            try:
                                result = await handler(conn, **block.input)
                                # Serialize Pydantic models
                                if isinstance(result, list):
                                    content = json.dumps([r.model_dump() for r in result])
                                else:
                                    content = json.dumps(result.model_dump())
                            except Exception as e:
                                content = json.dumps({"error": f"Tool execution failed: {str(e)}"})

                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": content,
                                }
                            )
                finally:
                    await conn.close()

                messages.append({"role": "user", "content": tool_results})

        # Exhausted loop iterations
        yield f"data: {json.dumps({'type': 'text', 'delta': 'I could not complete the analysis. Please try a narrower question.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _error_stream(message: str):
    """Yield an error event and done event."""
    yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
