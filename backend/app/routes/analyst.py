"""
AI Analyst SSE endpoint.

Provides a streaming Server-Sent Events endpoint for the Claude-powered
agricultural analyst. Uses an agentic loop that continues calling tools
until Claude issues an end_turn stop reason.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional dependency in tests
    genai = None  # type: ignore[assignment]

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


def _get_model() -> genai.GenerativeModel | None:
    """Create a Gemini model instance if the API key is available."""
    if genai is None:
        return None
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    
    genai.configure(api_key=api_key)
    
    # Define Gemini-compatible tools from the existing handlers
    # We pass the handlers as tools directly; Gemini will use their docstrings/signatures
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=SYSTEM_PROMPT,
        tools=list(TOOL_HANDLERS.values())
    )


@router.post("/api/analyst")
async def analyst(req: AnalystRequest):
    """
    SSE streaming endpoint for the AI agricultural analyst.

    Accepts a natural language query, runs a Claude agentic loop
    with tool calls, and streams text deltas back as SSE events.
    """
    model = _get_model()
    if model is None:
        return StreamingResponse(
            _error_stream("AI analyst unavailable: GEMINI_API_KEY not configured"),
            media_type="text/event-stream",
        )

    async def stream():
        # Initialize a chat session
        chat = model.start_chat()
        user_query = req.query

        # Agentic loop: continue until no more tool calls
        for _loop in range(MAX_TOOL_LOOPS):
            try:
                # Send the message (or tool results) and stream the response
                response = await chat.send_message_async(user_query, stream=True)
                
                # Stream text deltas to the client
                async for chunk in response:
                    if chunk.text:
                        yield f"data: {json.dumps({'type': 'text', 'delta': chunk.text})}\n\n"

                # Check if Gemini wants to call a tool
                last_msg = chat.history[-1]
                tool_calls = [p.function_call for p in last_msg.parts if p.function_call]
                
                if not tool_calls:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

                # Process tool calls
                tool_responses = []
                conn = await asyncpg.connect(DATABASE_URL)
                try:
                    for fc in tool_calls:
                        handler = TOOL_HANDLERS.get(fc.name)
                        if handler is None:
                            tool_responses.append(
                                genai.types.Part(
                                    function_response=genai.types.FunctionResponse(
                                        name=fc.name,
                                        response={"error": f"Unknown tool: {fc.name}"}
                                    )
                                )
                            )
                            continue

                        try:
                            # Convert Gemini arguments to handler-compatible dict
                            args = dict(fc.args)
                            result = await handler(conn, **args)
                            
                            # Serialize Pydantic models/lists
                            if isinstance(result, list):
                                content = [r.model_dump() for r in result]
                            else:
                                content = result.model_dump()
                            
                            tool_responses.append(
                                genai.types.Part(
                                    function_response=genai.types.FunctionResponse(
                                        name=fc.name,
                                        response={"result": content}
                                    )
                                )
                            )
                        except Exception as e:
                            tool_responses.append(
                                genai.types.Part(
                                    function_response=genai.types.FunctionResponse(
                                        name=fc.name,
                                        response={"error": f"Tool execution failed: {str(e)}"}
                                    )
                                )
                            )
                finally:
                    await conn.close()

                # Feed the tool results back into the chat as the next 'user' message
                user_query = tool_responses

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

        # Exhausted loop iterations
        yield f"data: {json.dumps({'type': 'text', 'delta': 'I could not complete the analysis. Please try a narrower question.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _error_stream(message: str):
    """Yield an error event and done event."""
    yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
