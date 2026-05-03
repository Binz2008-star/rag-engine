// === END-TO-END CONTRACT FLOW TEST ===
// Tests sellora -> runtime -> response -> validation flow

import { randomUUID } from "crypto";
import { GatewayClient } from "../src/shared/runtime-client/gateway-client";
import { CreateOrderSchema, OrderResponseSchema, ErrorSchema } from "../src/shared/schemas/orders";

// === E2E TEST CONFIGURATION ===

interface E2ETestConfig {
  runtimeApiUrl: string;
  sellerToken?: string;
  timeoutMs: number;
  retries: number;
}

interface E2ETestResult {
  success: boolean;
  requestId?: string;
  latencyMs: number;
  contractValidated: boolean;
  errors: string[];
  steps: {
    gatewayRequest: boolean;
    runtimeResponse: boolean;
    contractValidation: boolean;
    requestTracing: boolean;
  };
}

// === E2E CONTRACT FLOW TESTER ===

class E2EContractFlowTester {
  private gatewayClient: GatewayClient;
  private config: E2ETestConfig;

  constructor(config: E2ETestConfig) {
    this.config = config;
    this.gatewayClient = GatewayClient.withToken(
      config.runtimeApiUrl,
      config.sellerToken || "test-token",
      {
        timeoutMs: config.timeoutMs,
        retryAttempts: config.retries,
      }
    );
  }

  async runFullFlowTest(): Promise<E2ETestResult> {
    console.log("Running end-to-end contract flow test...");
    
    const startTime = Date.now();
    const result: E2ETestResult = {
      success: false,
      latencyMs: 0,
      contractValidated: false,
      errors: [],
      steps: {
        gatewayRequest: false,
        runtimeResponse: false,
        contractValidation: false,
        requestTracing: false,
      },
    };

    try {
      // Step 1: Create order via gateway client
      console.log("Step 1: Creating order via gateway client...");
      const orderData = CreateOrderSchema.parse({
        sellerId: "test-seller-e2e",
        customerId: "test-customer-e2e",
        items: [
          {
            productId: "test-product-e2e",
            quantity: 1,
          },
        ],
        paymentType: "CASH_ON_DELIVERY",
        notes: "E2E contract flow test",
      });

      const createResponse = await this.gatewayClient.post("/api/v1/orders", orderData);
      result.steps.gatewayRequest = true;
      
      // Check for request ID in response
      if (createResponse.headers?.["x-request-id"]) {
        result.requestId = createResponse.headers["x-request-id"];
        result.steps.requestTracing = true;
        console.log(`Request ID: ${result.requestId}`);
      } else {
        result.errors.push("No request ID found in response headers");
      }

      // Step 2: Validate runtime response structure
      console.log("Step 2: Validating runtime response structure...");
      
      if (!createResponse.success) {
        result.errors.push("Create order response not successful");
        throw new Error("Create order failed");
      }

      if (!createResponse.data?.order) {
        result.errors.push("No order data in response");
        throw new Error("Missing order data");
      }

      result.steps.runtimeResponse = true;

      // Step 3: Validate contract compliance
      console.log("Step 3: Validating contract compliance...");
      
      try {
        const validatedOrder = OrderResponseSchema.parse(createResponse.data.order);
        result.steps.contractValidation = true;
        result.contractValidated = true;
        console.log("Order response contract validated successfully");
        
        // Verify required fields
        if (!validatedOrder.id || !validatedOrder.sellerId || !validatedOrder.status) {
          result.errors.push("Missing required fields in order response");
          result.contractValidated = false;
        }
        
        // Verify field types
        if (typeof validatedOrder.totalMinor !== "number" || validatedOrder.totalMinor < 0) {
          result.errors.push("Invalid totalMinor field type or value");
          result.contractValidated = false;
        }
        
      } catch (validationError) {
        result.errors.push(`Contract validation failed: ${validationError}`);
        result.contractValidated = false;
      }

      // Step 4: Test order retrieval
      console.log("Step 4: Testing order retrieval...");
      
      if (validatedOrder?.id) {
        const getResponse = await this.gatewayClient.get(`/api/v1/orders/${validatedOrder.id}`);
        
        if (!getResponse.success || !getResponse.data?.order) {
          result.errors.push("Order retrieval failed");
        } else {
          try {
            OrderResponseSchema.parse(getResponse.data.order);
            console.log("Order retrieval contract validated successfully");
          } catch (retrievalValidationError) {
            result.errors.push(`Order retrieval validation failed: ${retrievalValidationError}`);
          }
        }
      }

      // Step 5: Test error contract
      console.log("Step 5: Testing error contract...");
      
      try {
        const invalidOrderData = {
          sellerId: "", // Invalid
          customerId: "test-customer",
          items: [], // Invalid
          paymentType: "INVALID_TYPE", // Invalid
        };

        await this.gatewayClient.post("/api/v1/orders", invalidOrderData);
        result.errors.push("Expected error for invalid data but got success");
      } catch (expectedError) {
        // This should fail with proper error contract
        if (expectedError instanceof Error && "response" in expectedError) {
          try {
            const errorResponse = JSON.parse((expectedError as any).response);
            ErrorSchema.parse(errorResponse);
            console.log("Error contract validated successfully");
          } catch (errorValidationError) {
            result.errors.push(`Error contract validation failed: ${errorValidationError}`);
          }
        } else {
          result.errors.push("Error response doesn't match expected format");
        }
      }

      result.latencyMs = Date.now() - startTime;
      result.success = result.errors.length === 0 && Object.values(result.steps).every(step => step);

    } catch (error) {
      result.errors.push(`E2E test failed: ${error}`);
      result.latencyMs = Date.now() - startTime;
    }

    return result;
  }

