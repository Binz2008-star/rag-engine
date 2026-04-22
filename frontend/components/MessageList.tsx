"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/lib/types";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex flex-col gap-5 px-4 py-6">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function EmptyState() {
  const examples = [
    "What does ECO Technology do?",
    "Summarize Robin Edwan's CV.",
    "Where is the company based?",
  ];

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-16 text-center">
      <div className="mb-4 h-12 w-12 rounded-full border border-border bg-muted" />
      <h2 className="text-lg font-semibold">Ask anything about your corpus</h2>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">
        Queries are grounded on your local FAISS index and answered by your
        Ollama model. Try one of these to get started:
      </p>
      <ul className="mt-4 flex flex-wrap justify-center gap-2">
        {examples.map((e) => (
          <li
            key={e}
            className="rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-muted-foreground"
          >
            {e}
          </li>
        ))}
      </ul>
    </div>
  );
}
