import { NextRequest, NextResponse } from "next/server";
import { GoogleGenerativeAI, Part } from "@google/generative-ai";

import { resolveServerApiOrigin, toApiV1Url } from "../../services/api/config";

export const runtime = "nodejs";

const BACKEND_API_BASE = toApiV1Url(resolveServerApiOrigin());
const MODEL = "claude-sonnet-4-20250514";
const MAX_TOOL_LOOPS = 8;

type ToolInput = Record<string, unknown>;
type AnalystMessage = {
  role: "user" | "assistant";
  content: string;
};

function getGeminiModel(systemPrompt: string) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return null;
  }
  const genAI = new GoogleGenerativeAI(apiKey);
  return genAI.getGenerativeModel({
    model: "gemini-1.5-pro",
    systemInstruction: systemPrompt,
    tools: [{ functionDeclarations: GEMINI_TOOLS }],
  });
}

function toQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      searchParams.set(key, value.join(","));
      continue;
    }
    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function fetchBackend(path: string): Promise<unknown> {
  const response = await fetch(`${BACKEND_API_BASE}${path}`, {
    method: "GET",
    cache: "no-store",
  });

  const contentType = response.headers.get("content-type") ?? "";

  if (!response.ok) {
    const detail = contentType.includes("application/json")
      ? JSON.stringify(await response.json().catch(() => ({ error: "Unknown error" })))
      : await response.text().catch(() => "Unknown error");
    return {
      error: `Backend error ${response.status}`,
      detail,
      path,
    };
  }

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return {
    data: await response.text(),
    path,
  };
}

const GEMINI_TOOLS = [
  {
    name: "search_entities",
    description:
      "Search districts and states by name. Use this first when the user does not know the district CDK or exact state spelling.",
    parameters: {
      type: "OBJECT",
      properties: {
        q: { type: "STRING", description: "Search query such as Bihar or Patna." },
        type: {
          type: "STRING",
          enum: ["all", "district", "state"],
          description: "Filter result types when needed.",
        },
        limit: { type: "NUMBER", description: "Maximum number of matches to return." },
      },
      required: ["q"],
    },
  },
  {
    name: "get_metric_history",
    description:
      "Get yearly area, production, and yield history for a district. Prefer cdk when available; otherwise supply district and optionally state.",
    parameters: {
      type: "OBJECT",
      properties: {
        cdk: { type: "STRING" },
        district: { type: "STRING" },
        state: { type: "STRING" },
        crop: { type: "STRING" },
      },
      required: ["crop"],
    },
  },
  {
    name: "get_state_overview",
    description:
      "Get a state-level overview for a crop, including district counts, benchmarks, and top/bottom performers.",
    parameters: {
      type: "OBJECT",
      properties: {
        state_name: { type: "STRING" },
        crop: { type: "STRING" },
        year: { type: "NUMBER" },
      },
      required: ["state_name"],
    },
  },
  {
    name: "get_split_events_for_state",
    description:
      "List district split events for a state, including parent and child CDKs needed for split-impact analysis.",
    parameters: {
      type: "OBJECT",
      properties: {
        state: { type: "STRING" },
      },
      required: ["state"],
    },
  },
  {
    name: "analyze_split_impact",
    description:
      "Run before/after split-impact analysis for a parent district and child districts. Use split events first if the CDKs are not known.",
    parameters: {
      type: "OBJECT",
      properties: {
        parent_cdk: { type: "STRING" },
        child_cdks: {
          type: "ARRAY",
          items: { type: "STRING" },
        },
        split_year: { type: "NUMBER" },
        crop: { type: "STRING" },
        metric: {
          type: "STRING",
          enum: ["yield", "area", "production"],
        },
        mode: {
          type: "STRING",
          enum: ["before_after", "entity_comparison"],
        },
      },
      required: ["parent_cdk", "child_cdks", "split_year"],
    },
  },
  {
    name: "get_yield_trend",
    description:
      "Get district yield trend analysis including CAGR and volatility over a year range.",
    parameters: {
      type: "OBJECT",
      properties: {
        cdk: { type: "STRING" },
        crop: { type: "STRING" },
        start_year: { type: "NUMBER" },
        end_year: { type: "NUMBER" },
      },
      required: ["cdk"],
    },
  },
  {
    name: "get_rainfall",
    description:
      "Get historic rainfall normals for a district and state. Use for climate context, not real-time weather.",
    parameters: {
      type: "OBJECT",
      properties: {
        state: { type: "STRING" },
        district: { type: "STRING" },
      },
      required: ["state", "district"],
    },
  },
  {
    name: "get_district_report",
    description:
      "Fetch a comprehensive district profile report with historical yield, area, production, and state benchmark context.",
    parameters: {
      type: "OBJECT",
      properties: {
        cdk: { type: "STRING" },
        crop: { type: "STRING" },
      },
      required: ["cdk"],
    },
  },
];

