// === RUNTIME CLIENT TYPES ===
// These types are used by sellora platform layer to communicate with runtime core

import {
  ApiResponse,
  CreateCustomerInput,
  CreateOrderInput,
  CreatePaymentInput,
  ErrorResponse,
  GetOrdersQuery,
  OrderResponse,
  RefundPaymentInput,
  UpdateOrderInput,
  UpdateOrderStatusInput,
  UpdatePaymentStatusInput
} from '../schemas/orders';

// === RUNTIME CLIENT INTERFACE ===

export interface RuntimeClient {
  // === ORDER OPERATIONS ===
  orders: {
    create(data: CreateOrderInput): Promise<ApiResponse>;
    get(id: string): Promise<ApiResponse>;
    list(query: GetOrdersQuery): Promise<ApiResponse>;
    update(id: string, data: UpdateOrderInput): Promise<ApiResponse>;
    updateStatus(id: string, data: UpdateOrderStatusInput): Promise<ApiResponse>;
    getEvents(id: string): Promise<ApiResponse>;
  };

  // === PAYMENT OPERATIONS ===
  payments: {
    create(orderId: string, data: CreatePaymentInput): Promise<ApiResponse>;
    get(id: string): Promise<ApiResponse>;
    list(query?: { orderId?: string }): Promise<ApiResponse>;
    updateStatus(id: string, data: UpdatePaymentStatusInput): Promise<ApiResponse>;
    refund(id: string, data: RefundPaymentInput): Promise<ApiResponse>;
  };

  // === CUSTOMER OPERATIONS ===
  customers: {
    create(data: CreateCustomerInput): Promise<ApiResponse>;
    get(id: string): Promise<ApiResponse>;
    list(query?: { sellerId?: string }): Promise<ApiResponse>;
    update(id: string, data: Partial<CreateCustomerInput>): Promise<ApiResponse>;
  };

  // === AUTH OPERATIONS ===
  auth: {
    login(credentials: { email: string; password: string }): Promise<ApiResponse>;
    refresh(refreshToken: string): Promise<ApiResponse>;
    logout(): Promise<ApiResponse>;
  };

  // === HEALTH OPERATIONS ===
  health: {
    check(): Promise<ApiResponse>;
  };

  // === WEBHOOK OPERATIONS ===
  webhooks: {
    create(config: { url: string; events: string[]; secret?: string }): Promise<ApiResponse>;
    list(): Promise<ApiResponse>;
    delete(id: string): Promise<ApiResponse>;
  };
}

// === HTTP CLIENT CONFIG ===

export interface RuntimeClientConfig {
  baseURL: string;
  apiKey?: string;
  timeout?: number;
  retryAttempts?: number;
  headers?: Record<string, string>;
}

// === ERROR TYPES ===

export class RuntimeApiError extends Error {
  constructor(
    public response: ErrorResponse,
    public status: number
  ) {
    super(response.error.message);
    this.name = 'RuntimeApiError';
  }
}

// === REQUEST/RESPONSE INTERFACES ===

export interface RuntimeRequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  retries?: number;
}

export interface RuntimeResponse<T = any> extends ApiResponse<T> {
  status: number;
  headers: Record<string, string>;
}

// === AUTH TOKEN INTERFACE ===

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt?: number;
}

// === CLIENT FACTORY ===

export interface RuntimeClientFactory {
  create(config: RuntimeClientConfig): RuntimeClient;
  createWithTokens(tokens: AuthTokens, config: RuntimeClientConfig): RuntimeClient;
}

// === EXPORTS ===

export type {
  ApiResponse, CreateCustomerInput, CreateOrderInput, CreatePaymentInput, ErrorResponse, GetOrdersQuery, OrderResponse, RefundPaymentInput, UpdateOrderInput,
  UpdateOrderStatusInput, UpdatePaymentStatusInput
};

