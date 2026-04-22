"use client";

import { FileText } from "lucide-react";
import type { SourceItem } from "@/lib/types";
import { truncate } from "@/lib/utils";

interface SourceListProps {
  sources: SourceItem[];
}

export function SourceList({ sources }: SourceListProps) {
  if (!sources.length) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Sources ({sources.length})
      </p>
      <ul className="flex flex-wrap gap-2">
        {sources.map((s, idx) => (
          <li
            key={`${s.source}-${s.chunk_id || idx}`}
            className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-border bg-muted/50 px-2 py-1 text-xs"
            title={`${s.source}${s.chunk_id ? ` (chunk ${s.chunk_id})` : ""}`}
          >
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate font-medium">{truncate(s.source, 48)}</span>
            {s.chunk_id ? (
              <span className="text-muted-foreground">#{s.chunk_id}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