  async runConcurrentFlowTest(concurrency: number = 5): Promise<{
    success: boolean;
    results: E2ETestResult[];
    averageLatency: number;
    maxLatency: number;
    minLatency: number;
    errorRate: number;
  }> {
    console.log(`Running concurrent flow test with ${concurrency} requests...`);
    
    const promises = Array(concurrency).fill(null).map(() => this.runFullFlowTest());
    const results = await Promise.all(promises);
    
    const latencies = results.map(r => r.latencyMs);
    const errorCount = results.filter(r => !r.success).length;
    
    return {
      success: errorCount === 0,
      results,
      averageLatency: latencies.reduce((a, b) => a + b, 0) / latencies.length,
      maxLatency: Math.max(...latencies),
      minLatency: Math.min(...latencies),
      errorRate: errorCount / concurrency,
    };
  }
}

// === E2E TEST RUNNER ===

class E2ETestRunner {
  static async runE2ETests(config: E2ETestConfig): Promise<{
    singleFlow: E2ETestResult;
    concurrentFlow: ReturnType<typeof E2ETestRunner["runConcurrentFlowTest"]> extends Promise<infer T> ? T : never;
    overallSuccess: boolean;
  }> {
    console.log("=== END-TO-END CONTRACT FLOW TESTING ===");
    console.log(`Runtime API: ${config.runtimeApiUrl}`);
    console.log(`Timeout: ${config.timeoutMs}ms`);
    console.log(`Retries: ${config.retries}`);
    console.log("");

    const tester = new E2EContractFlowTester(config);

    try {
      // Run single flow test
      console.log("Running single flow test...");
      const singleFlow = await tester.runFullFlowTest();
      
      // Run concurrent flow test
      console.log("\nRunning concurrent flow test...");
      const concurrentFlow = await tester.runConcurrentFlowTest(3);
      
      const overallSuccess = singleFlow.success && concurrentFlow.success;

      // Generate report
      this.generateReport(singleFlow, concurrentFlow);

      return {
        singleFlow,
        concurrentFlow,
        overallSuccess,
      };

    } catch (error) {
      console.error("E2E testing failed:", error);
      throw error;
    }
  }

  private static generateReport(
    singleFlow: E2ETestResult,
    concurrentFlow: {
      success: boolean;
      results: E2ETestResult[];
      averageLatency: number;
      maxLatency: number;
      minLatency: number;
      errorRate: number;
    }
  ): void {
    console.log("\n=== E2E TEST RESULTS ===");
    
    console.log("\nSingle Flow Test:");
    console.log(`  Success: ${singleFlow.success}`);
    console.log(`  Latency: ${singleFlow.latencyMs}ms`);
    console.log(`  Contract Validated: ${singleFlow.contractValidated}`);
    console.log(`  Request ID: ${singleFlow.requestId || "N/A"}`);
    console.log(`  Steps: ${Object.values(singleFlow.steps).filter(Boolean).length}/${Object.keys(singleFlow.steps).length}`);
    
    if (singleFlow.errors.length > 0) {
      console.log("  Errors:");
      singleFlow.errors.forEach(error => console.log(`    - ${error}`));
    }

    console.log("\nConcurrent Flow Test:");
    console.log(`  Success: ${concurrentFlow.success}`);
    console.log(`  Error Rate: ${(concurrentFlow.errorRate * 100).toFixed(1)}%`);
    console.log(`  Average Latency: ${concurrentFlow.averageLatency.toFixed(1)}ms`);
    console.log(`  Min Latency: ${concurrentFlow.minLatency}ms`);
    console.log(`  Max Latency: ${concurrentFlow.maxLatency}ms`);

    console.log("\nOverall Result:");
    const overallSuccess = singleFlow.success && concurrentFlow.success;
    console.log(`  Status: ${overallSuccess ? "PASS" : "FAIL"}`);
    
    if (!overallSuccess) {
      console.log("\nCritical Issues:");
      if (!singleFlow.success) {
        console.log("  - Single flow test failed");
      }
      if (!concurrentFlow.success) {
        console.log("  - Concurrent flow test failed");
      }
      if (!singleFlow.contractValidated) {
        console.log("  - Contract validation failed");
      }
      if (!singleFlow.requestId) {
        console.log("  - Request tracing failed");
      }
    }
  }
}

// === MAIN EXECUTION ===

async function main() {
  const config: E2ETestConfig = {
    runtimeApiUrl: process.argv[2] || "http://localhost:3000",
    sellerToken: process.argv[3] || "test-token",
    timeoutMs: parseInt(process.argv[4]) || 10000,
    retries: parseInt(process.argv[5]) || 3,
  };

  try {
    const result = await E2ETestRunner.runE2ETests(config);
    
    if (!result.overallSuccess) {
      console.error("\nE2E contract flow testing failed");
      process.exit(1);
    }
    
    console.log("\nE2E contract flow testing passed");
  } catch (error) {
    console.error("E2E contract flow testing failed:", error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

export { E2ETestRunner, E2EContractFlowTester, E2ETestResult };
