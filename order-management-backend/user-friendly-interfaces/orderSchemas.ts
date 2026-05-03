/**
 * ORDER API CONTRACT SCHEMAS (Zod)
 * ==================================
 * Runtime validation of API responses.
 * These schemas mirror the backend response types exactly.
 *
 * If the backend changes its response shape without updating these → ContractError thrown.
 * That is intentional: contract drift must be loud, not silent.
 *
 * Backend contract:
 *   GET  /api/v1/orders/:id  → OrderDetailResponse
 *   GET  /api/v1/orders      → OrderListResponse
 *   PATCH /api/v1/orders/:id/status → OrderDetailResponse
 */

import { z } from "zod";

// ─── Enums ────────────────────────────────────────────────────────────────────

export const OrderStatusSchema = z.enum([
  "PENDING",
  "CONFIRMED",
  "PREPARING",
  "READY_FOR_PICKUP",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "FAILED_DELIVERY",
  "CANCELLED",
]);

export const PaymentStatusSchema = z.enum(["PENDING", "PAID", "FAILED", "REFUNDED"]);
export const PaymentTypeSchema = z.enum(["CASH_ON_DELIVERY", "CARD", "STRIPE"]);
export const ActorSchema = z.enum(["system", "seller", "customer", "courier"]);

// ─── Sub-schemas ──────────────────────────────────────────────────────────────

export const OrderEventSchema = z.object({
  id: z.string(),
  type: z.string(),
  label: z.string(),
  actor: ActorSchema,
  createdAt: z.string(),
  metadata: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])).optional(),
});

export const OrderItemSchema = z.object({
  id: z.string(),
  productId: z.string(),
  name: z.string(),
  quantity: z.number().int().positive(),
  unitPriceMinor: z.number().int().nonnegative(),
  lineTotalMinor: z.number().int().nonnegative(),
});

export const CustomerSchema = z.object({
  id: z.string(),
  name: z.string(),
  phone: z.string(),
  addressText: z.string().nullable().optional(),
});

// ─── Order Detail ─────────────────────────────────────────────────────────────

export const OrderDetailSchema = z.object({
  id: z.string(),
  publicOrderNumber: z.string(),
  status: OrderStatusSchema,
  paymentStatus: PaymentStatusSchema,
  paymentType: PaymentTypeSchema,
  currency: z.string().min(3).max(3),
  subtotalMinor: z.number().int().nonnegative(),
  deliveryFeeMinor: z.number().int().nonnegative(),
  totalMinor: z.number().int().nonnegative(),
  notes: z.string().nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
  customer: CustomerSchema,
  items: z.array(OrderItemSchema),
  events: z.array(OrderEventSchema),
});

/** Shape of json.data for GET/PATCH /orders/:id */
export const OrderDetailDataSchema = z.object({
  order: OrderDetailSchema,
});

// ─── Order List ───────────────────────────────────────────────────────────────

export const OrderSummarySchema = z.object({
  id: z.string(),
  publicOrderNumber: z.string(),
  status: OrderStatusSchema,
  paymentStatus: PaymentStatusSchema,
  totalMinor: z.number().int().nonnegative(),
  currency: z.string().min(3).max(3),
  createdAt: z.string(),
  customer: z.object({
    name: z.string(),
    phone: z.string(),
  }),
});

export const OrderListDataSchema = z.object({
  orders: z.array(OrderSummarySchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  limit: z.number().int().positive(),
});

// ─── Inferred Types ───────────────────────────────────────────────────────────

export type OrderDetail = z.infer<typeof OrderDetailSchema>;
export type OrderSummary = z.infer<typeof OrderSummarySchema>;
export type OrderEvent = z.infer<typeof OrderEventSchema>;
export type OrderItem = z.infer<typeof OrderItemSchema>;
export type OrderStatus = z.infer<typeof OrderStatusSchema>;
export type PaymentStatus = z.infer<typeof PaymentStatusSchema>;
