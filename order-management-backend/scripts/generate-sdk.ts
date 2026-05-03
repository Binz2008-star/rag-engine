// === SDK GENERATION SCRIPT ===
// Generates TypeScript types and SDK from OpenAPI spec

import { execSync } from "child_process";
import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";

// === CONFIGURATION ===

const OPENAPI_FILE = join(__dirname, "../generated-openapi.json");
const OUTPUT_DIR = join(__dirname, "../src/generated");
const TYPES_FILE = join(OUTPUT_DIR, "runtime-api.ts");
const SDK_FILE = join(OUTPUT_DIR, "runtime-sdk.ts");

// === TYPE GENERATION ===

function generateTypes() {
  console.log("Generating TypeScript types from OpenAPI spec...");

  try {
    // First ensure OpenAPI spec is generated from source-of-truth
    console.log("Ensuring OpenAPI spec is up-to-date...");
    execSync("npm run generate-openapi", { stdio: "inherit" });

    // Generate types using openapi-typescript
    execSync(`npx openapi-typescript ${OPENAPI_FILE} -o ${TYPES_FILE}`, {
      stdio: "inherit",
    });

    console.log(`Types generated: ${TYPES_FILE}`);
  } catch (error) {
    console.error("Failed to generate types:", error);
    process.exit(1);
  }
}

// === SDK GENERATION ===

