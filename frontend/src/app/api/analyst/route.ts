import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

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

function getAnthropicClient(): Anthropic | null {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return null;
  }
  return new Anthropic({ apiKey });
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

const TOOLS: Anthropic.Tool[] = [
  {
    name: "search_entities",
    description:
      "Search districts and states by name. Use this first when the user does not know the district CDK or exact state spelling.",
    input_schema: {
      type: "object",
      properties: {
        q: { type: "string", description: "Search query such as Bihar or Patna." },
        type: {
          type: "string",
          enum: ["all", "district", "state"],
          description: "Filter result types when needed.",
        },
        limit: { type: "number", description: "Maximum number of matches to return." },
      },
      required: ["q"],
    },
  },
  {
    name: "get_metric_history",
    description:
      "Get yearly area, production, and yield history for a district. Prefer cdk when available; otherwise supply district and optionally state.",
    input_schema: {
      type: "object",
      properties: {
        cdk: { type: "string" },
        district: { type: "string" },
        state: { type: "string" },
        crop: { type: "string" },
      },
      required: ["crop"],
    },
  },
  {
    name: "get_state_overview",
    description:
      "Get a state-level overview for a crop, including district counts, benchmarks, and top/bottom performers.",
    input_schema: {
      type: "object",
      properties: {
        state_name: { type: "string" },
        crop: { type: "string" },
        year: { type: "number" },
      },
      required: ["state_name"],
    },
  },
  {
    name: "get_split_events_for_state",
    description:
      "List district split events for a state, including parent and child CDKs needed for split-impact analysis.",
    input_schema: {
      type: "object",
      properties: {
        state: { type: "string" },
      },
      required: ["state"],
    },
  },
  {
    name: "analyze_split_impact",
    description:
      "Run before/after split-impact analysis for a parent district and child districts. Use split events first if the CDKs are not known.",
    input_schema: {
      type: "object",
      properties: {
        parent_cdk: { type: "string" },
        child_cdks: {
          type: "array",
          items: { type: "string" },
        },
        split_year: { type: "number" },
        crop: { type: "string" },
        metric: {
          type: "string",
          enum: ["yield", "area", "production"],
        },
        mode: {
          type: "string",
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
    input_schema: {
      type: "object",
      properties: {
        cdk: { type: "string" },
        crop: { type: "string" },
        start_year: { type: "number" },
        end_year: { type: "number" },
      },
      required: ["cdk"],
    },
  },
  {
    name: "get_rainfall",
    description:
      "Get historic rainfall normals for a district and state. Use for climate context, not real-time weather.",
    input_schema: {
      type: "object",
      properties: {
        state: { type: "string" },
        district: { type: "string" },
      },
      required: ["state", "district"],
    },
  },
  {
    name: "get_district_report",
    description:
      "Fetch a comprehensive district profile report with historical yield, area, production, and state benchmark context.",
    input_schema: {
      type: "object",
      properties: {
        cdk: { type: "string" },
        crop: { type: "string" },
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

function normalizeMessages(messages: unknown): Anthropic.MessageParam[] {
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages
    .filter((message): message is AnalystMessage => {
      return (
        typeof message === "object" &&
        message !== null &&
        ("role" in message) &&
        ("content" in message)
      );
    })
    .map((message): Anthropic.MessageParam => {
      const role: "user" | "assistant" =
        message.role === "assistant" ? "assistant" : "user";

      return {
        role,
        content:
          typeof message.content === "string"
            ? message.content
            : String(message.content ?? ""),
      };
    })
    .slice(-12);
}

export async function POST(req: NextRequest) {
  const anthropic = getAnthropicClient();
  if (!anthropic) {
    return NextResponse.json(
      { error: "AI analyst is unavailable because ANTHROPIC_API_KEY is not configured." },
      { status: 503 },
    );
  }

  const body = await req.json().catch(() => ({}));
  const currentMessages = normalizeMessages(body.messages);

  if (currentMessages.length === 0) {
    return NextResponse.json(
      { error: "At least one user message is required." },
      { status: 400 },
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

  let conversation: Anthropic.MessageParam[] = currentMessages;
  let finalText = "";

  for (let i = 0; i < MAX_TOOL_LOOPS; i += 1) {
    const response = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 2048,
      system: systemPrompt,
      tools: TOOLS,
      messages: conversation,
    });

    if (response.stop_reason === "end_turn") {
      finalText = response.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("\n")
        .trim();
      break;
    }

    if (response.stop_reason !== "tool_use") {
      continue;
    }

    const toolUseBlocks = response.content.filter(
      (block): block is Anthropic.ToolUseBlock => block.type === "tool_use",
    );

    const toolResults = await Promise.all(
      toolUseBlocks.map(async (block) => {
        const result = await callBackend(block.name, block.input as ToolInput);
        return {
          type: "tool_result" as const,
          tool_use_id: block.id,
          content: JSON.stringify(result),
        };
      }),
    );

    conversation = [
      ...conversation,
      { role: "assistant", content: response.content },
      { role: "user", content: toolResults },
    ];
  }

  if (!finalText) {
    finalText =
      "I could not complete the analysis loop. Please try a narrower question with a district, state, crop, or year range.";
  }

  return NextResponse.json({ response: finalText });
}
