// === OPENAPI REGISTRY ===
// Central registry for all OpenAPI documentation generated from Zod schemas

import { extendZodWithOpenApi } from "@asteasolutions/zod-to-openapi";
import { z } from "zod";
import { ErrorSchema } from "../schemas/error";
import {
  CreateOrderSchema,
  GetOrdersSchema,
  UpdateOrderSchema,
  UpdateOrderStatusSchema
} from "../schemas/orders";

// Extend Zod with OpenAPI support
extendZodWithOpenApi(z);

// === OPENAPI COMPONENTS ===

// Register all schemas with OpenAPI extensions
export const OpenApiSchemas = {
  // Request schemas
  CreateOrderSchema: CreateOrderSchema.openapi({
    title: "Create Order Request",
    description: "Request payload for creating a new order",
    examples: [
      {
        sellerId: "seller_123",
        customerId: "customer_456",
        items: [
          {
            productId: "product_789",
            quantity: 2,
          },
        ],
        paymentType: "CASH_ON_DELIVERY",
        notes: "Customer prefers delivery after 6 PM",
      },
    ],
  }),

  UpdateOrderSchema: UpdateOrderSchema.openapi({
    title: "Update Order Request",
    description: "Request payload for updating an existing order",
  }),

  UpdateOrderStatusSchema: UpdateOrderStatusSchema.openapi({
    title: "Update Order Status Request",
    description: "Request payload for updating order status",
  }),

  GetOrdersQuerySchema: GetOrdersSchema.openapi({
    title: "Get Orders Query Parameters",
    description: "Query parameters for listing orders",
  }),

  ErrorSchema: ErrorSchema.openapi({
    title: "Error Response",
    description: "Standard error response format",
    examples: [
      {
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid input data",
          details: [
            {
              field: "totalMinor",
              message: "Must be a positive integer",
            },
          ],
          timestamp: "2023-12-01T10:00:00Z",
        },
      },
    ],
  }),
};

// === OPENAPI PATHS ===

export const OpenApiPaths = {
  // Orders endpoints
  "/api/v1/orders": {
    get: {
      summary: "List Orders",
      description: "Retrieve a paginated list of orders for the authenticated seller",
      tags: ["Orders"],
      parameters: [
        {
          name: "page",
          in: "query",
          required: false,
          schema: { type: "integer", minimum: 1, default: 1 },
        },
        {
          name: "limit",
          in: "query",
          required: false,
          schema: { type: "integer", minimum: 1, maximum: 100, default: 20 },
        },
        {
          name: "status",
          in: "query",
          required: false,
          schema: {
            type: "string",
            enum: ["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]
          },
        },
        {
          name: "paymentStatus",
          in: "query",
          required: false,
          schema: {
            type: "string",
            enum: ["PENDING", "PAID", "FAILED", "REFUNDED"]
          },
        },
        {
          name: "customerId",
          in: "query",
          required: false,
          schema: { type: "string" },
        },
      ],
      responses: {
        200: {
          description: "Orders retrieved successfully",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/OrderListResponseSchema" },
            },
          },
        },
        400: {
          description: "Invalid query parameters",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        401: {
          description: "Unauthorized",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
      },
      security: [{ bearerAuth: [] }],
    },
    post: {
      summary: "Create Order",
      description: "Create a new order with the specified items and payment type",
      tags: ["Orders"],
      requestBody: {
        required: true,
        content: {
          "application/json": {
            schema: { $ref: "#/components/schemas/CreateOrderSchema" },
          },
        },
      },
      responses: {
        201: {
          description: "Order created successfully",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/OrderCreateResponseSchema" },
            },
          },
        },
        400: {
          description: "Invalid order data",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        401: {
          description: "Unauthorized",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
      },
      security: [{ bearerAuth: [] }],
    },
  },

  "/api/v1/orders/{id}": {
    get: {
      summary: "Get Order",
      description: "Retrieve detailed information about a specific order",
      tags: ["Orders"],
      parameters: [
        {
          name: "id",
          in: "path",
          required: true,
          schema: { type: "string" },
          description: "Order ID",
        },
      ],
      responses: {
        200: {
          description: "Order retrieved successfully",
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  success: { type: "boolean", const: true },
                  data: {
                    type: "object",
                    properties: {
                      order: { $ref: "#/components/schemas/OrderResponseSchema" },
                    },
                  },
                },
              },
            },
          },
        },
        404: {
          description: "Order not found",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        401: {
          description: "Unauthorized",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
      },
      security: [{ bearerAuth: [] }],
    },
    put: {
      summary: "Update Order",
      description: "Update an existing order with new information",
      tags: ["Orders"],
      parameters: [
        {
          name: "id",
          in: "path",
          required: true,
          schema: { type: "string" },
          description: "Order ID",
        },
      ],
      requestBody: {
        required: true,
        content: {
          "application/json": {
            schema: { $ref: "#/components/schemas/UpdateOrderSchema" },
          },
        },
      },
      responses: {
        200: {
          description: "Order updated successfully",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/OrderUpdateResponseSchema" },
            },
          },
        },
        400: {
          description: "Invalid update data",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        404: {
          description: "Order not found",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        401: {
          description: "Unauthorized",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
      },
      security: [{ bearerAuth: [] }],
    },
  },

  "/api/v1/orders/{id}/status": {
    put: {
      summary: "Update Order Status",
      description: "Update the status of an existing order",
      tags: ["Orders"],
      parameters: [
        {
          name: "id",
          in: "path",
          required: true,
          schema: { type: "string" },
          description: "Order ID",
        },
      ],
      requestBody: {
        required: true,
        content: {
          "application/json": {
            schema: { $ref: "#/components/schemas/UpdateOrderStatusSchema" },
          },
        },
      },
      responses: {
        200: {
          description: "Order status updated successfully",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/OrderUpdateResponseSchema" },
            },
          },
        },
        400: {
          description: "Invalid status transition",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        404: {
          description: "Order not found",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
        401: {
          description: "Unauthorized",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ErrorSchema" },
            },
          },
        },
      },
      security: [{ bearerAuth: [] }],
    },
  },
};

// === OPENAPI INFO AND COMPONENTS ===

export const OpenApiDocument = {
  openapi: "3.0.0",
  info: {
    title: "Order Management API",
    version: "1.0.0",
    description: "Production-grade order management system with contract enforcement",
    contact: {
      name: "API Support",
      email: "api-support@example.com",
    },
  },
  servers: [
    {
      url: "http://localhost:3000",
      description: "Development server",
    },
    {
      url: "https://api.example.com",
      description: "Production server",
    },
  ],
  components: {
    schemas: Object.fromEntries(
      Object.entries(OpenApiSchemas).map(([key, schema]) => [key, schema])
    ),
    securitySchemes: {
      bearerAuth: {
        type: "http",
        scheme: "bearer",
        bearerFormat: "JWT",
        description: "JWT authentication token",
      },
    },
  },
  paths: OpenApiPaths,
  tags: [
    {
      name: "Orders",
      description: "Order management operations",
    },
  ],
};
