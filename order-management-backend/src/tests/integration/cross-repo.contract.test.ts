// === CROSS-REPO CONTRACT TESTS ===
// Tests that prove sellora and runtime core work together correctly

import { GatewayClient } from "@/shared/runtime-client/gateway-client";
import { ErrorSchema } from "@/shared/schemas/error";
import { OrderResponseSchema } from "@/shared/schemas/order-response";
import { CreateOrderSchema } from "@/shared/schemas/orders";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { z } from "zod";

// Response type schemas for contract validation
const CreateOrderResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    order: OrderResponseSchema,
  }),
});

const GetOrderResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    order: OrderResponseSchema,
  }),
});

const ListOrdersResponseSchema = z.object({
  success: z.literal(true),
  data: z.object({
    orders: z.array(OrderResponseSchema),
    pagination: z.object({
      page: z.number(),
      limit: z.number(),
      total: z.number(),
      totalPages: z.number(),
    }),
  }),
});

// Test configuration
const RUNTIME_API_URL = process.env.RUNTIME_API_URL || "http://localhost:3000";
// Get a real token for testing
const TEST_SELLER_TOKEN = process.env.TEST_SELLER_TOKEN || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImNtbnJpODJoNzAwMDAxMTRnMDJoZXU0azYiLCJlbWFpbCI6ImRlbW9Ac2VsbGVyLmNvbSIsInJvbGUiOiJTRUxMRVIiLCJzZWxsZXJJZCI6ImNtbnJpODJydTAwMDIxMTRnNXV4eG53cnYiLCJpYXQiOjE3NzU3NDA4MjQsImV4cCI6MTc3NjM0NTYyNH0.7563tWJYe2-TPC_-3sMPRZYh-DsAe4PqUwfPVJjNaSg";

