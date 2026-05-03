import { z } from "zod";

// === ORDER SCHEMAS ===

// ID schema - accepts any non-empty string (CUIDs in practice)
const idSchema = z.string().min(1, "ID is required");

// API contract schema - accepts database IDs directly
export const CreateOrderSchema = z.object({
  sellerId: idSchema,
  customerId: idSchema,
  items: z.array(z.object({
    productId: idSchema,
    quantity: z.number().int().positive().max(999),
  })).min(1, "At least one item is required"),
  paymentType: z.enum(["CASH_ON_DELIVERY", "CARD", "WALLET"]),
  notes: z.string().optional(),
});

// Internal schema - for database operations with CUIDs only
export const CreateOrderInternalSchema = z.object({
  sellerId: z.string().cuid(),
  customerId: z.string().cuid(),
  items: z.array(z.object({
    productId: z.string().cuid(),
    quantity: z.number().int().positive().max(999),
  })),
  paymentType: z.enum(["CASH_ON_DELIVERY", "CARD", "WALLET"]),
  notes: z.string().optional(),
});

// Order update schema
export const UpdateOrderSchema = z.object({
  status: z.enum(["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]).optional(),
  notes: z.string().optional(),
});

// Order status update schema (specific for status changes)
export const UpdateOrderStatusSchema = z.object({
  status: z.enum(["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]),
});

// Order query parameters
export const GetOrdersSchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
  status: z.enum(["PENDING", "CONFIRMED", "PACKED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]).optional(),
  paymentStatus: z.enum(["PENDING", "PAID", "FAILED", "REFUNDED"]).optional(),
  customerId: z.string().cuid().optional(),
});

// === PAYMENT SCHEMAS ===

// Create payment attempt schema
export const CreatePaymentSchema = z.object({
  provider: z.enum(["STRIPE", "PAYPAL", "MPESA"]),
  amountMinor: z.number().int().positive().max(999999999), // Max ~$10M
  currency: z.string().length(3).regex(/^[A-Z]{3}$/),
  paymentType: z.enum(["CASH_ON_DELIVERY", "CARD", "WALLET"]).optional(),
  metadataJson: z.string().optional(),
});

// Update payment status schema
export const UpdatePaymentStatusSchema = z.object({
  status: z.enum(["PENDING", "PROCESSING", "COMPLETED", "FAILED", "REFUNDED"]),
  failureReason: z.string().optional(),
});

// Refund payment schema
export const RefundPaymentSchema = z.object({
  reason: z.string().optional(),
});

// === CUSTOMER SCHEMAS ===

// Create customer schema
export const CreateCustomerSchema = z.object({
  name: z.string().min(1).max(100),
  phone: z.string().regex(/^[+]?[\d\s\-\(\)]+$/).min(10).max(20),
  addressText: z.string().max(500).optional(),
});

// === PRODUCT SCHEMAS ===

// Create product schema
export const CreateProductSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().max(2000).optional(),
  priceMinor: z.number().int().positive().max(999999999),
  currency: z.string().length(3).regex(/^[A-Z]{3}$/),
  category: z.string().max(100).optional(),
  isActive: z.boolean().default(true),
});

// === RESPONSE SCHEMAS ===

// Standard API response wrapper
export const ApiResponseSchema = z.object({
  success: z.boolean(),
  data: z.unknown().optional(),
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }).optional(),
});

export type ApiResponse<T = unknown> = z.infer<typeof ApiResponseSchema> & {
  data?: T;
};

// Order response schema
export const OrderResponseSchema = z.object({
  id: z.string().cuid(),
  publicOrderNumber: z.string(),
  status: z.string(),
  paymentStatus: z.string(),
  subtotalMinor: z.number().int(),
  deliveryFeeMinor: z.number().int(),
  totalMinor: z.number().int(),
  currency: z.string(),
  notes: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  customer: z.object({
    id: z.string().cuid(),
    name: z.string(),
    phone: z.string(),
    addressText: z.string().nullable(),
  }),
  items: z.array(z.object({
    id: z.string().cuid(),
    productId: z.string().cuid(),
    productNameSnapshot: z.string(),
    unitPriceMinor: z.number().int(),
    quantity: z.number().int(),
    lineTotalMinor: z.number().int(),
  })),
});

// === ERROR SCHEMAS ===

// Standard error response
export const ErrorResponseSchema = z.object({
  success: z.literal(false),
  error: z.object({
    code: z.enum([
      "VALIDATION_ERROR",
      "NOT_FOUND",
      "UNAUTHORIZED",
      "FORBIDDEN",
      "INTERNAL_ERROR",
      "PAYMENT_FAILED",
      "INSUFFICIENT_STOCK",
      "INVALID_STATUS_TRANSITION",
    ]),
    message: z.string(),
    details: z.unknown().optional(),
  }),
});

// === TYPE EXPORTS ===

export type CreateOrderInput = z.infer<typeof CreateOrderSchema>;
export type UpdateOrderInput = z.infer<typeof UpdateOrderSchema>;
export type UpdateOrderStatusInput = z.infer<typeof UpdateOrderStatusSchema>;
export type GetOrdersQuery = z.infer<typeof GetOrdersSchema>;
export type CreatePaymentInput = z.infer<typeof CreatePaymentSchema>;
export type UpdatePaymentStatusInput = z.infer<typeof UpdatePaymentStatusSchema>;
export type RefundPaymentInput = z.infer<typeof RefundPaymentSchema>;
export type CreateCustomerInput = z.infer<typeof CreateCustomerSchema>;
export type CreateProductInput = z.infer<typeof CreateProductSchema>;
export type OrderResponse = z.infer<typeof OrderResponseSchema>;
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
