import { z } from "zod";

// === SAFE FETCH WRAPPER ===
// Enforces response contracts on all API calls

export interface SafeFetchOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

export class SafeFetchError extends Error {
  constructor(
    message: string,
    public status?: number,
    public response?: unknown
  ) {
    super(message);
    this.name = 'SafeFetchError';
  }
}

export async function safeFetch<T>(
  url: string,
  schema: z.ZodSchema<T>,
  options: SafeFetchOptions = {}
): Promise<T> {
  const {
    timeout = 10000,
    retries = 3,
    retryDelay = 1000,
    ...fetchOptions
  } = options;

  let lastError: Error | null = null;

  // Retry logic with exponential backoff
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        throw new SafeFetchError(
          `API error: ${response.status} ${response.statusText}`,
          response.status,
          errorText
        );
      }

      const json = await response.json();

      // Enforce response contract
      const validated = schema.parse(json);

      return validated;
    } catch (error) {
      lastError = error as Error;

      // Don't retry on client errors (4xx) or abort errors
      if (
        error instanceof SafeFetchError &&
        (error.status && error.status >= 400 && error.status < 500) ||
        (error instanceof Error && error.name === 'AbortError')
      ) {
        throw error;
      }

      // Retry on server errors or network issues
      if (attempt < retries) {
        await new Promise(resolve =>
          setTimeout(resolve, retryDelay * Math.pow(2, attempt - 1))
        );
      }
    }
  }

  throw lastError || new SafeFetchError('Request failed after retries');
}

// === TYPE GUARDS ===

export function isSafeFetchError(error: unknown): error is SafeFetchError {
  return error instanceof SafeFetchError;
}

export function getErrorMessage(error: unknown): string {
  if (isSafeFetchError(error)) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unknown error occurred';
}

// === BATCH OPERATIONS ===

export async function safeFetchBatch<T>(
  requests: Array<{
    url: string;
    schema: z.ZodSchema<T>;
    options?: SafeFetchOptions;
  }>
): Promise<T[]> {
  const promises = requests.map(({ url, schema, options }) =>
    safeFetch(url, schema, options)
  );

  try {
    return await Promise.all(promises);
  } catch (error) {
    // In batch operations, we want to fail fast on any error
    throw error;
  }
}

// === CACHED FETCH ===

const fetchCache = new Map<string, { data: unknown; timestamp: number }>();

export async function safeFetchCached<T>(
  url: string,
  schema: z.ZodSchema<T>,
  options: SafeFetchOptions & { cacheTtl?: number } = {}
): Promise<T> {
  const { cacheTtl = 5 * 60 * 1000, ...fetchOptions } = options; // 5 minutes default
  const cacheKey = `${url}:${JSON.stringify(fetchOptions)}`;
  const cached = fetchCache.get(cacheKey);

  if (cached && Date.now() - cached.timestamp < cacheTtl) {
    try {
      return schema.parse(cached.data);
    } catch {
      // Cache invalid, remove and continue
      fetchCache.delete(cacheKey);
    }
  }

  const data = await safeFetch(url, schema, fetchOptions);
  fetchCache.set(cacheKey, { data, timestamp: Date.now() });

  return data;
}

// === HEALTH CHECK ===

export async function healthCheck(
  baseUrl: string,
  options?: SafeFetchOptions
): Promise<boolean> {
  try {
    await safeFetch(
      `${baseUrl}/api/health`,
      z.object({ status: z.string() }),
      { timeout: 5000, ...options }
    );
    return true;
  } catch {
    return false;
  }
}
