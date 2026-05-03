// === CONTRACT TESTS ===
// Critical for enterprise-grade system validation

import { ErrorSchema } from '@/shared/schemas/error';
import { OrderCreateResponseSchema, OrderResponseSchema } from '@/shared/schemas/order-response';
import { CreateOrderSchema } from '@/shared/schemas/orders';
import { PrismaClient } from '@prisma/client';
import { afterAll, beforeAll, describe, expect, test } from 'vitest';

// Test configuration
const TEST_BASE_URL = process.env.TEST_API_URL || 'http://localhost:3000';

describe('Order API Contract Tests', () => {
  let authToken: string;
  let testOrderId: string;
  let sellerId: string;
  let customerId: string;

  beforeAll(async () => {
    // Use existing demo user from seed (demo@seller.com / demo123)
    const loginResponse = await fetch(`${TEST_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'demo@seller.com',
        password: 'demo123',
      }),
    });

    if (loginResponse.ok) {
      const loginData = await loginResponse.json();
      authToken = loginData.token;
      sellerId = loginData.user.sellerId;
      console.log('Auth setup successful, token acquired');
      console.log('Seller ID:', sellerId);
    } else {
      console.warn('Auth setup failed, tests may not work properly');
      console.error('Login response:', await loginResponse.text());
    }

    // Fetch customer ID dynamically from database to ensure test determinism
    // Since there's no customers API, we'll use a deterministic approach
    // by finding the customer for the authenticated seller
    const prisma = new PrismaClient();

    try {
      let customer = await prisma.customer.findFirst({
        where: { sellerId: sellerId },
      });

      if (!customer) {
        // Create a test customer for this seller
        customer = await prisma.customer.create({
          data: {
            sellerId: sellerId,
            name: 'Test Customer',
            phone: '+12345678901',
            addressText: 'Test Address',
          },
        });
        console.log('Created test customer:', customer.id);
      }

      customerId = customer.id;
      console.log('Using customer ID:', customerId);
    } catch (error) {
      console.warn('Failed to setup customer:', error);
      customerId = 'fallback-customer-id';
    } finally {
      await prisma.$disconnect();
    }
  });

  afterAll(async () => {
    // Cleanup test data if needed
    if (testOrderId && authToken) {
      try {
        await fetch(`${TEST_BASE_URL}/api/v1/orders/${testOrderId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        });
      } catch {
        // Ignore cleanup errors
      }
    }
  });

  describe('POST /api/v1/orders - Create Order', () => {
    test('should create order with valid data and return correct contract', async () => {
      console.log('Creating order with sellerId:', sellerId);
      console.log('Creating order with customerId:', customerId);

      const validOrderData = CreateOrderSchema.parse({
        sellerId: sellerId,
        customerId: customerId,
        items: [
          {
            productId: 'cm1234567890abcdef12345677', // Valid CUID format for test
            quantity: 2,
          },
        ],
        paymentType: 'CASH_ON_DELIVERY',
        notes: 'Test order',
      });

      console.log('Order data:', JSON.stringify(validOrderData, null, 2));

      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(validOrderData),
      });

      // Debug: Log full response details
      const raw = await response.text();
      console.log("Response status:", response.status);
      console.log("Response headers:", Object.fromEntries(response.headers.entries()));
      console.log("Response body:", raw);

      expect(response.ok).toBe(true);

      const json = JSON.parse(raw);

      // Contract validation - this should NOT throw
      expect(() => OrderCreateResponseSchema.parse(json)).not.toThrow();

      // Verify contract structure
      const validated = OrderCreateResponseSchema.parse(json);
      expect(validated.success).toBe(true);
      expect(validated.data.order).toBeDefined();
      expect(validated.data.order.id).toBeDefined();
      expect(validated.data.order.publicOrderNumber).toBeDefined();
      expect(validated.data.order.status).toMatch(/^(PENDING|CONFIRMED|PREPARING|READY|COMPLETED|CANCELLED)$/);

      // Store test order ID for subsequent tests
      testOrderId = validated.data.order.id;
      console.log('Test order ID stored:', testOrderId);

      // Store in global scope to survive test cleanup
      (globalThis as { testOrderId?: string }).testOrderId = testOrderId;
      expect(validated.data.order.paymentStatus).toMatch(/^(PENDING|PAID|FAILED|REFUNDED)$/);
      expect(validated.data.order.totalMinor).toBeGreaterThan(0);
      expect(validated.data.order.currency).toMatch(/^[A-Z]{3}$/);
      expect(validated.data.order.customer).toBeDefined();
      expect(validated.data.order.items).toBeInstanceOf(Array);
      expect(validated.data.order.items).toHaveLength(1);

      // Store for cleanup
      testOrderId = validated.data.order.id;
    });

    test('should reject invalid order data with proper error contract', async () => {
      const invalidOrderData = {
        sellerId: '', // Invalid: empty string
        customerId: 'test-customer-id',
        items: [], // Invalid: empty items array
        paymentType: 'INVALID_TYPE', // Invalid: not in enum
      };

      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(invalidOrderData),
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(400);

      const json = await response.json();

      // Error contract validation
      expect(() => ErrorSchema.parse(json)).not.toThrow();

      const validated = ErrorSchema.parse(json);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('VALIDATION_ERROR');
      expect(validated.error.message).toBeDefined();
      expect(validated.error.timestamp).toBeDefined();
    });
  });

  describe('GET /api/v1/orders - List Orders', () => {
    test('should return orders list with correct contract', async () => {
      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders?page=1&limit=10`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      expect(response.ok).toBe(true);

      const json = await response.json();

      // Contract validation - should not throw
      expect(() => {
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
          expect(() => OrderResponseSchema.parse(json.data.orders[0])).not.toThrow();
        }
      }).not.toThrow();
    });

    test('should validate query parameters correctly', async () => {
      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders?page=invalid&limit=999`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(400);

      const json = await response.json();

      // Error contract validation
      expect(() => ErrorSchema.parse(json)).not.toThrow();

      const validated = ErrorSchema.parse(json);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('VALIDATION_ERROR');
    });
  });

  describe('GET /api/v1/orders/:id - Get Single Order', () => {
    test('should return order with correct contract', async () => {
      // Create a fresh order for this test to ensure it exists
      const createResponse = await fetch(`${TEST_BASE_URL}/api/v1/orders`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sellerId: 'cmnr4cnhi0002r794t4fmc8kq',
          customerId: customerId,
          items: [
            {
              productId: 'cm1234567890abcdef12345677',
              quantity: 1,
            },
          ],
          paymentType: 'CASH_ON_DELIVERY',
          notes: 'Single order test',
        }),
      });

      expect(createResponse.ok).toBe(true);
      const createData = await createResponse.json();
      const orderId = createData.data.order.id;
      // Now fetch the order we just created
      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders/${orderId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      expect(response.ok).toBe(true);

      const json = await response.json();

      // Contract validation
      expect(() => {
        expect(json).toHaveProperty('success', true);
        expect(json).toHaveProperty('data');
        expect(json.data).toHaveProperty('order');
        expect(() => OrderResponseSchema.parse(json.data.order)).not.toThrow();
      }).not.toThrow();
    });

    test('should return proper error for non-existent order', async () => {
      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders/non-existent-id`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(404);

      const json = await response.json();

      // Error contract validation
      expect(() => ErrorSchema.parse(json)).not.toThrow();

      const validated = ErrorSchema.parse(json);
      expect(validated.success).toBe(false);
      expect(validated.error.code).toBe('NOT_FOUND');
    });
  });

  describe('Contract Stability Tests', () => {
    test('should maintain backward compatibility with V1 contract', async () => {
      // This test ensures we don't break V1 contract
      const response = await fetch(`${TEST_BASE_URL}/api/v1/orders`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });

      expect(response.ok).toBe(true);

      const json = await response.json();

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

        requiredV1Fields.forEach(field => {
          expect(order).toHaveProperty(field);
        });
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
        const response = await fetch(`${TEST_BASE_URL}${endpoint.url}`, {
          method: endpoint.method,
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
          body: endpoint.body ? JSON.stringify(endpoint.body) : undefined,
        });

        if (!response.ok) {
          const json = await response.json();

          // All errors should follow the same contract
          expect(() => ErrorSchema.parse(json)).not.toThrow();

          const validated = ErrorSchema.parse(json);
          expect(validated.success).toBe(false);
          expect(validated.error).toHaveProperty('code');
          expect(validated.error).toHaveProperty('message');
          expect(validated.error).toHaveProperty('timestamp');
        }
      }
    });
  });
});

// === CONTRACT TEST UTILITIES ===

export class ContractTestUtils {
  static async validateApiResponse<T>(
    response: Response,
    schema: { parse: (data: unknown) => T }
  ): Promise<T> {
    if (!response.ok) {
      throw new Error(`API returned ${response.status}: ${response.statusText}`);
    }

    const json = await response.json();
    return schema.parse(json);
  }

  static async validateApiError(
    response: Response,
    expectedCode?: string
  ): Promise<void> {
    expect(response.ok).toBe(false);

    const json = await response.json();
    const validated = ErrorSchema.parse(json);

    expect(validated.success).toBe(false);
    expect(validated.error).toHaveProperty('code');
    expect(validated.error).toHaveProperty('message');
    expect(validated.error).toHaveProperty('timestamp');

    if (expectedCode) {
      expect(validated.error.code).toBe(expectedCode);
    }
  }

  static createTestOrderData() {
    return CreateOrderSchema.parse({
      sellerId: 'test-seller-id',
      customerId: 'test-customer-id',
      items: [
        {
          productId: 'test-product-id',
          quantity: 1,
        },
      ],
      paymentType: 'CASH_ON_DELIVERY',
    });
  }
}
