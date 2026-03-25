/**
 * I-ASCAP AI Analyst — Next.js API Route
 * File location: frontend/src/app/api/analyst/route.ts
 *
 * This route sits between your React frontend and the Anthropic API.
 * It defines all the tools Claude can call (which map to your FastAPI endpoints)
 * and handles the agentic loop — Claude calls a tool → we fetch real data →
 * we send it back → Claude synthesizes a final answer.
 *
 * Setup:
 *   Add to frontend/.env.local:
 *     ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
 *     ASCAP_API_URL=http://localhost:8000   (or your deployed backend URL)
 */

import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const BACKEND = process.env.ASCAP_API_URL ?? "http://localhost:8000";

// ── Tool definitions — mirrors your FastAPI endpoints ─────────────────────────
const TOOLS: Anthropic.Tool[] = [
  {
    name: "get_all_districts",
    description: "Fetch all districts available in the I-ASCAP database.",
    input_schema: { type: "object" as const, properties: {}, required: [] },
  },
  {
    name: "get_crop_data",
    description:
      "Get crop yield / production / area data for a district across a year range.",
    input_schema: {
      type: "object" as const,
      properties: {
        district: { type: "string" },
        start_year: { type: "number" },
        end_year: { type: "number" },
        crop: { type: "string" },
        metric: { type: "string", enum: ["yield", "production", "area"] },
      },
      required: ["district", "start_year", "end_year"],
    },
  },
  {
    name: "get_district_lineage",
    description:
      "Get the boundary split/merge lineage of a district (e.g. Adilabad → Nirmal).",
    input_schema: {
      type: "object" as const,
      properties: { district: { type: "string" } },
      required: ["district"],
    },
  },
  {
    name: "compare_districts",
    description:
      "Compare agricultural performance across 2+ districts for a metric and year range.",
    input_schema: {
      type: "object" as const,
      properties: {
        districts: { type: "array", items: { type: "string" } },
        metric: { type: "string", enum: ["yield", "production", "area"] },
        start_year: { type: "number" },
        end_year: { type: "number" },
        crop: { type: "string" },
      },
      required: ["districts", "metric", "start_year", "end_year"],
    },
  },
  {
    name: "get_climate_data",
    description:
      "Get rainfall and temperature data for a district — useful to correlate climate with yield.",
    input_schema: {
      type: "object" as const,
      properties: {
        district: { type: "string" },
        start_year: { type: "number" },
        end_year: { type: "number" },
      },
      required: ["district", "start_year", "end_year"],
    },
  },
  {
    name: "get_state_summary",
    description: "Aggregate agricultural data for an entire state across its districts.",
    input_schema: {
      type: "object" as const,
      properties: {
        state: { type: "string" },
        start_year: { type: "number" },
        end_year: { type: "number" },
        metric: { type: "string", enum: ["yield", "production", "area"] },
      },
      required: ["state", "start_year", "end_year"],
    },
  },
];

// ── Call the actual FastAPI backend ───────────────────────────────────────────
async function callBackend(toolName: string, input: Record<string, unknown>): Promise<unknown> {
  const routes: Record<string, () => Promise<Response>> = {
    get_all_districts: () => fetch(`${BACKEND}/api/districts`),
    get_crop_data: () =>
      fetch(`${BACKEND}/api/crop-data?` + new URLSearchParams(input as Record<string, string>)),
    get_district_lineage: () =>
      fetch(`${BACKEND}/api/lineage/${input.district}`),
    compare_districts: () =>
      fetch(`${BACKEND}/api/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
    get_climate_data: () =>
      fetch(`${BACKEND}/api/climate?` + new URLSearchParams(input as Record<string, string>)),
    get_state_summary: () =>
      fetch(`${BACKEND}/api/state-summary?` + new URLSearchParams(input as Record<string, string>)),
  };

  const fetcher = routes[toolName];
  if (!fetcher) return { error: `Unknown tool: ${toolName}` };

  try {
    const res = await fetcher();
    if (!res.ok) return { error: `Backend error ${res.status}: ${await res.text()}` };
    return await res.json();
  } catch (e) {
    return { error: `Cannot reach backend at ${BACKEND}. Is it running?` };
  }
}

// ── Agentic loop ──────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  const { messages } = await req.json();

  const systemPrompt = `You are the I-ASCAP Agricultural Analyst — an expert in Indian agriculture 
from 1966 to 2024. You have direct access to a geospatial database of district-level crop yield, 
production, and area data across all Indian districts.

When answering questions:
- Always use tools to fetch REAL data before drawing conclusions
- If a district was split (e.g. Adilabad → Nirmal), use get_district_lineage first to understand the boundary history
- Cite specific numbers and years from the data
- Highlight trends, anomalies, and climate correlations where relevant
- Be concise but data-driven

You are embedded in the I-ASCAP platform. Users are researchers, policymakers, and farmers.`;

  let currentMessages: Anthropic.MessageParam[] = messages;
  let finalText = "";

  // Agentic loop: keep going until Claude stops calling tools
  for (let i = 0; i < 8; i++) {
    const response = await anthropic.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 2048,
      system: systemPrompt,
      tools: TOOLS,
      messages: currentMessages,
    });

    if (response.stop_reason === "end_turn") {
      finalText = response.content
        .filter((b) => b.type === "text")
        .map((b) => (b as Anthropic.TextBlock).text)
        .join("");
      break;
    }

    if (response.stop_reason === "tool_use") {
      // Execute all tool calls in parallel
      const toolUseBlocks = response.content.filter(
        (b): b is Anthropic.ToolUseBlock => b.type === "tool_use"
      );

      const toolResults = await Promise.all(
        toolUseBlocks.map(async (block) => {
          const result = await callBackend(block.name, block.input as Record<string, unknown>);
          return {
            type: "tool_result" as const,
            tool_use_id: block.id,
            content: JSON.stringify(result),
          };
        })
      );

      // Add assistant turn + tool results back into message history
      currentMessages = [
        ...currentMessages,
        { role: "assistant" as const, content: response.content },
        { role: "user" as const, content: toolResults },
      ];
    }
  }

  return NextResponse.json({ response: finalText });
}
