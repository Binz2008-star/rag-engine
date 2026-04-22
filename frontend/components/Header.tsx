"use client";

import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { Moon, RefreshCw, Sun, Zap } from "lucide-react";
import { useEffect, useState } from "react";

interface HeaderProps {
  onClearChat: () => void;
  hasMessages: boolean;
}

export function Header({
  onClearChat,
  hasMessages,
}: HeaderProps) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 15_000,
  });

  const ready = data?.pipeline_ready === true;
  const status: "ok" | "starting" | "error" = isError
    ? "error"
    : ready
      ? "ok"
      : "starting";

  const [dark, setDark] = useState<boolean>(false);
  useEffect(() => {
    const initial =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(initial);
    document.documentElement.classList.toggle("dark", initial);
  }, []);

  const toggleTheme = () => {
    setDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-4xl items-center gap-3 px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Zap className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">RAG Assistant</p>
            <p className="text-[11px] text-muted-foreground">
              {data?.chat_model ? `model: ${data.chat_model}` : "local pipeline"}
            </p>
          </div>
        </div>

        <div className="ml-4 flex items-center gap-2">
          <HealthBadge status={status} loading={isLoading || isFetching} />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            aria-label="Refresh health"
            title="Refresh health"
          >
            <RefreshCw
              className={cn("h-4 w-4", isFetching && "animate-spin")}
            />
          </Button>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearChat}
            disabled={!hasMessages}
          >
            Clear
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </header>
  );
}

function HealthBadge({
  status,
  loading,
}: {
  status: "ok" | "starting" | "error";
  loading: boolean;
}) {
  const label =
    status === "ok" ? "Ready" : status === "starting" ? "Starting" : "Offline";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        status === "ok" && "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
        status === "starting" && "border-amber-500/40 text-amber-600 dark:text-amber-400",
        status === "error" && "border-destructive/50 text-destructive",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "ok" && "bg-emerald-500",
          status === "starting" && "bg-amber-500 animate-pulse-soft",
          status === "error" && "bg-destructive",
          loading && "animate-pulse-soft",
        )}
      />
      {label}
    </span>
  );
}
