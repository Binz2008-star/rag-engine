// === API GATEWAY CLIENT ===
// Centralizes all HTTP policy, auth, retries, and error handling

import { ErrorSchema, isApiError } from "../schemas/error";

// === CLIENT CONFIGURATION ===

export interface GatewayClientOptions {
  baseUrl: string;
  token?: string;
  timeoutMs?: number;
  requestId?: string;
  retryAttempts?: number;
  retryDelayMs?: number;
}

export interface GatewayRequestOptions extends RequestInit {
  params?: Record<string, any>;
  retries?: number;
  timeout?: number;
}

// === CENTRALIZED HTTP CLIENT ===

export class GatewayClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly defaultTimeout: number;
  private readonly defaultRetries: number;
  private readonly defaultRetryDelay: number;

  constructor(options: GatewayClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.token = options.token;
    this.defaultTimeout = options.timeoutMs || 10000;
    this.defaultRetries = options.retryAttempts || 3;
    this.defaultRetryDelay = options.retryDelayMs || 1000;
  }

  // === CORE HTTP METHOD ===

  protected async request<T>(
    path: string,
    method: string,
    options: GatewayRequestOptions = {}
  ): Promise<T> {
    const {
      params,
      retries = this.defaultRetries,
      timeout = this.defaultTimeout,
      ...fetchOptions
    } = options;

    // Build URL with query parameters
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    // Build headers with auth injection
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Request-ID": this.generateRequestId(),
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      ...(fetchOptions.headers as Record<string, string> || {}),
    };

    let lastError: Error | null = null;

    // Retry logic with exponential backoff
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const response = await fetch(url.toString(), {
          method,
          headers,
          body: fetchOptions.body,
          signal: controller.signal,
          ...fetchOptions,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          const errorText = await response.text();
          const error = new Error(`API error: ${response.status} ${response.statusText}`);
          (error as any).status = response.status;
          (error as any).response = errorText;
          throw error;
        }

        const json = await response.json();

        // Validate response structure
        if (json && typeof json === "object") {
          // Check for error responses
          if (json.success === false && json.error) {
            const validated = ErrorSchema.safeParse(json);
            if (validated.success) {
              throw new GatewayError(
                validated.data.error.message,
                validated.data.error.code,
                response.status,
                validated.data
              );
            }
          }
        }

        return json as T;
      } catch (error) {
        lastError = error as Error;

        // Don't retry on client errors (4xx) or abort errors
        const status = (error as any).status;
        if (
          (status && status >= 400 && status < 500) ||
          (error as Error).name === "AbortError" ||
          error instanceof GatewayError
        ) {
          throw error;
        }

        // Retry on server errors or network issues
        if (attempt < retries) {
          const delay = this.defaultRetryDelay * Math.pow(2, attempt - 1);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError || new Error("Request failed after retries");
  }

  // === HTTP METHOD WRAPPERS ===

  async get<T>(path: string, options?: GatewayRequestOptions): Promise<T> {
    return this.request<T>(path, "GET", options);
  }

  async post<T>(path: string, body?: any, options?: GatewayRequestOptions): Promise<T> {
    return this.request<T>(path, "POST", {
      ...options,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async put<T>(path: string, body?: any, options?: GatewayRequestOptions): Promise<T> {
    return this.request<T>(path, "PUT", {
      ...options,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T>(path: string, body?: any, options?: GatewayRequestOptions): Promise<T> {
    return this.request<T>(path, "PATCH", {
      ...options,
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(path: string, options?: GatewayRequestOptions): Promise<T> {
    return this.request<T>(path, "DELETE", options);
  }

  // === UTILITY METHODS ===

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    return this.get<{ status: string }>("/api/health", { timeout: 5000 });
  }

  // Batch requests (parallel)
  async batch<T>(requests: Array<{
    path: string;
    method: string;
    body?: any;
    options?: GatewayRequestOptions;
  }>): Promise<T[]> {
    const promises = requests.map(({ path, method, body, options }) =>
      this.request<T>(path, method, { ...options, body: body ? JSON.stringify(body) : undefined })
    );

    return Promise.all(promises);
  }

  // === STATIC FACTORY METHODS ===

  static withToken(
    baseUrl: string,
    token: string,
    options?: Omit<GatewayClientOptions, "baseUrl" | "token">
  ): GatewayClient {
    return new GatewayClient({ baseUrl, token, ...options });
  }

  static anonymous(
    baseUrl: string,
    options?: Omit<GatewayClientOptions, "token">
  ): GatewayClient {
    return new GatewayClient({ baseUrl, ...options });
  }
}

// === CUSTOM ERROR CLASS ===

export class GatewayError extends Error {
  constructor(
    message: string,
    public code: string,
    public status?: number,
    public details?: any
  ) {
    super(message);
    this.name = "GatewayError";
  }

  static is(error: unknown): error is GatewayError {
    return error instanceof GatewayError;
  }
}

// === ERROR TYPE GUARDS ===

export function isGatewayError(error: unknown): error is GatewayError {
  return GatewayError.is(error);
}

export function getErrorCode(error: unknown): string | undefined {
  if (isGatewayError(error)) {
    return error.code;
  }
  if (isApiError(error)) {
    return error.error.code;
  }
  return undefined;
}

// === MIDDLEWARE SUPPORT ===

export interface Middleware {
  beforeRequest?: (options: GatewayRequestOptions) => GatewayRequestOptions;
  afterResponse?: (response: any) => any;
  onError?: (error: Error) => Error | void;
}

export class MiddlewareGatewayClient extends GatewayClient {
  private middlewares: Middleware[] = [];

  addMiddleware(middleware: Middleware): void {
    this.middlewares.push(middleware);
  }

  protected async request<T>(
    path: string,
    method: string,
    options: GatewayRequestOptions = {}
  ): Promise<T> {
    let processedOptions = options;

    // Apply before request middleware
    for (const middleware of this.middlewares) {
      if (middleware.beforeRequest) {
        processedOptions = middleware.beforeRequest(processedOptions);
      }
    }

    try {
      const response = await super.request<T>(path, method, processedOptions);

      // Apply after response middleware
      let processedResponse = response;
      for (const middleware of this.middlewares) {
        if (middleware.afterResponse) {
          processedResponse = middleware.afterResponse(processedResponse);
        }
      }

      return processedResponse;
    } catch (error) {
      // Apply error middleware
      let processedError = error as Error;
      for (const middleware of this.middlewares) {
        if (middleware.onError) {
          const result = middleware.onError(processedError);
          if (result) {
            processedError = result;
          }
        }
      }

      throw processedError;
    }
  }
}

// === EXAMPLE MIDDLEWARES ===

export const loggingMiddleware: Middleware = {
  beforeRequest(options) {
    console.log(`[Gateway] ${options.method || 'GET'} ${options.params ? JSON.stringify(options.params) : ''}`);
    return options;
  },
  afterResponse(response) {
    console.log(`[Gateway] Response received`);
    return response;
  },
  onError(error) {
    console.error(`[Gateway] Error: ${error.message}`);
    return error;
  },
};

export const retryMiddleware: Middleware = {
  onError(error) {
    // Add custom retry logic here
    return error;
  },
};
