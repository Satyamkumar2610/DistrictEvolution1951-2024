"use client";
/**
 * I-ASCAP AI Analyst Panel
 * File location: frontend/src/app/components/AIAnalyst.tsx
 *
 * Drop this component anywhere in your app — sidebar, drawer, or dedicated page.
 * It gives users a natural language interface to your agricultural database.
 *
 * Usage in a page:
 *   import AIAnalyst from "@/app/components/AIAnalyst";
 *   <AIAnalyst />
 *
 * Or open it as a slide-over panel from a button:
 *   const [open, setOpen] = useState(false);
 *   <button onClick={() => setOpen(true)}>Ask AI Analyst</button>
 *   {open && <AIAnalyst onClose={() => setOpen(false)} />}
 */

import { useState, useRef, useEffect } from "react";
import { resolvePublicApiOrigin } from "../services/api/config";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const EXAMPLE_QUESTIONS = [
  "Compare wheat yield in Punjab vs Haryana from 1990 to 2020",
  "What happened to crop production in Adilabad after the district split?",
  "Show me rice production trends in West Bengal over the last 30 years",
  "Which districts had the biggest yield drop during the 2002 drought?",
];

export default function AIAnalyst({ onClose }: { onClose?: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(text?: string) {
    const query = text ?? input.trim();
    if (!query || loading) return;

    const userMsg: Message = { role: "user", content: query };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput("");
    setLoading(true);

    let accumulated = "";

    try {
      const apiBase = resolvePublicApiOrigin();
      const res = await fetch(`${apiBase}/api/analyst`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, context: {} }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "text") {
              accumulated += event.delta;
              setMessages([
                ...updated,
                { role: "assistant", content: accumulated },
              ]);
            } else if (event.type === "done") {
              break;
            } else if (event.type === "error") {
              accumulated += `\n\n⚠️ ${event.message}`;
              setMessages([
                ...updated,
                { role: "assistant", content: accumulated },
              ]);
            }
          } catch {
            // Skip malformed SSE lines
          }
        }
      }

      // Ensure final message is set
      if (accumulated) {
        setMessages([...updated, { role: "assistant", content: accumulated }]);
      }
    } catch {
      setMessages([
        ...updated,
        {
          role: "assistant",
          content:
            "Failed to reach the analyst. Make sure the backend is running and your API key is set.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  /** Render message content with inline estimate badges */
  function renderContent(content: string) {
    // Split on words that indicate harmonized/estimated data
    const parts = content.split(/(\bestimate[ds]?\b|\bharmonized\b|\barea-weighted\b)/gi);
    return parts.map((part, i) => {
      const lower = part.toLowerCase();
      if (
        lower === "estimate" ||
        lower === "estimated" ||
        lower === "estimates" ||
        lower === "harmonized" ||
        lower === "area-weighted"
      ) {
        return (
          <span
            key={i}
            style={{
              background: "#FAEEDA",
              color: "#633806",
              padding: "1px 5px",
              borderRadius: "4px",
              fontSize: "11px",
              fontWeight: 600,
              marginLeft: "2px",
              marginRight: "2px",
            }}
          >
            {part}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  }

  return (
    <div className="analyst-panel">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="analyst-header">
        <div className="analyst-header-left">
          <div className="analyst-dot" />
          <span className="analyst-title">Agricultural Analyst</span>
          <span className="analyst-badge">AI</span>
        </div>
        {onClose && (
          <button className="analyst-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        )}
      </div>

      {/* ── Messages ───────────────────────────────────────────────────────── */}
      <div className="analyst-messages">
        {messages.length === 0 && (
          <div className="analyst-welcome">
            <p className="analyst-welcome-text">
              Ask me anything about Indian agriculture from 1966 to 2024.
              I have access to district-level yield, production, climate, and boundary data.
            </p>
            <div className="analyst-examples">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="analyst-example-btn"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`analyst-msg analyst-msg--${m.role}`}>
            <div className="analyst-msg-label">
              {m.role === "user" ? "You" : "Analyst"}
            </div>
            <div className="analyst-msg-content">
              {m.role === "assistant"
                ? m.content.split("\n").map((line, j) => (
                    <p key={j}>{renderContent(line)}</p>
                  ))
                : m.content.split("\n").map((line, j) => (
                    <p key={j}>{line}</p>
                  ))}
            </div>
          </div>
        ))}

        {loading && (
          <div className="analyst-msg analyst-msg--assistant">
            <div className="analyst-msg-label">Analyst</div>
            <div className="analyst-loading">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input ──────────────────────────────────────────────────────────── */}
      <div className="analyst-input-row">
        <input
          className="analyst-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
          placeholder="Ask about any district, crop, or year range..."
          disabled={loading}
        />
        <button
          className="analyst-send"
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
        >
          →
        </button>
      </div>

      {/* ── Styles ─────────────────────────────────────────────────────────── */}
      <style>{`
        .analyst-panel {
          display: flex;
          flex-direction: column;
          height: 100%;
          min-height: 500px;
          max-height: 800px;
          background: #0d1117;
          border: 1px solid #21262d;
          border-radius: 12px;
          font-family: 'IBM Plex Mono', 'Fira Code', monospace;
          color: #e6edf3;
          overflow: hidden;
        }

        .analyst-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 18px;
          border-bottom: 1px solid #21262d;
          background: #161b22;
        }

        .analyst-header-left {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .analyst-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #3fb950;
          box-shadow: 0 0 6px #3fb950;
          animation: pulse 2s infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }

        .analyst-title {
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.05em;
          color: #e6edf3;
        }

        .analyst-badge {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.1em;
          color: #58a6ff;
          background: rgba(88, 166, 255, 0.1);
          border: 1px solid rgba(88, 166, 255, 0.3);
          padding: 2px 6px;
          border-radius: 4px;
        }

        .analyst-close {
          background: none;
          border: none;
          color: #8b949e;
          cursor: pointer;
          font-size: 14px;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.2s;
        }
        .analyst-close:hover { background: #21262d; color: #e6edf3; }

        .analyst-messages {
          flex: 1;
          overflow-y: auto;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 16px;
          scrollbar-width: thin;
          scrollbar-color: #21262d transparent;
        }

        .analyst-welcome {
          text-align: center;
          padding: 20px 0;
        }

        .analyst-welcome-text {
          font-size: 13px;
          color: #8b949e;
          line-height: 1.6;
          margin-bottom: 20px;
        }

        .analyst-examples {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .analyst-example-btn {
          background: #161b22;
          border: 1px solid #21262d;
          color: #58a6ff;
          font-family: inherit;
          font-size: 12px;
          padding: 10px 14px;
          border-radius: 8px;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s;
          line-height: 1.4;
        }
        .analyst-example-btn:hover {
          background: #21262d;
          border-color: #58a6ff;
          color: #79c0ff;
        }

        .analyst-msg { display: flex; flex-direction: column; gap: 4px; }

        .analyst-msg-label {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }

        .analyst-msg--user .analyst-msg-label { color: #3fb950; }
        .analyst-msg--assistant .analyst-msg-label { color: #58a6ff; }

        .analyst-msg--user .analyst-msg-content {
          background: #161b22;
          border: 1px solid #21262d;
          border-radius: 8px 8px 8px 2px;
          padding: 12px 14px;
          font-size: 13px;
          color: #e6edf3;
          align-self: flex-start;
          max-width: 90%;
        }

        .analyst-msg--assistant .analyst-msg-content {
          background: rgba(88, 166, 255, 0.05);
          border: 1px solid rgba(88, 166, 255, 0.15);
          border-radius: 8px 8px 2px 8px;
          padding: 14px 16px;
          font-size: 13px;
          color: #c9d1d9;
          line-height: 1.7;
          max-width: 100%;
        }

        .analyst-msg-content p { margin: 0 0 6px; }
        .analyst-msg-content p:last-child { margin: 0; }

        .analyst-loading {
          display: flex;
          gap: 6px;
          padding: 14px 16px;
          background: rgba(88, 166, 255, 0.05);
          border: 1px solid rgba(88, 166, 255, 0.15);
          border-radius: 8px 8px 2px 8px;
          width: fit-content;
        }

        .analyst-loading span {
          display: block;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #58a6ff;
          animation: bounce 1.2s infinite;
        }
        .analyst-loading span:nth-child(2) { animation-delay: 0.2s; }
        .analyst-loading span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40% { transform: translateY(-6px); opacity: 1; }
        }

        .analyst-input-row {
          display: flex;
          gap: 8px;
          padding: 14px;
          border-top: 1px solid #21262d;
          background: #161b22;
        }

        .analyst-input {
          flex: 1;
          background: #0d1117;
          border: 1px solid #30363d;
          border-radius: 8px;
          color: #e6edf3;
          font-family: inherit;
          font-size: 13px;
          padding: 10px 14px;
          outline: none;
          transition: border-color 0.2s;
        }
        .analyst-input:focus { border-color: #58a6ff; }
        .analyst-input::placeholder { color: #484f58; }
        .analyst-input:disabled { opacity: 0.5; }

        .analyst-send {
          background: #238636;
          border: none;
          border-radius: 8px;
          color: #fff;
          font-size: 18px;
          width: 42px;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .analyst-send:hover:not(:disabled) { background: #2ea043; }
        .analyst-send:disabled { opacity: 0.4; cursor: not-allowed; }
      `}</style>
    </div>
  );
}
