/**
 * safeFetch — Contract-driven API client
 * =========================================
 * Validates API responses against Zod schemas at runtime.
 * If the response shape doesn't match the contract → throws immediately.
 * This prevents silent contract drift between UI and backend.
 *
 * Usage:
 *   const data = await safeFetch(
 *     `/api/v1/orders/${orderId}`,
 *     OrderDetailResponseSchema,
 *     { headers: { Authorization: `Bearer ${token}` } }
 *   );
 *   setOrder(data.data.order);
 *
 * API contract expected from backend:
 *   { success: true, data: { ... } }
 *   { success: false, error: { code, message, timestamp } }
 */

import { z } from "zod";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly timestamp?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ContractError extends Error {
  constructor(
    message: string,
    public readonly issues: z.ZodIssue[]
  ) {
    super(message);
    this.name = "ContractError";
  }
}

/** Standard API envelope — all backend responses must match this */
const ApiEnvelopeSchema = z.object({
  success: z.boolean(),
  data: z.unknown().optional(),
  error: z.object({
    code: z.string(),
    message: z.string(),
    timestamp: z.string().optional(),
  }).optional(),
});

export async function safeFetch<T>(
  url: string,
  schema: z.ZodType<T>,
  options?: RequestInit & { token?: string }
): Promise<T> {
  const { token, ...fetchOptions } = options || {};

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...fetchOptions, headers });

  let json: unknown;
  try {
    json = await res.json();
  } catch {
    throw new ApiError("PARSE_ERROR", "Failed to parse API response as JSON", res.status);
  }

  // Validate envelope shape
  const envelope = ApiEnvelopeSchema.safeParse(json);
  if (!envelope.success) {
    throw new ContractError("API response does not match expected envelope", envelope.error.issues);
  }

  // Handle API-level errors
  if (!res.ok || !envelope.data.success) {
    const err = envelope.data.error;
    throw new ApiError(
      err?.code || "UNKNOWN_ERROR",
      err?.message || `Request failed with status ${res.status}`,
      res.status,
      err?.timestamp
    );
  }

  // Validate data shape against provided schema
  const parsed = schema.safeParse(envelope.data.data);
  if (!parsed.success) {
    throw new ContractError(
      `API response data does not match schema for ${url}`,
      parsed.error.issues
    );
  }

  return parsed.data;
}

/** Convenience: PATCH order status */
export async function patchOrderStatus(
  orderId: string,
  nextStatus: string,
  token?: string
): Promise<void> {
  await fetch(`/api/v1/orders/${orderId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ status: nextStatus }),
  });
}
