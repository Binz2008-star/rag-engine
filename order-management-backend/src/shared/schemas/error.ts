import { z } from "zod";

// === UNIFIED ERROR CONTRACT ===

// Standard error schema for all API responses
export const ErrorSchema = z.object({
  success: z.literal(false),
  error: z.object({
    code: z.enum([
      // Validation errors
      "VALIDATION_ERROR",
      "INVALID_INPUT",
      "MISSING_REQUIRED_FIELD",
      "INVALID_FORMAT",
      
      // Authentication errors
      "UNAUTHORIZED",
      "FORBIDDEN",
      "INVALID_TOKEN",
      "TOKEN_EXPIRED",
      
      // Resource errors
      "NOT_FOUND",
      "ALREADY_EXISTS",
      "RESOURCE_CONFLICT",
      
      // Business logic errors
      "INSUFFICIENT_STOCK",
      "INVALID_STATUS_TRANSITION",
      "PAYMENT_FAILED",
      "INSUFFICIENT_FUNDS",
      
      // System errors
      "INTERNAL_ERROR",
      "SERVICE_UNAVAILABLE",
      "RATE_LIMIT_EXCEEDED",
      "TIMEOUT_ERROR",
    ]),
    message: z.string().min(1).max(500),
    details: z.unknown().optional(),
    timestamp: z.string().datetime().optional(),
    requestId: z.string().optional(),
  }),
});

// Specific error types for better type safety
export const ValidationErrorSchema = ErrorSchema.extend({
  error: z.object({
    code: z.literal("VALIDATION_ERROR"),
    message: z.string(),
    details: z.array(z.object({
      field: z.string(),
      message: z.string(),
      code: z.string().optional(),
    })).optional(),
  }),
});

export const NotFoundErrorSchema = ErrorSchema.extend({
  error: z.object({
    code: z.literal("NOT_FOUND"),
    message: z.string(),
    details: z.object({
      resource: z.string(),
      id: z.string(),
    }).optional(),
  }),
});

export const UnauthorizedErrorSchema = ErrorSchema.extend({
  error: z.object({
    code: z.literal("UNAUTHORIZED"),
    message: z.string(),
  }),
});

export const PaymentErrorSchema = ErrorSchema.extend({
  error: z.object({
    code: z.literal("PAYMENT_FAILED"),
    message: z.string(),
    details: z.object({
      provider: z.string(),
      providerCode: z.string().optional(),
      lastFour: z.string().optional(),
    }).optional(),
  }),
});

// === TYPE EXPORTS ===

export type ApiError = z.infer<typeof ErrorSchema>;
export type ValidationError = z.infer<typeof ValidationErrorSchema>;
export type NotFoundError = z.infer<typeof NotFoundErrorSchema>;
export type UnauthorizedError = z.infer<typeof UnauthorizedErrorSchema>;
export type PaymentError = z.infer<typeof PaymentErrorSchema>;

// === ERROR FACTORY FUNCTIONS ===

export function createValidationError(
  message: string,
  details?: Array<{ field: string; message: string; code?: string }>
): ValidationError {
  return ValidationErrorSchema.parse({
    success: false,
    error: {
      code: "VALIDATION_ERROR",
      message,
      details,
      timestamp: new Date().toISOString(),
    },
  });
}

export function createNotFoundError(
  resource: string,
  id: string,
  message?: string
): NotFoundError {
  return NotFoundErrorSchema.parse({
    success: false,
    error: {
      code: "NOT_FOUND",
      message: message || `${resource} with id ${id} not found`,
      details: { resource, id },
      timestamp: new Date().toISOString(),
    },
  });
}

export function createUnauthorizedError(
  message: string = "Authentication required"
): UnauthorizedError {
  return UnauthorizedErrorSchema.parse({
    success: false,
    error: {
      code: "UNAUTHORIZED",
      message,
      timestamp: new Date().toISOString(),
    },
  });
}

export function createPaymentError(
  message: string,
  provider: string,
  providerCode?: string,
  lastFour?: string
): PaymentError {
  return PaymentErrorSchema.parse({
    success: false,
    error: {
      code: "PAYMENT_FAILED",
      message,
      details: { provider, providerCode, lastFour },
      timestamp: new Date().toISOString(),
    },
  });
}

export function createInternalError(
  message: string = "An internal error occurred"
): ApiError {
  return ErrorSchema.parse({
    success: false,
    error: {
      code: "INTERNAL_ERROR",
      message,
      timestamp: new Date().toISOString(),
    },
  });
}

// === ERROR RESPONSE HELPERS ===

export class ErrorResponse {
  static validation(message: string, details?: ValidationError['error']['details']) {
    return createValidationError(message, details);
  }

  static notFound(resource: string, id: string, message?: string) {
    return createNotFoundError(resource, id, message);
  }

  static unauthorized(message?: string) {
    return createUnauthorizedError(message);
  }

  static payment(message: string, provider: string, providerCode?: string, lastFour?: string) {
    return createPaymentError(message, provider, providerCode, lastFour);
  }

  static internal(message?: string) {
    return createInternalError(message);
  }

  static custom(code: ApiError['error']['code'], message: string, details?: unknown): ApiError {
    return ErrorSchema.parse({
      success: false,
      error: {
        code,
        message,
        details,
        timestamp: new Date().toISOString(),
      },
    });
  }
}

// === ERROR TYPE GUARDS ===

export function isValidationError(error: unknown): error is ValidationError {
  return ValidationErrorSchema.safeParse(error).success;
}

export function isNotFoundError(error: unknown): error is NotFoundError {
  return NotFoundErrorSchema.safeParse(error).success;
}

export function isUnauthorizedError(error: unknown): error is UnauthorizedError {
  return UnauthorizedErrorSchema.safeParse(error).success;
}

export function isPaymentError(error: unknown): error is PaymentError {
  return PaymentErrorSchema.safeParse(error).success;
}

export function isApiError(error: unknown): error is ApiError {
  return ErrorSchema.safeParse(error).success;
}
