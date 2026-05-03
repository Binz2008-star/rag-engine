#!/usr/bin/env tsx

/**
 * Release Validation Test Script
 *
 * This script performs a repeatable end-to-end test against the production environment
 * and captures exact request/response pairs as release proof.
 */

import { execSync } from 'child_process';
import { writeFileSync } from 'fs';

interface TestResult {
  testName: string;
  method: string;
  url: string;
  request: any;
  response: any;
  status: number;
  responseTime: number;
  success: boolean;
  error?: string;
}

interface ValidationSession {
  timestamp: string;
  environment: string;
  baseUrl: string;
  results: TestResult[];
  summary: {
    totalTests: number;
    passedTests: number;
    failedTests: number;
    averageResponseTime: number;
    success: boolean;
  };
}

class ReleaseValidator {
  private baseUrl: string;
  private jwtToken: string | null = null;
  private sellerSlug: string;
  private orderId: string | null = null;
  private productId: string | null = null;

  constructor(baseUrl: string, sellerSlug: string = 'test-store-2') {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.sellerSlug = sellerSlug;
  }

  async makeRequest(method: string, endpoint: string, body?: any, headers?: Record<string, string>): Promise<TestResult> {
    const url = `${this.baseUrl}${endpoint}`;
    const startTime = Date.now();

    let curlCommand = `curl -X ${method} "${url}"`;

    // Add headers
    if (headers) {
      Object.entries(headers).forEach(([key, value]) => {
        curlCommand += ` -H "${key}: ${value}"`;
      });
    }

    // Add body
    if (body) {
      curlCommand += ` -d '${JSON.stringify(body)}'`;
    }

    // Add response options
    curlCommand += ' -w "\\nHTTP_STATUS:%{http_code}\\nRESPONSE_TIME:%{time_total}\\n" -s';

    try {
      const output = execSync(curlCommand, { encoding: 'utf8', timeout: 30000 });
      const endTime = Date.now();
      const responseTime = endTime - startTime;

      // Parse the output
      const lines = output.split('\n');
      const httpStatusLine = lines.find(line => line.startsWith('HTTP_STATUS:'));
      const responseTimeLine = lines.find(line => line.startsWith('RESPONSE_TIME:'));

      const status = httpStatusLine ? parseInt(httpStatusLine.split(':')[1]) : 0;
      const curlResponseTime = responseTimeLine ? parseFloat(responseTimeLine.split(':')[1]) * 1000 : responseTime;

      // Extract response body (everything before HTTP_STATUS line)
      const httpStatusIndex = lines.findIndex(line => line.startsWith('HTTP_STATUS:'));
      const responseBody = httpStatusIndex > 0 ? lines.slice(0, httpStatusIndex).join('\n') : output;

      let parsedResponse;
      try {
        parsedResponse = JSON.parse(responseBody);
      } catch {
        parsedResponse = responseBody;
      }

      return {
        testName: `${method} ${endpoint}`,
        method,
        url,
        request: body,
        response: parsedResponse,
        status,
        responseTime: curlResponseTime,
        success: status >= 200 && status < 300
      };

    } catch (error: any) {
      return {
        testName: `${method} ${endpoint}`,
        method,
        url,
        request: body,
        response: null,
        status: 0,
        responseTime: Date.now() - startTime,
        success: false,
        error: error.message
      };
    }
  }

  async runHealthCheck(): Promise<TestResult> {
    return this.makeRequest('GET', '/api/health');
  }

  async authenticate(): Promise<TestResult> {
    const result = await this.makeRequest('POST', '/api/auth/login', {
      email: 'seller1@test.com',
      password: 'TestSeller123!'
    }, {
      'Content-Type': 'application/json'
    });

    if (result.success && result.response && result.response.token) {
      this.jwtToken = result.response.token;
    }

    return result;
  }

  async getProducts(): Promise<TestResult> {
    const headers = this.jwtToken ? { 'Authorization': `Bearer ${this.jwtToken}` } : {};
    const result = await this.makeRequest('GET', '/api/seller/products', undefined, headers);

    if (result.success && result.response && result.response.products && result.response.products.length > 0) {
      this.productId = result.response.products[0].id;
    }

    return result;
  }

  async createOrder(): Promise<TestResult> {
    if (!this.productId) {
      return {
        testName: 'POST /api/public/test-store-2/orders',
        method: 'POST',
        url: `${this.baseUrl}/api/public/test-store-2/orders`,
        request: null,
        response: null,
        status: 0,
        responseTime: 0,
        success: false,
        error: 'No product ID available'
      };
    }

    const orderPayload = {
      customerName: 'Release Validation Test',
      customerPhone: '+15551234567',
      addressText: '123 Validation Street, Test City',
      items: [
        {
          productId: this.productId,
          quantity: 1
        }
      ],
      notes: 'Release validation test order'
    };

    const result = await this.makeRequest('POST', `/api/public/${this.sellerSlug}/orders`, orderPayload);

    if (result.success && result.response && result.response.id) {
      this.orderId = result.response.id;
    }

    return result;
  }

  async updateOrderStatus(): Promise<TestResult> {
    if (!this.orderId || !this.jwtToken) {
      return {
        testName: 'PATCH /api/seller/orders/{id}/status',
        method: 'PATCH',
        url: `${this.baseUrl}/api/seller/orders/${this.orderId}/status`,
        request: null,
        response: null,
        status: 0,
        responseTime: 0,
        success: false,
        error: 'No order ID or JWT token available'
      };
    }

    const headers = {
      'Authorization': `Bearer ${this.jwtToken}`,
      'Content-Type': 'application/json'
    };

    const statusPayload = {
      status: 'CONFIRMED',
      reason: 'Release validation test'
    };

    return this.makeRequest('PATCH', `/api/seller/orders/${this.orderId}/status`, statusPayload, headers);
  }

