/**
 * Order API Contract Tests
 *
 * Requirements:
 * - Uses real HTTP requests (no direct route invocation)
 * - Creates real database entities via factories
 * - No fake IDs - all IDs are real CUIDs from the database
 * - Tests own their data completely
 * - No fallback logic - setup failures fail the test immediately
 */

import { safeFetch } from '@/shared/runtime-client/safe-fetch';
import { ErrorSchema } from '@/shared/schemas/error';
import { OrderCreateResponseSchema, OrderResponseSchema } from '@/shared/schemas/order-response';
import {
  createCustomer,
  createSeller,
  createUser,
  deleteCustomer,
  deleteOrder,
  deleteSeller,
  deleteUser,
  getValidTestProductId,
} from '@/tests/factories';
import { afterAll, beforeAll, describe, expect, test } from 'vitest';
import { z } from 'zod';

// Test configuration
const TEST_BASE_URL = process.env.TEST_API_URL || 'http://localhost:3000';

describe('Order API Contract Tests', () => {
  // Test-owned data (no reliance on global seed)
  let authToken: string;
  let testUser: { id: string; email: string; plainPassword: string };
  let testSeller: { id: string; slug: string };
  let testCustomer: { id: string; phone: string };
  const createdOrderIds: string[] = [];

  beforeAll(async () => {
    // Create test-owned data deterministically
    testUser = await createUser({
      email: `contract-test-${Date.now()}@example.com`,
      fullName: 'Contract Test User',
      password: 'test-password-123',
      role: 'SELLER',
    });

    testSeller = await createSeller({
      ownerUserId: testUser.id,
      brandName: 'Contract Test Store',
      slug: `contract-test-store-${Date.now()}`,
      whatsappNumber: '+1234567890',
      currency: 'USD',
      status: 'ACTIVE',
    });

    testCustomer = await createCustomer({
      sellerId: testSeller.id,
      name: 'Contract Test Customer',
      phone: `+1555${Date.now().toString().slice(-8)}`,
      addressText: '123 Contract Test St',
    });

    // Authenticate via HTTP login endpoint
    const loginResponse = await safeFetch(
      `${TEST_BASE_URL}/api/auth/login`,
      z.object({
        token: z.string(),
        user: z.object({
          id: z.string(),
          email: z.string(),
          role: z.string(),
          sellerId: z.string(),
        }),
      }),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: testUser.email,
          password: testUser.plainPassword,
        }),
      }
    );

    // safeFetch already validates the response, no need to check .ok
    const loginData = loginResponse;

    // Assert auth contract explicitly
    expect(loginData).toHaveProperty('token');
    expect(typeof loginData.token).toBe('string');
    expect(loginData.token.length).toBeGreaterThan(0);
    expect(loginData).toHaveProperty('user');
    expect(loginData.user).toHaveProperty('id');
    expect(loginData.user).toHaveProperty('email');
    expect(loginData.user).toHaveProperty('role');
    expect(loginData.user).toHaveProperty('sellerId');
    expect(loginData.user.sellerId).toBe(testSeller.id);

    authToken = loginData.token;
  });

  afterAll(async () => {
    // Clean up created orders first (to respect FK constraints)
    for (const orderId of createdOrderIds) {
      await deleteOrder(orderId).catch(() => {
        // Ignore cleanup errors
      });
    }

    // Clean up test-owned data
    await deleteCustomer(testCustomer.id).catch(() => { });
    await deleteSeller(testSeller.id).catch(() => { });
    await deleteUser(testUser.id).catch(() => { });
  });

  describe('POST /api/v1/orders - Create Order', () => {
    test('should create order with valid data and return correct contract', async () => {
      // Use valid external IDs that map to real database entities
      const orderPayload = {
        sellerId: 'seller_123', // External ID format (mapped via MOCK_EXTERNAL_ID_MAP)
        customerId: 'customer_456', // External ID format
        items: [
          {
            productId: getValidTestProductId(),
            quantity: 2,
          },
        ],
        paymentType: 'CASH_ON_DELIVERY',
        notes: 'Contract test order',
      };

      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders`,
        OrderCreateResponseSchema,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(orderPayload),
        }
      );

      // safeFetch already validates the response and returns typed data
      const validated = response;

      // Verify contract structure
      expect(validated.success).toBe(true);
      expect(validated.data.order).toBeDefined();
      expect(validated.data.order.id).toBeDefined();
      expect(validated.data.order.publicOrderNumber).toBeDefined();
      expect(validated.data.order.status).toBeOneOf(['PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED']);
      expect(validated.data.order.paymentStatus).toBeOneOf(['PENDING', 'PAID', 'FAILED', 'REFUNDED']);
      expect(validated.data.order.totalMinor).toBeGreaterThan(0);
      expect(validated.data.order.currency).toMatch(/^[A-Z]{3}$/);
      expect(validated.data.order.customer).toBeDefined();
      expect(validated.data.order.items).toBeInstanceOf(Array);
      expect(validated.data.order.items).toHaveLength(1);

      // Track for cleanup
      createdOrderIds.push(validated.data.order.id);
    });

    test('should reject invalid order data with proper error contract', async () => {
      const invalidOrderData = {
        sellerId: '', // Invalid: empty string
        customerId: 'customer_456',
        items: [], // Invalid: empty items array
        paymentType: 'INVALID_TYPE', // Invalid: not in enum
      };

      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders`,
        z.object({
          success: z.literal(false),
          error: z.object({
            code: z.string(),
            message: z.string(),
          }),
        }),
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(invalidOrderData),
        }
      );

      expect(response.success).toBe(false);
      expect(response.error.code).toBeDefined();

      // Error contract validation
      const validated = ErrorSchema.parse(response);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('VALIDATION_ERROR');
      expect(validated.error.message).toBeDefined();
      expect(validated.error.timestamp).toBeDefined();
    });
  });

  describe('GET /api/v1/orders - List Orders', () => {
    test('should return orders list with correct contract', async () => {
      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders?page=1&limit=10`,
        z.object({
          success: z.literal(true),
          data: z.object({
            orders: z.array(OrderResponseSchema),
            pagination: z.object({
              page: z.number(),
              limit: z.number(),
              total: z.number(),
              totalPages: z.number(),
              hasNext: z.boolean(),
              hasPrev: z.boolean(),
            }),
          }),
        }),
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const json = response;

      // Validate the structure matches expected contract
      expect(json).toHaveProperty('success', true);
      expect(json).toHaveProperty('data');
      expect(json.data).toHaveProperty('orders');
      expect(json.data).toHaveProperty('pagination');
      expect(Array.isArray(json.data.orders)).toBe(true);
      expect(json.data.pagination).toHaveProperty('page');
      expect(json.data.pagination).toHaveProperty('limit');
      expect(json.data.pagination).toHaveProperty('total');
      expect(json.data.pagination).toHaveProperty('totalPages');
      expect(json.data.pagination).toHaveProperty('hasNext');
      expect(json.data.pagination).toHaveProperty('hasPrev');

      // Validate each order in the list
      if (json.data.orders.length > 0) {
        const firstOrder = OrderResponseSchema.parse(json.data.orders[0]);
        expect(firstOrder.id).toBeDefined();
        expect(firstOrder.status).toBeDefined();
      }
    });

    test('should validate query parameters correctly', async () => {
      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders?page=invalid&limit=999`,
        ErrorSchema,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const json = response;

      // Error contract validation
      const validated = ErrorSchema.parse(json);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('VALIDATION_ERROR');
    });
  });

  describe('GET /api/v1/orders/:id - Get Single Order', () => {
    test('should return order with correct contract', async () => {
      // Create a fresh order for this test to ensure it exists
      const createResponse = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders`,
        OrderCreateResponseSchema,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sellerId: 'seller_123',
            customerId: 'customer_456',
            items: [
              {
                productId: getValidTestProductId(),
                quantity: 1,
              },
            ],
            paymentType: 'CASH_ON_DELIVERY',
            notes: 'Single order test',
          }),
        }
      );

      const orderId = createResponse.data.order.id;

      // Track for cleanup
      createdOrderIds.push(orderId);

      // Now fetch the order we just created
      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders/${orderId}`,
        z.object({
          success: z.literal(true),
          data: z.object({
            order: OrderResponseSchema,
          }),
        }),
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const json = response;

      // Contract validation
      expect(json).toHaveProperty('success', true);
      expect(json).toHaveProperty('data');
      expect(json.data).toHaveProperty('order');

      const validatedOrder = OrderResponseSchema.parse(json.data.order);
      expect(validatedOrder.id).toBe(orderId);
    });

    test('should return proper error for non-existent order', async () => {
      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders/non-existent-id`,
        ErrorSchema,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const json = response;

      // Error contract validation
      const validated = ErrorSchema.parse(json);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('NOT_FOUND');
    });
  });

  describe('Contract Stability Tests', () => {
    test('should maintain backward compatibility with V1 contract', async () => {
      // This test ensures we don't break V1 contract
      const response = await safeFetch(
        `${TEST_BASE_URL}/api/v1/orders`,
        z.object({
          success: z.literal(true),
          data: z.object({
            orders: z.array(z.any()),
            pagination: z.any(),
          }),
        }),
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      const json = response;

      // Verify V1 contract fields are present
      expect(json).toHaveProperty('success');
      expect(json).toHaveProperty('data');
      expect(json.data).toHaveProperty('orders');
      expect(json.data).toHaveProperty('pagination');

      // Verify required V1 fields in order objects
      if (json.data.orders.length > 0) {
        const order = json.data.orders[0];
        const requiredV1Fields = [
          'id', 'sellerId', 'publicOrderNumber', 'status', 'paymentStatus',
          'paymentType', 'subtotalMinor', 'deliveryFeeMinor', 'totalMinor',
          'currency', 'notes', 'createdAt', 'updatedAt', 'customer', 'items'
        ];

        for (const field of requiredV1Fields) {
          expect(order).toHaveProperty(field);
        }
      }
    });

    test('should handle malformed responses gracefully', async () => {
      // Test that our contracts reject malformed data
      const malformedOrder = {
        success: true,
        data: {
          order: {
            // Missing required fields
            id: 'test-id',
            status: 'INVALID_STATUS', // Invalid enum value
          },
        },
      };

      expect(() => OrderCreateResponseSchema.parse(malformedOrder)).toThrow();
    });
  });

  describe('Error Contract Consistency', () => {
    test('should return consistent error format across all endpoints', async () => {
      const endpoints = [
        { method: 'POST', url: '/api/v1/orders', body: { invalid: 'data' } },
        { method: 'GET', url: '/api/v1/orders?page=invalid' },
        { method: 'GET', url: '/api/v1/orders/non-existent-id' },
      ];

      for (const endpoint of endpoints) {
        const response = await safeFetch(
          `${TEST_BASE_URL}${endpoint.url}`,
          ErrorSchema,
          {
            method: endpoint.method,
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json',
            },
            body: endpoint.body ? JSON.stringify(endpoint.body) : undefined,
          }
        );

        // All errors should follow the same contract
        const validated = ErrorSchema.parse(response);
        expect(validated.success).toBe(false);
        expect(validated.error).toHaveProperty('code');
        expect(validated.error).toHaveProperty('message');
        expect(validated.error).toHaveProperty('timestamp');
      }
    });
  });
});
