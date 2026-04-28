# RAG Assistant Frontend

Next.js 14 (App Router) + TypeScript + Tailwind + TanStack Query chat UI for
the local RAG system. Talks to the FastAPI gateway in `../api`.

## Features

- ChatGPT-style chat layout with sources panel per assistant message
- Non-streaming (`/api/query`) and streaming (`/api/stream` SSE) modes
- Request cancellation, copy-to-clipboard, clear chat
- Health badge polling `/api/health`
- Light/dark mode, responsive, keyboard shortcut (Enter / Shift+Enter)

## Setup

```powershell
# 1. Install deps
npm install

# 2. Configure the API base URL (defaults to http://localhost:8000)
Copy-Item .env.example .env.local

# 3. Start dev server
npm run dev
```

Open <http://localhost:3000>.

## Project layout

```
frontend/
├─ app/
│  ├─ layout.tsx        # Root layout, loads providers
│  ├─ page.tsx          # Renders ChatShell
│  ├─ providers.tsx     # React Query + Toast providers
│  └─ globals.css       # Tailwind base + tokens
├─ components/
│  ├─ ChatShell.tsx     # Stateful chat container
│  ├─ Header.tsx        # Branding, health badge, stream toggle, theme, clear
│  ├─ MessageList.tsx   # Message stream + empty state
│  ├─ MessageBubble.tsx # Single message with timings, copy, sources
│  ├─ SourceList.tsx    # Source chips
│  ├─ ChatInput.tsx     # Auto-resizing textarea + send/cancel
│  └─ ui/               # Button, Textarea, Toast primitives
├─ lib/
│  ├─ api.ts            # fetch wrappers + SSE stream parser
│  ├─ types.ts          # Shared TS types (mirror backend schemas)
│  └─ utils.ts          # cn(), formatDuration(), truncate()
├─ tailwind.config.ts
├─ tsconfig.json
├─ next.config.mjs
├─ postcss.config.mjs
└─ package.json
```

## Notes

- Streaming uses `fetch` + a manual SSE parser (not `EventSource`) because we
  POST a JSON body. Supports request cancellation via `AbortController`.
- Types in `lib/types.ts` are kept in 1-to-1 correspondence with the backend
  Pydantic schemas (`server/schemas.py`). If you change one, change both.