function generateSDK() {
  console.log("Generating typed SDK...");

  const sdkCode = `
// === AUTO-GENERATED RUNTIME SDK ===
// Generated from OpenAPI spec - DO NOT EDIT MANUALLY

import type { paths } from "./runtime-api";
import { safeFetch } from "../shared/runtime-client/safe-fetch";
import { z } from "zod";

export interface RuntimeClientOptions {
  baseUrl: string;
  token?: string;
  timeoutMs?: number;
  requestId?: string;
}

export class RuntimeSDK {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly timeoutMs: number;

  constructor(options: RuntimeClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\\/$/, "");
    this.token = options.token;
    this.timeoutMs = options.timeoutMs || 10000;
  }

  private buildPath(
    templatePath: string,
    pathParams?: Record<string, string | number>
  ): string {
    if (!pathParams) {
      return templatePath;
    }

    return Object.entries(pathParams).reduce((resolvedPath, [key, value]) => {
      return resolvedPath.replace(\`{\${key}}\`, encodeURIComponent(String(value)));
    }, templatePath);
  }

  private async request<T, TPath extends keyof paths, TMethod extends keyof paths[TPath] & string>(
    path: TPath,
    method: TMethod,
    options?: RequestInit & {
      params?: Record<string, string | number | boolean | null | undefined>;
      pathParams?: Record<string, string | number>;
    }
  ): Promise<T> {
    const resolvedPath = this.buildPath(path, options?.pathParams);
    const url = new URL(\`\${this.baseUrl}\${resolvedPath}\`, this.baseUrl);

    // Add query parameters
    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(this.token ? { Authorization: \`Bearer \${this.token}\` } : {}),
      ...(options?.headers as Record<string, string> || {}),
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      // Create a simple schema for the response
      const responseSchema = z.any();

      const response = await safeFetch(
        url.toString(),
        responseSchema,
        {
          method: method.toUpperCase(),
          headers,
          body: options?.body,
          signal: controller.signal,
          ...options,
        }
      );

      clearTimeout(timeoutId);

      return response as Promise<T>;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  // === ORDERS API ===

  /**
   * List orders with pagination and filtering
   */
  async getOrders(params?: paths["/api/v1/orders"]["get"]["parameters"]["query"]): Promise<
    paths["/api/v1/orders"]["get"]["responses"]["200"]["content"]["application/json"]
  > {
    return this.request("/api/v1/orders", "get", { params });
  }

  /**
   * Create a new order
   */
  async createOrder(body: paths["/api/v1/orders"]["post"]["requestBody"]["content"]["application/json"]): Promise<
    paths["/api/v1/orders"]["post"]["responses"]["201"]["content"]["application/json"]
  > {
    return this.request("/api/v1/orders", "post", { body: JSON.stringify(body) });
  }

  /**
   * Get a specific order by ID
   */
  async getOrder(id: string): Promise<
    paths["/api/v1/orders/{id}"]["get"]["responses"]["200"]["content"]["application/json"]
  > {
    return this.request("/api/v1/orders/{id}", "get", {
      pathParams: { id },
    });
  }

  /**
   * Update an existing order
   */
  async updateOrder(
    id: string,
    body: paths["/api/v1/orders/{id}"]["put"]["requestBody"]["content"]["application/json"]
  ): Promise<
    paths["/api/v1/orders/{id}"]["put"]["responses"]["200"]["content"]["application/json"]
  > {
    return this.request("/api/v1/orders/{id}", "put", {
      pathParams: { id },
      body: JSON.stringify(body),
    });
  }

  /**
   * Update order status
   */
  async updateOrderStatus(
    id: string,
    body: paths["/api/v1/orders/{id}/status"]["put"]["requestBody"]["content"]["application/json"]
  ): Promise<
    paths["/api/v1/orders/{id}/status"]["put"]["responses"]["200"]["content"]["application/json"]
  > {
    return this.request("/api/v1/orders/{id}/status", "put", {
      pathParams: { id },
      body: JSON.stringify(body),
    });
  }

  // === UTILITY METHODS ===

  /**
   * Check API health
   */
  async healthCheck(): Promise<{ status: string }> {
    const healthSchema = z.object({ status: z.string() });

    const response = await safeFetch(
      \`\${this.baseUrl}/api/health\`,
      healthSchema,
      {
        method: 'GET',
        headers: this.token ? { Authorization: \`Bearer \${this.token}\` } : {},
      }
    );

    return response;
  }

  /**
   * Create authenticated client
   */
  static withToken(baseUrl: string, token: string, options?: Omit<RuntimeClientOptions, "baseUrl" | "token">): RuntimeSDK {
    return new RuntimeSDK({ baseUrl, token, ...options });
  }

  /**
   * Create anonymous client
   */
  static anonymous(baseUrl: string, options?: Omit<RuntimeClientOptions, "token">): RuntimeSDK {
    return new RuntimeSDK({ baseUrl, ...options });
  }
}

// === TYPE EXPORTS ===

export type {
  paths,
  components,
} from "./runtime-api";

// === CONVENIENCE TYPES ===

export type CreateOrderRequest = paths["/api/v1/orders"]["post"]["requestBody"]["content"]["application/json"];
export type OrderResponse = NonNullable<
  NonNullable<
    paths["/api/v1/orders/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["data"]
  >["order"]
>;
export type OrderListResponse = paths["/api/v1/orders"]["get"]["responses"]["200"]["content"]["application/json"];
export type ErrorResponse = {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
    timestamp?: string;
  };
};
`;

  try {
    mkdirSync(OUTPUT_DIR, { recursive: true });
    writeFileSync(SDK_FILE, sdkCode.trim());
    console.log(`SDK generated: ${SDK_FILE}`);
  } catch (error) {
    console.error("Failed to generate SDK:", error);
    process.exit(1);
  }
}

// === MAIN EXECUTION ===

async function main() {
  console.log("Starting SDK generation...");

  // Ensure output directory exists
  mkdirSync(OUTPUT_DIR, { recursive: true });

  // Generate types first, then SDK
  generateTypes();
  generateSDK();

  console.log("SDK generation completed successfully!");
  console.log(`Types: ${TYPES_FILE}`);
  console.log(`SDK: ${SDK_FILE}`);

  // Show usage example
  console.log("\n=== USAGE EXAMPLE ===");
  console.log(`
import { RuntimeSDK } from "@/generated/runtime-sdk";

const sdk = RuntimeSDK.withToken("http://localhost:3000", "your-token");

// Create order
const order = await sdk.createOrder({
  sellerId: "seller_123",
  customerId: "customer_456",
  items: [{ productId: "product_789", quantity: 2 }],
  paymentType: "CASH_ON_DELIVERY",
});

// List orders
const orders = await sdk.getOrders({ page: 1, limit: 10, status: "PENDING" });
`);
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error("SDK generation failed:", error);
    process.exit(1);
  });
}

export { main as generateSDK };
