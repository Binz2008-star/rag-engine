import type {
  AgentAnalyzeRequest,
  AgentAnalyzeResponse,
  CreateTaskRequest,
  DispatchRequest,
  DispatchResponse,
  ExecuteTaskRequest,
  ExecuteTaskResponse,
  HealthResponse,
  QueryRequest,
  QueryResponse,
  ScheduleTaskRequest,
  ScheduleTaskResponse,
  SystemHealthResponse,
  TaskResponse,
  TradingAnalyzeRequest,
  TradingAnalyzeResponse
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return API_BASE_URL;
  }
  const fromEnv = (window as Window & { NEXT_PUBLIC_API_BASE_URL?: string })
    .NEXT_PUBLIC_API_BASE_URL;
  return (fromEnv && fromEnv.trim()) || API_BASE_URL;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown = undefined;
  let message = response.statusText || `HTTP ${response.status}`;

  try {
    const body = await response.json();
    detail = body;
    if (typeof body?.detail === "string") message = body.detail;
    else if (typeof body?.error === "string") message = body.error;
  } catch {
    try {
      const text = await response.text();
      if (text) message = text;
    } catch {
      // noop
    }
  }
  return new ApiError(response.status, message, detail);
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  throw await parseError(response);
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
    signal,
  });

  return parseJsonOrThrow<HealthResponse>(response);
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getHealth(signal);
}

export async function getSystemHealth(
  signal?: AbortSignal,
): Promise<SystemHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/system/health`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
    signal,
  });

  return parseJsonOrThrow<SystemHealthResponse>(response);
}

export async function postQuery(
  payload: QueryRequest,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  return parseJsonOrThrow<QueryResponse>(response);
}

export async function postTradingAnalyze(
  payload: TradingAnalyzeRequest,
  signal?: AbortSignal,
): Promise<TradingAnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trading/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  return parseJsonOrThrow<TradingAnalyzeResponse>(response);
}

export async function postAgentAnalyze(
  payload: AgentAnalyzeRequest,
  signal?: AbortSignal,
): Promise<AgentAnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  return parseJsonOrThrow<AgentAnalyzeResponse>(response);
}

export async function postDispatch(
  payload: DispatchRequest,
  signal?: AbortSignal,
): Promise<DispatchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/dispatch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  return parseJsonOrThrow<DispatchResponse>(response);
}

export async function createAgentTask(
  payload: CreateTaskRequest,
  signal?: AbortSignal,
): Promise<TaskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return parseJsonOrThrow<TaskResponse>(response);
}

export async function listAgentTasks(
  sessionId?: string,
  signal?: AbortSignal,
): Promise<TaskResponse[]> {
  const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/agent/tasks${suffix}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  return parseJsonOrThrow<TaskResponse[]>(response);
}

export async function scheduleAgentTask(
  payload: ScheduleTaskRequest,
  signal?: AbortSignal,
): Promise<ScheduleTaskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/tasks/schedule`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return parseJsonOrThrow<ScheduleTaskResponse>(response);
}

export async function executeAgentTask(
  payload: ExecuteTaskRequest,
  signal?: AbortSignal,
): Promise<ExecuteTaskResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/tasks/execute`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  return parseJsonOrThrow<ExecuteTaskResponse>(response);
}
