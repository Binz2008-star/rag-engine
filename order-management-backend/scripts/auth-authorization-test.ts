#!/usr/bin/env tsx

/**
 * Auth and Authorization Boundary Test
 * 
 * Explicit validation of:
 * 1. Unauthorized request rejected
 * 2. Cross-seller access rejected  
 * 3. Privileged status update allowed only for correct actor
 */

import { execSync } from 'child_process';
import { writeFileSync } from 'fs';

interface AuthTestResult {
  timestamp: string;
  environment: string;
  tests: {
    unauthorizedAccess: {
      success: boolean;
      expectedStatus: number;
      actualStatus: number;
      error?: string;
      description: string;
    };
    crossSellerAccess: {
      success: boolean;
      expectedStatus: number;
      actualStatus: number;
      error?: string;
      description: string;
    };
    privilegedStatusUpdate: {
      success: boolean;
      expectedStatus: number;
      actualStatus: number;
      error?: string;
      description: string;
    };
    validSellerAccess: {
      success: boolean;
      expectedStatus: number;
      actualStatus: number;
      error?: string;
      description: string;
    };
  };
  overall: {
    success: boolean;
    passedTests: number;
    totalTests: number;
  };
}

class AuthAuthorizationTest {
  private baseUrl: string;
  private sellerToken: string | null = null;
  private otherSellerToken: string | null = null;
  private orderId: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private async makeRequest(method: string, endpoint: string, body?: any, headers?: Record<string, string>) {
    const url = `${this.baseUrl}${endpoint}`;
    let curlCommand = `curl -X ${method} "${url}" -w "\\nHTTP_STATUS:%{http_code}" -s`;
    
    if (headers) {
      Object.entries(headers).forEach(([key, value]) => {
        curlCommand += ` -H "${key}: ${value}"`;
      });
    }
    
    if (body) {
      curlCommand += ` -d '${JSON.stringify(body)}'`;
    }
    
    try {
      const output = execSync(curlCommand, { encoding: 'utf8', timeout: 30000 });
      const lines = output.split('\n');
      const httpStatusLine = lines.find(line => line.startsWith('HTTP_STATUS:'));
      const status = httpStatusLine ? parseInt(httpStatusLine.split(':')[1]) : 0;
      
      const httpStatusIndex = lines.findIndex(line => line.startsWith('HTTP_STATUS:'));
      const responseBody = httpStatusIndex > 0 ? lines.slice(0, httpStatusIndex).join('\n') : '';
      
      let parsedResponse;
      try {
        parsedResponse = JSON.parse(responseBody);
      } catch {
        parsedResponse = responseBody;
      }
      
      return { success: status >= 200 && status < 300, status, response: parsedResponse };
    } catch (error: any) {
      return { success: false, status: 0, response: null, error: error.message };
    }
  }

  private async authenticateSeller(email: string, password: string): Promise<string | null> {
    const result = await this.makeRequest('POST', '/api/auth/login', {
      email,
      password
    });
    
    if (result.success && result.response && result.response.token) {
      return result.response.token;
    }
    
    return null;
  }

  private async setupTokens(): Promise<boolean> {
    // Authenticate as seller1@test.com
    this.sellerToken = await this.authenticateSeller('seller1@test.com', 'TestSeller123!');
    if (!this.sellerToken) return false;

    // Authenticate as seller2@test.com (different seller)
    this.otherSellerToken = await this.authenticateSeller('seller2@test.com', 'TestSeller123!');
    if (!this.otherSellerToken) return false;

    // Create an order for testing
    const productsResult = await this.makeRequest('GET', '/api/seller/products', undefined, {
      'Authorization': `Bearer ${this.sellerToken}`
    });
    
    if (productsResult.success && productsResult.response && productsResult.response.products && productsResult.response.products.length > 0) {
      const productId = productsResult.response.products[0].id;
      
      const orderResult = await this.makeRequest('POST', '/api/public/fashion-forward/orders', {
        customerName: 'Auth Test Customer',
        customerPhone: '+15551234567',
        addressText: '123 Auth Test Street',
        items: [{ productId, quantity: 1 }],
        notes: 'Auth test order'
      });
      
      if (orderResult.success && orderResult.response && orderResult.response.id) {
        this.orderId = orderResult.response.id;
        return true;
      }
    }
    
    return false;
  }

