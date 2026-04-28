"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

interface ChatInputProps {
  onSubmit: (question: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
}

export function ChatInput({
  onSubmit,
  onCancel,
  disabled,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoresize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    autoresize();
  }, [value, autoresize]);

  const handleSubmit = () => {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="sticky bottom-0 border-t border-border bg-background/95 backdrop-blur">
      <div className="mx-auto max-w-4xl px-4 py-3">
        <div
          className={cn(
            "flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-sm transition-colors",
            "focus-within:border-foreground/30",
          )}
        >
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your corpus..."
            rows={1}
            className="min-h-[40px] border-0 bg-transparent px-2 py-2 shadow-none focus-visible:ring-0"
            disabled={disabled}
          />

          <Button
            size="icon"
            onClick={handleSubmit}
            disabled={disabled || !value.trim()}
            aria-label="Send message"
            title="Send (Enter)"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1.5 text-center text-[11px] text-muted-foreground">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
