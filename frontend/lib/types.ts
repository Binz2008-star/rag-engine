export type SourceItem = {
  source: string;
  chunk_id: string;
  doc_type: string;
  score: number;
};

export type QueryRequest = {
  question: string;
  session_id?: string | null;
  user_id?: string | null;
};

export type TradingAnalyzeRequest = {
  question: string;
  session_id?: string | null;
  user_id?: string | null;
};

export type AgentAnalyzeRequest = {
  question: string;
  session_id?: string | null;
  user_id?: string | null;
};

export type DispatchRequest = {
  question: string;
  session_id?: string | null;
  user_id?: string | null;
};

export type QueryResponse = {
  answer: string;
  sources: SourceItem[];
  latency_ms: number;
  wall_ms: number;
  request_id: string;
  intent: string;
  intent_confidence: number;
  intent_method: string;
  intent_method_raw: string;
  grounded: boolean;
  failure_type: string | null;
  model_version: string;
  retriever_version: string;
};

export type TradingAnalyzeResponse = {
  capability: string;
  intent: string;
  market: string | null;
  asset: string | null;
  timeframe: string | null;
  prompt: string;
  status: string;
};

export type AgentAnalyzeResponse = {
  capability: string;
  intent: string;
  prompt: string;
  summary: string;
  suggested_tools: string[];
  status: string;
};

export type GeneralChatResponse = {
  capability: string;
  intent: string;
  answer: string;
  status: string;
};

export type DispatchResponse = {
  capability: "rag" | "trading" | "agent" | "general";
  kind: "rag_answer" | "trading_analysis" | "agent_analysis" | "general_chat" | "error";
  status: "ok" | "error";
  request_id: string;
  payload: Record<string, unknown>;
};

export type CreateTaskRequest = {
  title: string;
  prompt: string;
  intent: string;
  session_id?: string | null;
  user_id?: string | null;
};

export type TaskResponse = {
  task_id: string;
  title: string;
  prompt: string;
  intent: string;
  status: string;
  session_id?: string | null;
  user_id?: string | null;
  created_at: number;
  updated_at: number;
};

export type ScheduleTaskRequest = {
  task_id: string;
  run_at: number;
};

export type ScheduleTaskResponse = {
  task_id: string;
  run_at: number;
  status: string;
  created_at: number;
};

export type ExecuteTaskRequest = {
  task_id: string;
};

export type ExecuteTaskResponse = {
  task_id: string;
  status: string;
  output: string;
  started_at: number;
  finished_at: number;
};

export type HealthResponse = {
  status: string;
  pipeline_ready: boolean;
  version: string;
  chat_model: string;
  index_count?: number | null;
  detail?: string | null;
};

export type SystemHealthCheck = {
  name: string;
  status: string;
  detail: string;
  metadata?: Record<string, unknown> | null;
};

export type SystemHealthResponse = {
  version: string;
  pipeline_ready: boolean;
  index_count?: number | null;
  guardian: {
    overall_status: string;
    checks: SystemHealthCheck[];
    timestamp: number;
  };
};

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  sources?: SourceItem[];
  latencyMs?: number;
  error?: string;
}
