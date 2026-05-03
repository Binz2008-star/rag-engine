import { z } from "zod";

// === ORDER RESPONSE SCHEMAS ===

// Strict order response schema for API output validation
export const OrderResponseSchema = z.object({
  id: z.string().cuid(),
  sellerId: z.string().cuid(),
  publicOrderNumber: z.string(),
  status: z.enum(["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]),
  paymentStatus: z.enum(["PENDING", "PAID", "FAILED", "REFUNDED"]),
  paymentType: z.enum(["CASH_ON_DELIVERY", "CARD", "WALLET"]),
  subtotalMinor: z.number().int().nonnegative(),
  deliveryFeeMinor: z.number().int().nonnegative(),
  totalMinor: z.number().int().positive(),
  currency: z.string().length(3).regex(/^[A-Z]{3}$/),
  notes: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  customer: z.object({
    id: z.string().cuid(),
    name: z.string().min(1).max(100),
    phone: z.string().regex(/^[+]?[\d\s\-\(\)]+$/).min(10).max(20),
    addressText: z.string().nullable(),
  }),
  items: z.array(z.object({
    id: z.string().cuid(),
    productId: z.string().cuid(),
    productNameSnapshot: z.string().min(1).max(200),
    unitPriceMinor: z.number().int().nonnegative(),
    quantity: z.number().int().positive(),
    lineTotalMinor: z.number().int().nonnegative(),
  })),
});

// Order list response schema
export const OrderListResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    orders: z.array(OrderResponseSchema),
    pagination: z.object({
      page: z.number().int().positive(),
      limit: z.number().int().positive(),
      total: z.number().int().nonnegative(),
      totalPages: z.number().int().nonnegative(),
      hasNext: z.boolean(),
      hasPrev: z.boolean(),
    }),
  }),
});

// Order creation response schema
export const OrderCreateResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    order: OrderResponseSchema,
  }),
});

// Order update response schema
export const OrderUpdateResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    order: OrderResponseSchema,
  }),
});

// === TYPE EXPORTS ===

export type OrderResponse = z.infer<typeof OrderResponseSchema>;
export type OrderListResponse = z.infer<typeof OrderListResponseSchema>;
export type OrderCreateResponse = z.infer<typeof OrderCreateResponseSchema>;
export type OrderUpdateResponse = z.infer<typeof OrderUpdateResponseSchema>;
