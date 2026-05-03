import { z } from 'zod';

// === AUTH TYPES ===

export const UserRoleSchema = z.enum(['STAFF', 'SELLER', 'ADMIN']);

export type UserRole = z.infer<typeof UserRoleSchema>;

export const AuthTokenPayloadSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  role: UserRoleSchema,
  sellerId: z.string().nullable(),
  iat: z.number().optional(),
  exp: z.number().optional(),
  iss: z.string().optional(),
  aud: z.string().optional(),
});

export type AuthTokenPayload = z.infer<typeof AuthTokenPayloadSchema>;

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const LoginResponseSchema = z.object({
  user: z.object({
    id: z.string(),
    email: z.string().email(),
    role: UserRoleSchema,
    sellerId: z.string().nullable(),
    fullName: z.string(),
    isActive: z.boolean(),
  }),
  token: z.string(),
  expiresIn: z.string(),
});

export type LoginResponse = z.infer<typeof LoginResponseSchema>;

// === ORDER TYPES ===

export const OrderStatusSchema = z.enum([
  'PENDING',
  'CONFIRMED',
  'PROCESSING',
  'SHIPPED',
  'DELIVERED',
  'CANCELLED',
  'REFUNDED'
]);

export type OrderStatus = z.infer<typeof OrderStatusSchema>;

export const CreateOrderRequestSchema = z.object({
  customerId: z.string(),
  items: z.array(z.object({
    productId: z.string(),
    quantity: z.number().min(1),
    price: z.number().min(0),
  })),
  shippingAddress: z.object({
    street: z.string(),
    city: z.string(),
    state: z.string(),
    zipCode: z.string(),
    country: z.string(),
  }),
});

export type CreateOrderRequest = z.infer<typeof CreateOrderRequestSchema>;

export const OrderSchema = z.object({
  id: z.string(),
  customerId: z.string(),
  status: OrderStatusSchema,
  totalAmount: z.number(),
  items: z.array(z.object({
    id: z.string(),
    productId: z.string(),
    quantity: z.number(),
    price: z.number(),
  })),
  shippingAddress: z.object({
    street: z.string(),
    city: z.string(),
    state: z.string(),
    zipCode: z.string(),
    country: z.string(),
  }),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type Order = z.infer<typeof OrderSchema>;

// === PAYMENT TYPES ===

export const PaymentStatusSchema = z.enum([
  'PENDING',
  'PROCESSING',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'REFUNDED'
]);

export type PaymentStatus = z.infer<typeof PaymentStatusSchema>;

export const PaymentMethodSchema = z.enum([
  'CREDIT_CARD',
  'DEBIT_CARD',
  'PAYPAL',
  'STRIPE',
  'BANK_TRANSFER'
]);

export type PaymentMethod = z.infer<typeof PaymentMethodSchema>;

export const CreatePaymentRequestSchema = z.object({
  orderId: z.string(),
  amount: z.number().min(0),
  currency: z.string().length(3),
  method: PaymentMethodSchema,
  paymentDetails: z.record(z.unknown()),
});

export type CreatePaymentRequest = z.infer<typeof CreatePaymentRequestSchema>;

export const PaymentSchema = z.object({
  id: z.string(),
  orderId: z.string(),
  amount: z.number(),
  currency: z.string(),
  status: PaymentStatusSchema,
  method: PaymentMethodSchema,
  provider: z.string(),
  providerTransactionId: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type Payment = z.infer<typeof PaymentSchema>;

// === API RESPONSE TYPES ===

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

export const PaginatedResponseSchema = z.object({
  data: z.array(z.unknown()),
  pagination: z.object({
    page: z.number(),
    limit: z.number(),
    total: z.number(),
    totalPages: z.number(),
  }),
});

export type PaginatedResponse<T = unknown> = {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
};

// === ERROR TYPES ===

export const ApiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  statusCode: z.number(),
  details: z.unknown().optional(),
});

export type ApiError = z.infer<typeof ApiErrorSchema>;

export const ErrorCodeSchema = z.enum([
  'VALIDATION_ERROR',
  'AUTHENTICATION_ERROR',
  'AUTHORIZATION_ERROR',
  'NOT_FOUND',
  'CONFLICT',
  'RATE_LIMIT_EXCEEDED',
  'INTERNAL_SERVER_ERROR',
  'SERVICE_UNAVAILABLE',
]);

export type ErrorCode = z.infer<typeof ErrorCodeSchema>;

// === CONFIGURATION TYPES ===

export const SdkConfigSchema = z.object({
  baseURL: z.string().url(),
  timeout: z.number().min(1000).default(10000),
  retryAttempts: z.number().min(0).default(3),
  retryDelay: z.number().min(100).default(1000),
});

export type SdkConfig = z.infer<typeof SdkConfigSchema>;