  async verifyOrder(): Promise<TestResult> {
    if (!this.jwtToken) {
      return {
        testName: 'GET /api/seller/orders',
        method: 'GET',
        url: `${this.baseUrl}/api/seller/orders`,
        request: null,
        response: null,
        status: 0,
        responseTime: 0,
        success: false,
        error: 'No JWT token available'
      };
    }

    const headers = { 'Authorization': `Bearer ${this.jwtToken}` };
    return this.makeRequest('GET', '/api/seller/orders', undefined, headers);
  }

  async testInvalidTransition(): Promise<TestResult> {
    if (!this.orderId || !this.jwtToken) {
      return {
        testName: 'PATCH Invalid Status Transition',
        method: 'PATCH',
        url: `${this.baseUrl}/api/seller/orders/${this.orderId}/status`,
        request: null,
        response: null,
        status: 0,
        responseTime: 0,
        success: false,
        error: 'No order ID or JWT token available'
      };
    }

    const headers = {
      'Authorization': `Bearer ${this.jwtToken}`,
      'Content-Type': 'application/json'
    };

    // Try invalid status transition
    const invalidPayload = {
      status: 'INVALID_STATUS',
      reason: 'Test invalid transition'
    };

    const result = await this.makeRequest('PATCH', `/api/seller/orders/${this.orderId}/status`, invalidPayload, headers);

    // For invalid transitions, we expect a 400 response, which is actually correct behavior
    result.success = result.status === 400;

    return result;
  }

  async runFullValidation(): Promise<ValidationSession> {
    console.log('Starting release validation test...');
    console.log(`Environment: ${this.baseUrl}`);

    const results: TestResult[] = [];

    // Test 1: Health Check
    console.log('1. Testing health endpoint...');
    const healthResult = await this.runHealthCheck();
    results.push(healthResult);

    // Test 2: Authentication
    console.log('2. Testing authentication...');
    const authResult = await this.authenticate();
    results.push(authResult);

    // Test 3: Get Products
    console.log('3. Testing product retrieval...');
    const productsResult = await this.getProducts();
    results.push(productsResult);

    // Test 4: Create Order
    console.log('4. Testing order creation...');
    const orderResult = await this.createOrder();
    results.push(orderResult);

    // Test 5: Update Order Status
    console.log('5. Testing order status update...');
    const statusResult = await this.updateOrderStatus();
    results.push(statusResult);

    // Test 6: Verify Order
    console.log('6. Testing order verification...');
    const verifyResult = await this.verifyOrder();
    results.push(verifyResult);

    // Test 7: Invalid Transition Test
    console.log('7. Testing invalid transition handling...');
    const invalidResult = await this.testInvalidTransition();
    results.push(invalidResult);

    // Calculate summary
    const passedTests = results.filter(r => r.success).length;
    const failedTests = results.length - passedTests;
    const averageResponseTime = results.reduce((sum, r) => sum + r.responseTime, 0) / results.length;

    const session: ValidationSession = {
      timestamp: new Date().toISOString(),
      environment: this.baseUrl,
      baseUrl: this.baseUrl,
      results,
      summary: {
        totalTests: results.length,
        passedTests,
        failedTests,
        averageResponseTime: Math.round(averageResponseTime),
        success: failedTests === 0 && healthResult.success
      }
    };

    return session;
  }
}

async function main(): Promise<void> {
  const baseUrl = process.argv[2] || 'http://localhost:3000';
  const sellerSlug = process.argv[3] || 'test-store-2';
  const outputFile = process.argv[4] || `release-validation-${Date.now()}.json`;

  console.log(`Release Validation Test`);
  console.log(`Target: ${baseUrl}`);
  console.log(`Seller: ${sellerSlug}`);
  console.log(`Output: ${outputFile}`);
  console.log('');

  const validator = new ReleaseValidator(baseUrl, sellerSlug);

  try {
    const session = await validator.runFullValidation();

    // Save results to file
    writeFileSync(outputFile, JSON.stringify(session, null, 2));

    // Print summary
    console.log('');
    console.log('=== VALIDATION RESULTS ===');
    console.log(`Environment: ${session.environment}`);
    console.log(`Timestamp: ${session.timestamp}`);
    console.log(`Total Tests: ${session.summary.totalTests}`);
    console.log(`Passed: ${session.summary.passedTests}`);
    console.log(`Failed: ${session.summary.failedTests}`);
    console.log(`Average Response Time: ${session.summary.averageResponseTime}ms`);
    console.log(`Overall Success: ${session.summary.success ? 'YES' : 'NO'}`);
    console.log('');

    // Print individual test results
    console.log('=== TEST DETAILS ===');
    session.results.forEach((result, index) => {
      console.log(`${index + 1}. ${result.testName}`);
      console.log(`   Status: ${result.status}`);
      console.log(`   Success: ${result.success}`);
      console.log(`   Response Time: ${result.responseTime}ms`);
      if (result.error) {
        console.log(`   Error: ${result.error}`);
      }
      console.log('');
    });

    // Exit with appropriate code
    process.exit(session.summary.success ? 0 : 1);

  } catch (error: any) {
    console.error('Validation test failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
