"use client";

import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import { postAgentAnalyze, postQuery, postTradingAnalyze } from "@/lib/api";
import type { AgentAnalyzeResponse, TradingAnalyzeResponse } from "@/lib/types";

const SESSION_ID = "web-session-1";
const USER_ID = "web-user-1";

const TRADING_TERMS = [
  "trade", "trading", "signal", "buy", "sell", "stop loss", "take profit",
  "lot size", "risk reward", "forex", "crypto", "btc", "xauusd", "eurusd",
  "strategy", "backtest",
  "تداول", "صفقة", "شراء", "بيع", "وقف", "هدف", "مخاطرة", "ذهب", "يورو",
  "دولار", "بتكوين", "كريبتو", "استراتيجية", "تحليل", "حلل",
];

const AGENT_TERMS = [
  "plan", "roadmap", "steps", "workflow", "architecture", "strategy",
  "remind", "reminder", "schedule", "scheduled", "daily", "weekly",
  "tomorrow", "todo", "task", "remember", "recall", "memory", "context",
  "خطة", "خطوات", "سير العمل", "معمارية", "استراتيجية",
  "ذكرني", "تذكير", "جدولة", "يومي", "أسبوعي", "غدًا", "مهمة",
  "تذكر", "ذاكرة", "سياق",
];

type AssistantMessage =
  | { id: string; role: "assistant"; kind: "text"; content: string }
  | { id: string; role: "assistant"; kind: "trading"; trading: TradingAnalyzeResponse }
  | { id: string; role: "assistant"; kind: "agent"; agent: AgentAnalyzeResponse }
  | { id: string; role: "assistant"; kind: "error"; content: string };

type UserMessage = { id: string; role: "user"; kind: "text"; content: string };
type Message = UserMessage | AssistantMessage;

function isTradingPrompt(input: string): boolean {
  const normalized = input.toLowerCase().trim();
  return TRADING_TERMS.some((term) => normalized.includes(term));
}

function isAgentPrompt(input: string): boolean {
  const normalized = input.toLowerCase().trim();
  return AGENT_TERMS.some((term) => normalized.includes(term));
}

function makeId(): string {
  return crypto.randomUUID();
}