async function callBackend(toolName: string, input: ToolInput): Promise<unknown> {
  switch (toolName) {
    case "search_entities":
      return fetchBackend(
        `/search${toQueryString({
          q: input.q,
          type: input.type ?? "all",
          limit: input.limit ?? 10,
        })}`,
      );
    case "get_metric_history":
      return fetchBackend(
        `/metrics/history${toQueryString({
          cdk: input.cdk,
          district: input.district,
          state: input.state,
          crop: input.crop ?? "wheat",
        })}`,
      );
    case "get_state_overview":
      if (!input.state_name) {
        return { error: "state_name is required" };
      }
      return fetchBackend(
        `/states/${encodeURIComponent(String(input.state_name))}/overview${toQueryString({
          crop: input.crop ?? "wheat",
          year: input.year,
        })}`,
      );
    case "get_split_events_for_state":
      return fetchBackend(
        `/analysis/split-impact/districts${toQueryString({
          state: input.state,
        })}`,
      );
    case "analyze_split_impact":
      return fetchBackend(
        `/analysis/split-impact/analysis${toQueryString({
          parent: input.parent_cdk,
          children: input.child_cdks,
          splitYear: input.split_year,
          crop: input.crop ?? "wheat",
          metric: input.metric ?? "yield",
          mode: input.mode ?? "before_after",
        })}`,
      );
    case "get_yield_trend":
      return fetchBackend(
        `/analytics/yield-trend${toQueryString({
          cdk: input.cdk,
          crop: input.crop ?? "rice",
          start_year: input.start_year ?? 1990,
          end_year: input.end_year ?? 2020,
        })}`,
      );
    case "get_rainfall":
      return fetchBackend(
        `/climate/rainfall${toQueryString({
          state: input.state,
          district: input.district,
        })}`,
      );
    case "get_district_report":
      return fetchBackend(
        `/reports/district-profile${toQueryString({
          cdk: input.cdk,
          crop: input.crop ?? "wheat",
          format: "json",
        })}`,
      );
    default:
      return { error: `Unknown tool: ${toolName}` };
  }
}

function normalizeMessages(messages: unknown): any[] {
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages
    .filter((message): message is AnalystMessage => {
      return (
        typeof message === "object" &&
        message !== null &&
        "role" in message &&
        "content" in message
      );
    })
    .map((message) => {
      const role = message.role === "assistant" ? "model" : "user";
      return {
        role,
        parts: [{ text: String(message.content ?? "") }],
      };
    })
    .slice(-12);
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const history = normalizeMessages(body.messages);

  if (history.length === 0) {
    return NextResponse.json(
      { error: "At least one user message is required." },
      { status: 400 }
    );
  }

  const systemPrompt = `You are the I-ASCAP agricultural analyst.

You answer questions using only the live I-ASCAP API tools.

Rules:
- Use tools before making factual claims.
- If a district CDK is unknown, call search_entities first.
- For split questions, call get_split_events_for_state before analyze_split_impact unless the exact parent and child CDKs are already known.
- Be explicit about years, crops, and whether a result is district-level, state-level, or split-event analysis.
- Treat rainfall data as historic normals, not real-time weather.
- When the data is insufficient or ambiguous, say so directly.`;

  const model = getGeminiModel(systemPrompt);
  if (!model) {
    return NextResponse.json(
      { error: "AI analyst is unavailable because GEMINI_API_KEY is not configured." },
      { status: 503 }
    );
  }

  // Remove the last message from history as it will be our first 'sendMessage'
  const lastMessage = history.pop();
  const chat = model.startChat({ history });
  
  let currentResponse = await chat.sendMessage(lastMessage.parts[0].text);
  let finalText = "";

  for (let i = 0; i < MAX_TOOL_LOOPS; i += 1) {
    const call = currentResponse.response.functionCalls()?.[0];
    
    if (!call) {
      finalText = currentResponse.response.text();
      break;
    }

    // Execute tool
    const result = await callBackend(call.name, call.args as ToolInput);

    // Feed result back
    currentResponse = await chat.sendMessage([
      {
        functionResponse: {
          name: call.name,
          response: result,
        },
      },
    ]);
  }

  if (!finalText) {
    finalText =
      "I could not complete the analysis loop. Please try a narrower question with a district, state, crop, or year range.";
  }

  return NextResponse.json({ response: finalText });
}