describe("Cross-Repo Contract Tests", () => {
  let gatewayClient: GatewayClient;
  let createdOrderId: string;

  beforeAll(() => {
    gatewayClient = GatewayClient.withToken(RUNTIME_API_URL, TEST_SELLER_TOKEN, {
      timeoutMs: 10000,
      retryAttempts: 3,
    });
  });

  afterAll(async () => {
    // Cleanup test data
    if (createdOrderId) {
      try {
        await gatewayClient.delete(`/api/v1/orders/${createdOrderId}`);
      } catch {
        // Ignore cleanup errors
      }
    }
  });

  describe("Request/Response Contract Validation", () => {
    test("sellora request matches runtime contract", () => {
      // This simulates what sellora would send
      const selloraRequest = {
        sellerId: "seller_123",
        customerId: "customer_456",
        items: [
          {
            productId: "product_789",
            quantity: 2,
          },
        ],
        paymentType: "CASH_ON_DELIVERY",
        notes: "Test order from sellora",
      };

      // Validate that sellora's request matches runtime's expected schema
      expect(() => CreateOrderSchema.parse(selloraRequest)).not.toThrow();

      const validated = CreateOrderSchema.parse(selloraRequest);
      expect(validated.sellerId).toBe("seller_123");
      expect(validated.items).toHaveLength(1);
      expect(validated.items[0].quantity).toBe(2);
    });

    test("runtime response matches sellora expectations", () => {
      // This simulates what runtime would return
      const runtimeResponse = {
        id: "cmnrc36r00002pn1yeyixi1sn",
        sellerId: "cmnrc36r00002pn1yeyixi1sn",
        publicOrderNumber: "ORD-123",
        status: "PENDING",
        paymentStatus: "PENDING",
        paymentType: "CASH_ON_DELIVERY",
        subtotalMinor: 2000,
        deliveryFeeMinor: 500,
        totalMinor: 2500,
        currency: "USD",
        notes: null,
        createdAt: "2023-12-01T10:00:00Z",
        updatedAt: "2023-12-01T10:00:00Z",
        customer: {
          id: "cmnrc36r00002pn1yeyixi1sn",
          name: "John Doe",
          phone: "+1234567890",
          addressText: "123 Main St",
        },
        items: [
          {
            id: "cmnrc36r00002pn1yeyixi1sn",
            productId: "cmnrc36r00002pn1yeyixi1sn",
            productNameSnapshot: "Test Product",
            unitPriceMinor: 1000,
            quantity: 2,
            lineTotalMinor: 2000,
          },
        ],
      };

      // Validate that runtime's response matches sellora's expected schema
      expect(() => OrderResponseSchema.parse(runtimeResponse)).not.toThrow();

      const validated = OrderResponseSchema.parse(runtimeResponse);
      expect(validated.id).toBe("cmnrc36r00002pn1yeyixi1sn");
      expect(validated.status).toBe("PENDING");
      expect(validated.items).toHaveLength(1);
    });
  });

  describe("Live Integration Tests", () => {
    test("end-to-end order creation and retrieval flow", async () => {
      // Step 0: Log seller ID from token for verification
      const jwt = require('jsonwebtoken');
      const token = TEST_SELLER_TOKEN;
      const decoded = jwt.decode(token, 'dev-secret-32-characters-minimum-for-security');
      console.log("DEBUG: Seller ID from token:", decoded.sellerId);
      console.log("DEBUG: User ID from token:", decoded.id);

      const orderData = CreateOrderSchema.parse({
        sellerId: "seller_123", // External ID format
        customerId: "customer_456", // External ID format
        items: [
          {
            productId: "product_789", // External ID format
            quantity: 2,
          },
        ],
        paymentType: "CASH_ON_DELIVERY",
        notes: "Test order from sellora",
      });

      console.log("DEBUG: Order data for creation:", JSON.stringify(orderData, null, 2));

      // Create order via runtime API
      const createResponse = await gatewayClient.post("/api/v1/orders", orderData);

      // Validate response contract
      const validatedCreateResponse = CreateOrderResponseSchema.parse(createResponse);
      expect(validatedCreateResponse.success).toBe(true);
      expect(validatedCreateResponse.data.order).toBeDefined();

      // Validate order data contract
      const createdOrder = validatedCreateResponse.data.order;
      expect(createdOrder.id).toBeDefined();
      expect(createdOrder.status).toMatch(/^(PENDING|CONFIRMED|PREPARING|READY|COMPLETED|CANCELLED)$/);
      expect(createdOrder.paymentStatus).toMatch(/^(PENDING|PAID|FAILED|REFUNDED)$/);

      // Step 1: Log created order ID
      console.log("DEBUG: STEP 1 - Created order ID:", createdOrder.id);
      console.log("DEBUG: STEP 1 - Created order sellerId:", createdOrder.sellerId);
      console.log("DEBUG: STEP 1 - Created order full data:", JSON.stringify(createdOrder, null, 2));

      // Step 2: Query DB immediately after create to confirm row exists
      const { PrismaClient } = require('@prisma/client');
      const prisma = new PrismaClient();
      const dbOrderAfterCreate = await prisma.order.findUnique({
        where: { id: createdOrder.id },
        include: { customer: true, orderItems: true }
      });
      console.log("DEBUG: STEP 2 - DB query after create - Order exists:", !!dbOrderAfterCreate);
      if (dbOrderAfterCreate) {
        console.log("DEBUG: STEP 2 - DB order sellerId:", dbOrderAfterCreate.sellerId);
        console.log("DEBUG: STEP 2 - DB order customerId:", dbOrderAfterCreate.customerId);
      }

      // Step 3: Now test retrieval in the same test flow
      console.log("DEBUG: STEP 3 - Attempting to fetch order ID:", createdOrder.id);

      // Step 4: Query DB immediately before retrieval to confirm row still exists
      const dbOrderBeforeRetrieve = await prisma.order.findUnique({
        where: { id: createdOrder.id }
      });
      console.log("DEBUG: STEP 4 - DB query before retrieval - Order exists:", !!dbOrderBeforeRetrieve);

      // Get order via runtime API
      let getResponse;
      try {
        getResponse = await gatewayClient.get(`/api/v1/orders/${createdOrder.id}`);
        console.log("DEBUG: STEP 5 - Retrieval successful");
      } catch (error) {
        console.log("DEBUG: STEP 5 - Retrieval failed with error:", error instanceof Error ? error.message : String(error));
        console.log("DEBUG: STEP 5 - Error details:", JSON.stringify(error instanceof Error ? error.message : error, null, 2));
        throw error;
      }

      // Validate response contract
      const validatedGetResponse = GetOrderResponseSchema.parse(getResponse);
      expect(validatedGetResponse.success).toBe(true);
      expect(validatedGetResponse.data.order).toBeDefined();

      // Validate order data contract
      const retrievedOrder = validatedGetResponse.data.order;
      expect(retrievedOrder.id).toBeDefined();
      expect(retrievedOrder.status).toMatch(/^(PENDING|CONFIRMED|PREPARING|READY|COMPLETED|CANCELLED)$/);
      expect(retrievedOrder.paymentStatus).toMatch(/^(PENDING|PAID|FAILED|REFUNDED)$/);

      // Step 6: Log exact ID used in retrieval and compare
      console.log("DEBUG: STEP 6 - Retrieved order ID:", retrievedOrder.id);
      console.log("DEBUG: STEP 6 - Retrieved order sellerId:", retrievedOrder.sellerId);
      console.log("DEBUG: STEP 6 - Retrieved order full data:", JSON.stringify(retrievedOrder, null, 2));

      // Validate contract consistency - same order returned
      expect(retrievedOrder.id).toBe(createdOrder.id);
      expect(retrievedOrder.sellerId).toBe(createdOrder.sellerId);
      expect(retrievedOrder.publicOrderNumber).toBe(createdOrder.publicOrderNumber);

      console.log("DEBUG: FINAL - Successfully retrieved order:", retrievedOrder.id);

      await prisma.$disconnect();

      // Store for cleanup
      createdOrderId = createdOrder.id;
    });

    test("order listing flow", async () => {
      // List orders via runtime API
      const listResponse = await gatewayClient.get("/api/v1/orders", {
        params: { page: 1, limit: 10 },
      });

      // Validate response contract
      const validatedListResponse = ListOrdersResponseSchema.parse(listResponse);
      expect(validatedListResponse.success).toBe(true);
      expect(validatedListResponse.data.orders).toBeDefined();
      expect(validatedListResponse.data.pagination).toBeDefined();
      expect(Array.isArray(validatedListResponse.data.orders)).toBe(true);

      // Validate each order in the list
      validatedListResponse.data.orders.forEach(order => {
        expect(() => OrderResponseSchema.parse(order)).not.toThrow();
      });
    });
  });

  describe("Error Contract Validation", () => {
    test("invalid request returns proper error contract", async () => {
      const invalidOrderData = {
        sellerId: "", // Invalid: empty string
        customerId: "test-customer",
        items: [], // Invalid: empty array
        paymentType: "INVALID_TYPE", // Invalid: not in enum
      };

      try {
        await gatewayClient.post("/api/v1/orders", invalidOrderData);
        expect.fail("Should have thrown an error");
      } catch (error) {
        // Validate error contract
        if (error instanceof Error && "response" in error) {
          const errorResponse = JSON.parse((error as any).response);

          expect(() => ErrorSchema.parse(errorResponse)).not.toThrow();

          const validated = ErrorSchema.parse(errorResponse);
          expect(validated.success).toBe(false);
          expect(validated.error.code).toBe("VALIDATION_ERROR");
          expect(validated.error.message).toBeDefined();
          expect(validated.error.timestamp).toBeDefined();
        }
      }
    });

    test("non-existent resource returns proper error contract", async () => {
      try {
        await gatewayClient.get("/api/v1/orders/non-existent-id");
        expect.fail("Should have thrown an error");
      } catch (error) {
        // Validate error contract
        if (error instanceof Error && "response" in error) {
          const errorResponse = JSON.parse((error as any).response);

          expect(() => ErrorSchema.parse(errorResponse)).not.toThrow();

          const validated = ErrorSchema.parse(errorResponse);
          expect(validated.success).toBe(false);
          expect(validated.error.code).toBe("NOT_FOUND");
        }
      }
    });
  });

  describe("Data Type Consistency", () => {
    test("numeric fields are properly typed", () => {
      const orderResponse = {
        id: "cmnrc36r00002pn1yeyixi1sn",
        sellerId: "cmnrc36r00002pn1yeyixi1sn",
        publicOrderNumber: "ORD-123",
        status: "PENDING",
        paymentStatus: "PENDING",
        paymentType: "CASH_ON_DELIVERY",
        subtotalMinor: 2000,
        deliveryFeeMinor: 500,
        totalMinor: 2500,
        currency: "USD",
        notes: null,
        createdAt: "2023-12-01T10:00:00Z",
        updatedAt: "2023-12-01T10:00:00Z",
        customer: {
          id: "cmnrc36r00002pn1yeyixi1sn",
          name: "John Doe",
          phone: "+1234567890",
          addressText: "123 Main St",
        },
        items: [
          {
            id: "cmnrc36r00002pn1yeyixi1sn",
            productId: "cmnrc36r00002pn1yeyixi1sn",
            productNameSnapshot: "Test Product",
            unitPriceMinor: 1000,
            quantity: 2,
            lineTotalMinor: 2000,
          },
        ],
      };

      const validated = OrderResponseSchema.parse(orderResponse);

      // Verify numeric fields are numbers (not strings)
      expect(typeof validated.subtotalMinor).toBe("number");
      expect(typeof validated.deliveryFeeMinor).toBe("number");
      expect(typeof validated.totalMinor).toBe("number");
      expect(typeof validated.items[0].unitPriceMinor).toBe("number");
      expect(typeof validated.items[0].quantity).toBe("number");
      expect(typeof validated.items[0].lineTotalMinor).toBe("number");

      // Verify they are integers
      expect(Number.isInteger(validated.subtotalMinor)).toBe(true);
      expect(Number.isInteger(validated.totalMinor)).toBe(true);
      expect(Number.isInteger(validated.items[0].quantity)).toBe(true);
    });

    test("enum fields are properly constrained", () => {
      const orderResponse = {
        id: "cmnrc36r00002pn1yeyixi1sn",
        sellerId: "cmnrc36r00002pn1yeyixi1sn",
        publicOrderNumber: "ORD-123",
        status: "PENDING",
        paymentStatus: "PENDING",
        paymentType: "CASH_ON_DELIVERY",
        subtotalMinor: 2000,
        deliveryFeeMinor: 500,
        totalMinor: 2500,
        currency: "USD",
        notes: null,
        createdAt: "2023-12-01T10:00:00Z",
        updatedAt: "2023-12-01T10:00:00Z",
        customer: {
          id: "cmnrc36r00002pn1yeyixi1sn",
          name: "John Doe",
          phone: "+1234567890",
          addressText: "123 Main St",
        },
        items: [],
      };

      const validated = OrderResponseSchema.parse(orderResponse);

      // Verify enum values are valid
      expect(["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED"]).toContain(validated.status);
      expect(["PENDING", "PAID", "FAILED", "REFUNDED"]).toContain(validated.paymentStatus);
      expect(["CASH_ON_DELIVERY", "CARD", "WALLET"]).toContain(validated.paymentType);
      expect(validated.currency).toMatch(/^[A-Z]{3}$/);
    });
  });

  describe("Performance and Reliability", () => {
    test("requests complete within reasonable time", async () => {
      const startTime = Date.now();

      await gatewayClient.get("/api/v1/orders", {
        params: { page: 1, limit: 5 },
      });

      const duration = Date.now() - startTime;

      // Should complete within 5 seconds
      expect(duration).toBeLessThan(5000);
    });

    test("concurrent requests are handled properly", async () => {
      const requests = Array(5).fill(null).map(() =>
        gatewayClient.get("/api/v1/orders", {
          params: { page: 1, limit: 5 },
        })
      );

      const responses = await Promise.all(requests);

      // All requests should succeed
      responses.forEach((response: any) => {
        expect(response.success).toBe(true);
        expect(response.data.orders).toBeDefined();
      });
    });
  });
});

