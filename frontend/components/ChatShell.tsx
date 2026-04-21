"use client";

import { useToast } from "@/components/ui/toast";
import { ApiError, postQuery } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { useCallback, useRef, useState } from "react";
import { ChatInput } from "./ChatInput";
import { Header } from "./Header";
import { MessageList } from "./MessageList";

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function ChatShell() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const { toast } = useToast();

  const patchMessage = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      );
    },
    [],
  );

  const handleSubmit = useCallback(
    async (question: string) => {
      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: question,
        createdAt: Date.now(),
      };
      const assistantId = createId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: Date.now(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await postQuery({ question }, controller.signal);
        patchMessage(assistantId, {
          content: res.answer,
          sources: res.sources,
          latencyMs: res.latency_ms,
        });
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          patchMessage(assistantId, {
            content:
              (prevContent(messages, assistantId) || "") + " [stopped]",
          });
          toast({
            kind: "info",
            title: "Generation stopped",
            description: "You cancelled the request.",
          });
        } else {
          const message =
            err instanceof ApiError
              ? `${err.status}: ${err.message}`
              : err instanceof Error
                ? err.message
                : "Request failed";
          patchMessage(assistantId, {
            error: message,
          });
          toast({
            kind: "error",
            title: "Request failed",
            description: message,
          });
        }
      } finally {
        setIsBusy(false);
        abortRef.current = null;
      }
    },
    [messages, patchMessage, toast],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleClear = useCallback(() => {
    if (isBusy) return;
    setMessages([]);
  }, [isBusy]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        onClearChat={handleClear}
        hasMessages={messages.length > 0}
      />

      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col">
        <MessageList messages={messages} />
      </main>

      <ChatInput
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        disabled={isBusy}
      />
    </div>
  );
}

function prevContent(messages: ChatMessage[], id: string): string | undefined {
  return messages.find((m) => m.id === id)?.content;
}
