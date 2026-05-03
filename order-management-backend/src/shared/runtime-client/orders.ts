// === ORDERS RUNTIME CLIENT ===
// Type-safe, validated API client for order operations

import { z } from "zod";
import {
  OrderCreateResponseSchema,
  OrderListResponseSchema,
  OrderResponseSchema,
  OrderUpdateResponseSchema
} from "../schemas/order-response";
import {
  CreateOrderSchema,
  GetOrdersSchema,
  UpdateOrderSchema,
  UpdateOrderStatusSchema
} from "../schemas/orders";
import { safeFetch, SafeFetchError, SafeFetchOptions } from "./safe-fetch";

// Type aliases for input types
type CreateOrderInput = z.infer<typeof CreateOrderSchema>;
type GetOrdersQuery = z.infer<typeof GetOrdersSchema>;
type UpdateOrderInput = z.infer<typeof UpdateOrderSchema>;
type UpdateOrderStatusInput = z.infer<typeof UpdateOrderStatusSchema>;

// Type aliases for response types
type OrderResponse = z.infer<typeof OrderResponseSchema>;
type OrderListResponse = z.infer<typeof OrderListResponseSchema>;
type OrderCreateResponse = z.infer<typeof OrderCreateResponseSchema>;
type OrderUpdateResponse = z.infer<typeof OrderUpdateResponseSchema>;

// === ORDERS API CLIENT ===

export class OrdersClient {
  private baseUrl: string;
  private defaultOptions: SafeFetchOptions;

  constructor(baseUrl: string, defaultOptions: SafeFetchOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, ""); // Remove trailing slash
    this.defaultOptions = defaultOptions;
  }

  // === ORDER CRUD OPERATIONS ===

  async create(data: z.infer<typeof CreateOrderSchema>, options?: SafeFetchOptions): Promise<OrderCreateResponse> {
    return safeFetch(
      `${this.baseUrl}/api/v1/orders`,
      z.object({
        success: z.literal(true),
        data: z.object({
          order: OrderResponseSchema,
        }),
      }),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  async get(id: string, options?: SafeFetchOptions): Promise<{ success: true; data: { order: OrderResponse } }> {
    return safeFetch(
      `${this.baseUrl}/api/v1/orders/${id}`,
      z.object({
        success: z.literal(true),
        data: z.object({
          order: OrderResponseSchema,
        }),
      }),
      {
        method: "GET",
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  async list(query: GetOrdersQuery, options?: SafeFetchOptions): Promise<OrderListResponse> {
    const params = new URLSearchParams();

    if (query.page) params.set("page", query.page.toString());
    if (query.limit) params.set("limit", query.limit.toString());
    if (query.status) params.set("status", query.status);
    if (query.paymentStatus) params.set("paymentStatus", query.paymentStatus);
    if (query.customerId) params.set("customerId", query.customerId);

    return safeFetch(
      `${this.baseUrl}/api/v1/orders?${params.toString()}`,
      OrderListResponseSchema,
      {
        method: "GET",
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  async update(id: string, data: UpdateOrderInput, options?: SafeFetchOptions): Promise<OrderUpdateResponse> {
    return safeFetch(
      `${this.baseUrl}/api/v1/orders/${id}`,
      OrderUpdateResponseSchema,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  async updateStatus(id: string, data: UpdateOrderStatusInput, options?: SafeFetchOptions): Promise<OrderUpdateResponse> {
    return safeFetch(
      `${this.baseUrl}/api/v1/orders/${id}/status`,
      OrderUpdateResponseSchema,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  async getEvents(id: string, options?: SafeFetchOptions): Promise<{ success: true; data: { events: unknown[] } }> {
    return safeFetch(
      `${this.baseUrl}/api/v1/orders/${id}/events`,
      z.object({
        success: z.literal(true),
        data: z.object({
          events: z.array(z.unknown()),
        }),
      }),
      {
        method: "GET",
        ...this.defaultOptions,
        ...options,
      }
    );
  }

  // === BULK OPERATIONS ===

  async createMultiple(orders: CreateOrderInput[], options?: SafeFetchOptions): Promise<OrderCreateResponse[]> {
    const promises = orders.map(order => this.create(order, options));

    try {
      return await Promise.all(promises);
    } catch (error) {
      // In bulk operations, we want to fail fast on any error
      throw error;
    }
  }

  async getMultiple(ids: string[], options?: SafeFetchOptions): Promise<{ success: true; data: { order: OrderResponse } }[]> {
    const promises = ids.map(id => this.get(id, options));

    try {
      return await Promise.all(promises);
    } catch (error) {
      throw error;
    }
  }

  // === UTILITY METHODS ===

  async exists(id: string, options?: SafeFetchOptions): Promise<boolean> {
    try {
      await this.get(id, options);
      return true;
    } catch (error) {
      if (error instanceof SafeFetchError && error.status === 404) {
        return false;
      }
      throw error;
    }
  }

  async count(query: Omit<GetOrdersQuery, "page" | "limit">, options?: SafeFetchOptions): Promise<number> {
    const params = new URLSearchParams();

    if (query.status) params.set("status", query.status);
    if (query.paymentStatus) params.set("paymentStatus", query.paymentStatus);
    if (query.customerId) params.set("customerId", query.customerId);
    params.set("count", "true");

    const response = await safeFetch(
      `${this.baseUrl}/api/v1/orders?${params.toString()}`,
      z.object({
        success: z.literal(true),
        data: z.object({
          count: z.number().int().nonnegative(),
        }),
      }),
      {
        method: "GET",
        ...this.defaultOptions,
        ...options,
      }
    );

    return response.data.count;
  }

  // === HEALTH CHECK ===

  async healthCheck(): Promise<boolean> {
    try {
      await safeFetch(
        `${this.baseUrl}/api/v1/health`,
        z.object({ status: z.string() }),
        { timeout: 5000, ...this.defaultOptions }
      );
      return true;
    } catch {
      return false;
    }
  }
}

// === FACTORY FUNCTION ===

export function createOrdersClient(baseUrl: string, options?: SafeFetchOptions): OrdersClient {
  return new OrdersClient(baseUrl, options);
}

// === TYPE EXPORTS ===

export type { OrderCreateResponse, OrderListResponse, OrderResponse, OrderUpdateResponse };

