"use client";

import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/types";
import { cn, formatDuration } from "@/lib/utils";
import { Bot, Copy, User } from "lucide-react";
import { useState } from "react";
import { SourceList } from "./SourceList";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* noop */
    }
  };

  return (
    <div
      className={cn(
        "flex w-full gap-3 animate-fade-in",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-muted-foreground">
          <Bot className="h-4 w-4" />
        </div>
      )}

      <div
        className={cn(
          "group flex max-w-[82%] flex-col gap-1.5",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm shadow-sm",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-sm"
              : "bg-card border border-border text-card-foreground rounded-bl-sm",
            message.error && "border-destructive/50",
          )}
        >
          {message.content ? (
            <p className="whitespace-pre-wrap break-words leading-relaxed">
              {message.content}
            </p>
          ) : (
            <p className="text-muted-foreground italic">No response.</p>
          )}
        </div>

        {message.error && (
          <p className="text-xs text-destructive">{message.error}</p>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}

        {!isUser && message.content && (
          <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
            {message.latencyMs !== undefined && (
              <span>{formatDuration(message.latencyMs / 1000)}</span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-6 px-2 text-[11px]"
            >
              <Copy className="mr-1 h-3 w-3" />
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        )}
      </div>

      {isUser && (
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}

function LoadingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Thinking">
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-current" />
      <span
        className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-current"
        style={{ animationDelay: "150ms" }}
      />
      <span
        className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-current"
        style={{ animationDelay: "300ms" }}
      />
    </span>
  );
}