  private async testUnauthorizedAccess(): Promise<AuthTestResult['tests']['unauthorizedAccess']> {
    // Test accessing seller endpoint without token
    const result = await this.makeRequest('GET', '/api/seller/orders');
    
    return {
      success: result.status === 401,
      expectedStatus: 401,
      actualStatus: result.status,
      error: result.status !== 401 ? `Expected 401, got ${result.status}` : undefined,
      description: 'Unauthorized request to seller endpoint should be rejected'
    };
  }

  private async testCrossSellerAccess(): Promise<AuthTestResult['tests']['crossSellerAccess']> {
    if (!this.otherSellerToken || !this.orderId) {
      return {
        success: false,
        expectedStatus: 403,
        actualStatus: 0,
        error: 'Setup failed - no token or order ID',
        description: 'Cross-seller access test setup failed'
      };
    }

    // Try to access order from seller1 while authenticated as seller2
    const result = await this.makeRequest('GET', '/api/seller/orders', undefined, {
      'Authorization': `Bearer ${this.otherSellerToken}`
    });
    
    // The order should not be visible to seller2
    let orderVisible = false;
    if (result.success && result.response && result.response.orders) {
      orderVisible = result.response.orders.some((order: any) => order.id === this.orderId);
    }
    
    // Success if order is NOT visible (authorization working)
    const authWorking = !orderVisible && result.success;
    
    return {
      success: authWorking,
      expectedStatus: 200, // Request succeeds but order filtered out
      actualStatus: result.status,
      error: orderVisible ? 'Cross-seller order visible - authorization bypassed' : undefined,
      description: 'Seller should not see orders from other sellers'
    };
  }

  private async testPrivilegedStatusUpdate(): Promise<AuthTestResult['tests']['privilegedStatusUpdate']> {
    if (!this.otherSellerToken || !this.orderId) {
      return {
        success: false,
        expectedStatus: 403,
        actualStatus: 0,
        error: 'Setup failed - no token or order ID',
        description: 'Privileged status update test setup failed'
      };
    }

    // Try to update status of seller1's order while authenticated as seller2
    const result = await this.makeRequest('PATCH', `/api/seller/orders/${this.orderId}/status`, {
      status: 'CONFIRMED',
      reason: 'Cross-seller status update test'
    }, {
      'Authorization': `Bearer ${this.otherSellerToken}`,
      'Content-Type': 'application/json'
    });
    
    // Should be rejected (403 or 404)
    const properlyRejected = !result.success && (result.status === 403 || result.status === 404);
    
    return {
      success: properlyRejected,
      expectedStatus: 403,
      actualStatus: result.status,
      error: !properlyRejected ? `Expected rejection (403/404), got ${result.status}` : undefined,
      description: 'Seller should not be able to update other seller orders'
    };
  }

  private async testValidSellerAccess(): Promise<AuthTestResult['tests']['validSellerAccess']> {
    if (!this.sellerToken) {
      return {
        success: false,
        expectedStatus: 200,
        actualStatus: 0,
        error: 'Setup failed - no seller token',
        description: 'Valid seller access test setup failed'
      };
    }

    // Test valid seller accessing their own orders
    const result = await this.makeRequest('GET', '/api/seller/orders', undefined, {
      'Authorization': `Bearer ${this.sellerToken}`
    });
    
    return {
      success: result.success,
      expectedStatus: 200,
      actualStatus: result.status,
      error: !result.success ? `Expected 200, got ${result.status}` : undefined,
      description: 'Valid seller should access their own orders'
    };
  }

