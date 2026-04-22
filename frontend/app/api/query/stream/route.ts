export const runtime = "edge";

import { type NextRequest } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

  try {
    const upstream = await fetch(`${BACKEND}/api/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: controller.signal,
    });

    if (!upstream.ok) {
      return new Response(await upstream.text(), { status: upstream.status });
    }

    // Create a transformed stream with proper cleanup
    const stream = new ReadableStream({
      async start(controller) {
        const reader = upstream.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              controller.close();
              break;
            }
            controller.enqueue(value);
          }
        } catch (error) {
          // Ignore errors from aborted requests during shutdown
          if (error instanceof Error && error.name !== 'AbortError') {
            controller.error(error);
          }
        } finally {
          reader.releaseLock();
        }
      },
      cancel() {
        controller.abort();
      },
    });

    return new Response(stream, {
      status: 200,
      headers: {
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection":    "keep-alive",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return new Response("Stream aborted", { status: 499 });
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