function TradingCard({ trading }: { trading: TradingAnalyzeResponse }) {
  const fields: Array<[string, string | null | undefined, string?]> = [
    ["Capability", trading.capability],
    ["Intent", trading.intent],
    ["Market", trading.market],
    ["Asset", trading.asset],
    ["Timeframe", trading.timeframe, "col-span-2"],
  ];

  return (
    <div className="w-full max-w-xl rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
            Trading Analysis
          </div>
          <p className="mt-1 truncate text-sm text-emerald-900">{trading.prompt}</p>
        </div>
        <span className="shrink-0 rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white">
          {trading.status}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        {fields.map(([label, value, span]) => (
          <div
            key={label}
            className={`rounded-xl border border-emerald-100 bg-white p-3 ${span ?? ""}`}
          >
            <div className="text-xs uppercase text-neutral-500">{label}</div>
            <div className="mt-1 font-medium text-neutral-900">{value ?? "N/A"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentAnalyzeResponse }) {
  return (
    <div className="w-full max-w-xl rounded-2xl border border-blue-200 bg-blue-50 p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wide text-blue-700">
            Agent Analysis
          </div>
          <p className="mt-1 truncate text-sm text-blue-900">{agent.prompt}</p>
        </div>
        <span className="shrink-0 rounded-full bg-blue-600 px-3 py-1 text-xs font-medium text-white">
          {agent.status}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl border border-blue-100 bg-white p-3">
          <div className="text-xs uppercase text-neutral-500">Capability</div>
          <div className="mt-1 font-medium text-neutral-900">{agent.capability}</div>
        </div>
        <div className="rounded-xl border border-blue-100 bg-white p-3">
          <div className="text-xs uppercase text-neutral-500">Intent</div>
          <div className="mt-1 font-medium text-neutral-900">{agent.intent}</div>
        </div>
        <div className="col-span-2 rounded-xl border border-blue-100 bg-white p-3">
          <div className="text-xs uppercase text-neutral-500">Summary</div>
          <div className="mt-1 text-neutral-900">{agent.summary}</div>
        </div>
        <div className="col-span-2 rounded-xl border border-blue-100 bg-white p-3">
          <div className="text-xs uppercase text-neutral-500">Suggested Tools</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {agent.suggested_tools.length > 0 ? (
              agent.suggested_tools.map((tool) => (
                <span
                  key={tool}
                  className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800"
                >
                  {tool}
                </span>
              ))
            ) : (
              <span className="text-sm text-neutral-500">N/A</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 rounded-2xl border border-neutral-200 bg-white px-4 py-3 shadow-sm">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="inline-block h-2 w-2 animate-bounce rounded-full bg-neutral-400"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

export default function ChatShell() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const question = input.trim();
      if (!question || isLoading) return;

      const userMessage: UserMessage = {
        id: makeId(),
        role: "user",
        kind: "text",
        content: question,
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");

      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      setIsLoading(true);

      try {
        if (isTradingPrompt(question)) {
          const result = await postTradingAnalyze({
            question,
            session_id: SESSION_ID,
            user_id: USER_ID,
          });

          setMessages((prev) => [
            ...prev,
            { id: makeId(), role: "assistant", kind: "trading", trading: result },
          ]);
          return;
        }

        if (isAgentPrompt(question)) {
          const result = await postAgentAnalyze({
            question,
            session_id: SESSION_ID,
            user_id: USER_ID,
          });

          setMessages((prev) => [
            ...prev,
            { id: makeId(), role: "assistant", kind: "agent", agent: result },
          ]);
          return;
        }

        const result = await postQuery({
          question,
          session_id: SESSION_ID,
          user_id: USER_ID,
        });

        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: "assistant", kind: "text", content: result.answer },
        ]);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Request failed unexpectedly.";
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: "assistant", kind: "error", content: message },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        event.currentTarget.form?.requestSubmit();
      }
    },
    [],
  );

  return (
    <div className="flex h-screen w-full items-center justify-center bg-neutral-100 p-6">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-neutral-300 bg-white shadow-sm">
        <header className="border-b border-neutral-200 px-6 py-4">
          <h1 className="text-lg font-semibold text-neutral-900">RAG Assistant</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Ask a document question, trading analysis question, or agent planning question.
          </p>
        </header>

        <main className="flex-1 overflow-y-auto bg-neutral-50 px-6 py-5">
          {messages.length === 0 && !isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-md text-center text-sm text-neutral-500">
                Try:
                <div className="mt-3 space-y-2 rounded-lg bg-white p-3 text-left shadow-sm">
                  <p>What does ECO do?</p>
                  <p>Analyze EURUSD on H1</p>
                  <p>Create a plan to add scheduled task support</p>
                </div>
                <p className="mt-3 text-xs text-neutral-400">
                  Press <kbd className="rounded border border-neutral-300 px-1 py-0.5 text-xs">Enter</kbd> to send
                  &nbsp;·&nbsp;
                  <kbd className="rounded border border-neutral-300 px-1 py-0.5 text-xs">Shift+Enter</kbd> for newline
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message) => {
                if (message.role === "user") {
                  return (
                    <div key={message.id} className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl bg-neutral-900 px-4 py-3 text-sm whitespace-pre-wrap text-white shadow-sm">
                        {message.content}
                      </div>
                    </div>
                  );
                }

                if (message.kind === "trading") {
                  return (
                    <div key={message.id} className="flex justify-start">
                      <TradingCard trading={message.trading} />
                    </div>
                  );
                }

                if (message.kind === "agent") {
                  return (
                    <div key={message.id} className="flex justify-start">
                      <AgentCard agent={message.agent} />
                    </div>
                  );
                }

                if (message.kind === "error") {
                  return (
                    <div key={message.id} className="flex justify-start">
                      <div className="max-w-[80%] rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">
                        <span className="mr-1.5 font-semibold">Error:</span>
                        {message.content}
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={message.id} className="flex justify-start">
                    <div className="max-w-[80%] rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm whitespace-pre-wrap text-neutral-900 shadow-sm">
                      {message.content}
                    </div>
                  </div>
                );
              })}

              {isLoading && <LoadingBubble />}
              <div ref={scrollAnchorRef} />
            </div>
          )}
        </main>

        <form
          onSubmit={handleSubmit}
          className="border-t border-neutral-200 bg-white px-4 py-4"
        >
          <div className="flex items-end gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              rows={2}
              onChange={(e) => {
                setInput(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Ask about ECO, analyze EURUSD, or create a plan..."
              disabled={isLoading}
              className="min-h-[56px] max-h-[200px] flex-1 resize-none rounded-xl border border-neutral-300 px-4 py-3 text-sm text-neutral-900 outline-none transition-colors focus:border-neutral-500 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="h-[56px] rounded-xl bg-neutral-900 px-5 text-sm font-medium text-white transition-opacity disabled:opacity-40"
            >
              {isLoading ? "..." : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