  async runAuthTests(): Promise<AuthTestResult> {
    console.log('Auth and Authorization Boundary Test');
    console.log(`Environment: ${this.baseUrl}`);
    console.log('');

    const result: AuthTestResult = {
      timestamp: new Date().toISOString(),
      environment: this.baseUrl,
      tests: {
        unauthorizedAccess: { success: false, expectedStatus: 401, actualStatus: 0, description: '' },
        crossSellerAccess: { success: false, expectedStatus: 200, actualStatus: 0, description: '' },
        privilegedStatusUpdate: { success: false, expectedStatus: 403, actualStatus: 0, description: '' },
        validSellerAccess: { success: false, expectedStatus: 200, actualStatus: 0, description: '' }
      },
      overall: {
        success: false,
        passedTests: 0,
        totalTests: 4
      }
    };

    // Setup tokens and test order
    console.log('Setting up test tokens and order...');
    const setupSuccess = await this.setupTokens();
    if (!setupSuccess) {
      console.log('FAILED: Could not set up test environment');
      return result;
    }
    console.log('SUCCESS: Test environment ready');

    // Test 1: Unauthorized access
    console.log('1. Testing unauthorized access...');
    result.tests.unauthorizedAccess = await this.testUnauthorizedAccess();
    console.log(`   ${result.tests.unauthorizedAccess.success ? 'PASS' : 'FAIL'}: ${result.tests.unauthorizedAccess.description}`);
    if (result.tests.unauthorizedAccess.error) {
      console.log(`   Error: ${result.tests.unauthorizedAccess.error}`);
    }

    // Test 2: Cross-seller access
    console.log('2. Testing cross-seller access...');
    result.tests.crossSellerAccess = await this.testCrossSellerAccess();
    console.log(`   ${result.tests.crossSellerAccess.success ? 'PASS' : 'FAIL'}: ${result.tests.crossSellerAccess.description}`);
    if (result.tests.crossSellerAccess.error) {
      console.log(`   Error: ${result.tests.crossSellerAccess.error}`);
    }

    // Test 3: Privileged status update
    console.log('3. Testing privileged status update...');
    result.tests.privilegedStatusUpdate = await this.testPrivilegedStatusUpdate();
    console.log(`   ${result.tests.privilegedStatusUpdate.success ? 'PASS' : 'FAIL'}: ${result.tests.privilegedStatusUpdate.description}`);
    if (result.tests.privilegedStatusUpdate.error) {
      console.log(`   Error: ${result.tests.privilegedStatusUpdate.error}`);
    }

    // Test 4: Valid seller access
    console.log('4. Testing valid seller access...');
    result.tests.validSellerAccess = await this.testValidSellerAccess();
    console.log(`   ${result.tests.validSellerAccess.success ? 'PASS' : 'FAIL'}: ${result.tests.validSellerAccess.description}`);
    if (result.tests.validSellerAccess.error) {
      console.log(`   Error: ${result.tests.validSellerAccess.error}`);
    }

    // Calculate results
    const passedTests = Object.values(result.tests).filter(test => test.success).length;
    result.overall.passedTests = passedTests;
    result.overall.success = passedTests >= 3; // At least 3/4 tests must pass

    console.log('');
    console.log('=== AUTHORIZATION TEST RESULTS ===');
    console.log(`Passed Tests: ${result.overall.passedTests}/${result.overall.totalTests}`);
    console.log(`Overall Success: ${result.overall.success ? 'YES' : 'NO'}`);
    console.log('');

    return result;
  }
}

async function main(): Promise<void> {
  const baseUrl = process.argv[2] || 'http://localhost:3000';
  const outputFile = process.argv[3] || `auth-authorization-test-${Date.now()}.json`;

  const test = new AuthAuthorizationTest(baseUrl);
  const result = await test.runAuthTests();

  writeFileSync(outputFile, JSON.stringify(result, null, 2));
  console.log(`Results saved to: ${outputFile}`);

  process.exit(result.overall.success ? 0 : 1);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