// === CONTRACT TEST UTILITIES ===

export class ContractTestUtils {
  static async validateContractConsistency(
    client: GatewayClient,
    endpoint: string,
    requestData: unknown,
    expectedResponseSchema: any
  ): Promise<void> {
    // Send request
    const response = await client.post(endpoint, requestData);

    // Validate response structure
    expect(() => expectedResponseSchema.parse(response)).not.toThrow();
  }

  static async validateErrorContract(
    client: GatewayClient,
    endpoint: string,
    invalidData: unknown,
    expectedErrorCode: string
  ): Promise<void> {
    try {
      await client.post(endpoint, invalidData);
      expect.fail("Should have thrown an error");
    } catch (error) {
      if (error instanceof Error && "response" in error) {
        const errorResponse = JSON.parse((error as any).response);
        const validated = ErrorSchema.parse(errorResponse);

        expect(validated.success).toBe(false);
        expect(validated.error.code).toBe(expectedErrorCode);
      }
    }
  }

  static generateTestData(): {
    validOrder: any;
    invalidOrder: any;
    validCustomer: any;
    invalidCustomer: any;
  } {
    return {
      validOrder: {
        sellerId: "seller_123",
        customerId: "customer_456",
        items: [{ productId: "product_789", quantity: 1 }],
        paymentType: "CASH_ON_DELIVERY",
      },
      invalidOrder: {
        sellerId: "",
        customerId: "customer_456",
        items: [],
        paymentType: "INVALID",
      },
      validCustomer: {
        name: "John Doe",
        phone: "+1234567890",
        addressText: "123 Main St",
      },
      invalidCustomer: {
        name: "",
        phone: "invalid",
        addressText: "",
      },
    };
  }
}
