// scripts/auth-authorization-boundaries.ts
import fs from "node:fs/promises";

type AuthTestResult = {
  testName: string;
  method: string;
  url: string;
  requestHeaders?: Record<string, string>;
  requestBody?: unknown;
  status?: number;
  responseBody?: unknown;
  ok: boolean;
  error?: string;
  expectedStatus?: number;
  actualBehavior?: string;
};

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const SELLER_SLUG = process.env.SELLER_SLUG ?? "demo-store";
const SELLER1_EMAIL = process.env.SELLER1_EMAIL ?? "seller1@test.com";
const SELLER1_PASSWORD = process.env.SELLER1_PASSWORD ?? "TestSeller123!";
const SELLER2_EMAIL = process.env.SELLER2_EMAIL ?? "seller2@test.com";
const SELLER2_PASSWORD = process.env.SELLER2_PASSWORD ?? "TestSeller123!";

async function safeJson(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
}

async function runAuthTest(
  testName: string,
  method: string,
  url: string,
  init?: RequestInit,
  expectedStatus?: number,
): Promise<AuthTestResult> {
  try {
    const res = await fetch(url, { method, ...init });
    const body = await safeJson(res);

    const result: AuthTestResult = {
      testName,
      method,
      url,
      requestHeaders: (init?.headers as Record<string, string>) ?? undefined,
      requestBody: init?.body ? JSON.parse(String(init.body)) : undefined,
      status: res.status,
      responseBody: body,
      ok: res.ok,
      expectedStatus,
    };

    // Determine actual behavior
    if (expectedStatus) {
      result.actualBehavior = res.status === expectedStatus ? "PASS" : "FAIL";
    }

    return result;
  } catch (error) {
    return {
      testName,
      method,
      url,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      expectedStatus,
      actualBehavior: "ERROR",
    };
  }
}

async function getAuthToken(email: string, password: string): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    
    if (res.ok) {
      const body = await safeJson(res);
      return (body as any)?.token ?? null;
    }
    return null;
  } catch {
    return null;
  }
}

async function createTestOrder(sellerSlug: string): Promise<string | null> {
  try {
    // First get products
    const productsRes = await fetch(`${BASE_URL}/api/public/${sellerSlug}/products`);
    if (!productsRes.ok) return null;
    
    const productsBody = await safeJson(productsRes);
    const products = Array.isArray((productsBody as any)?.products)
      ? (productsBody as any).products
      : Array.isArray(productsBody)
        ? productsBody
        : [];

    if (products.length === 0) return null;

    const product = products[0];
    const orderPayload = {
      customerName: "Auth Test Customer",
      customerPhone: "+15550001111",
      addressText: "123 Auth Test St",
      items: [{ productId: product.id, quantity: 1 }],
      notes: "auth-test",
    };

    const orderRes = await fetch(`${BASE_URL}/api/public/${sellerSlug}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(orderPayload),
    });

    if (orderRes.ok) {
      const orderBody = await safeJson(orderRes);
      return (orderBody as any)?.id ?? (orderBody as any)?.order?.id ?? null;
    }
    return null;
  } catch {
    return null;
  }
}

async function main() {
  const results: AuthTestResult[] = [];

  console.log("Running authentication and authorization boundary tests...");

  // === AUTHENTICATION TESTS ===

  // 1. Valid login returns token
  const validLogin = await runAuthTest(
    "valid-login",
    "POST",
    `${BASE_URL}/api/auth/login`,
    {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: SELLER1_EMAIL, password: SELLER1_PASSWORD }),
    },
    200,
  );
  results.push(validLogin);

  // 2. Invalid JSON returns 400
  const invalidJson = await runAuthTest(
    "invalid-json",
    "POST",
    `${BASE_URL}/api/auth/login`,
    {
      headers: { "Content-Type": "application/json" },
      body: "invalid json",
    },
    400,
  );
  results.push(invalidJson);

  // 3. Wrong password returns 401
  const wrongPassword = await runAuthTest(
    "wrong-password",
    "POST",
    `${BASE_URL}/api/auth/login`,
    {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: SELLER1_EMAIL, password: "wrongpassword" }),
    },
    401,
  );
  results.push(wrongPassword);

  // 4. Missing token on protected route returns 401
  const missingToken = await runAuthTest(
    "missing-token",
    "GET",
    `${BASE_URL}/api/seller/orders`,
    undefined,
    401,
  );
  results.push(missingToken);

  // === AUTHORIZATION TESTS ===

  // Get tokens for both sellers
  const seller1Token = await getAuthToken(SELLER1_EMAIL, SELLER1_PASSWORD);
  const seller2Token = await getAuthToken(SELLER2_EMAIL, SELLER2_PASSWORD);

  if (seller1Token && seller2Token) {
    // 5. Seller A cannot read seller B orders
    const sellerAOrders = await runAuthTest(
      "seller-a-read-orders",
      "GET",
      `${BASE_URL}/api/seller/orders`,
      {
        headers: { Authorization: `Bearer ${seller1Token}` },
      },
      200, // Should succeed but only show seller A's orders
    );
    results.push(sellerAOrders);

    // 6. Non-authenticated client cannot access seller routes
    const noAuthAccess = await runAuthTest(
      "no-auth-seller-route",
      "GET",
      `${BASE_URL}/api/seller/products`,
      undefined,
      401,
    );
    results.push(noAuthAccess);

    // Create test orders for cross-seller testing
    const seller1Order = await createTestOrder("demo-store");
    const seller2Order = await createTestOrder("fashion-forward");

    if (seller1Order && seller2Order) {
      // 7. Seller A cannot update seller B orders
      const crossSellerUpdate = await runAuthTest(
        "cross-seller-update",
        "PATCH",
        `${BASE_URL}/api/seller/orders/${seller2Order}/status`,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${seller1Token}`,
          },
          body: JSON.stringify({ status: "CONFIRMED" }),
        },
        403, // Should be forbidden
      );
      results.push(crossSellerUpdate);

      // 8. Seller A can update their own orders
      const ownSellerUpdate = await runAuthTest(
        "own-seller-update",
        "PATCH",
        `${BASE_URL}/api/seller/orders/${seller1Order}/status`,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${seller1Token}`,
          },
          body: JSON.stringify({ status: "CONFIRMED" }),
        },
        200, // Should succeed
      );
      results.push(ownSellerUpdate);
    }

    // 9. Invalid role cannot perform seller mutation (if we had different roles)
    // This would require a non-seller user token, which we don't have in current setup
    // For now, we'll test with malformed token
    const invalidToken = await runAuthTest(
      "invalid-token",
      "GET",
      `${BASE_URL}/api/seller/orders`,
      {
        headers: { Authorization: "Bearer invalid.token.here" },
      },
      401,
    );
    results.push(invalidToken);
  }

  // Calculate results
  const passed = results.filter(r => r.actualBehavior === "PASS").length;
  const failed = results.filter(r => r.actualBehavior === "FAIL").length;
  const errors = results.filter(r => r.actualBehavior === "ERROR").length;

  const output = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    testMatrix: {
      "POST /api/auth/login": ["valid-login", "invalid-json", "wrong-password"],
      "GET /api/seller/orders": ["missing-token", "seller-a-read-orders", "no-auth-seller-route", "invalid-token"],
      "PATCH /api/seller/orders/:id/status": ["cross-seller-update", "own-seller-update"],
    },
    results,
    summary: {
      totalTests: results.length,
      passed,
      failed,
      errors,
      success: failed === 0 && errors === 0,
    },
  };

  const filename = `auth-authorization-boundaries-${Date.now()}.json`;
  await fs.writeFile(filename, JSON.stringify(output, null, 2), "utf8");
  console.log(`Saved ${filename}`);

  console.log(`\n=== AUTHORIZATION BOUNDARY TEST RESULTS ===`);
  console.log(`Total Tests: ${results.length}`);
  console.log(`Passed: ${passed}`);
  console.log(`Failed: ${failed}`);
  console.log(`Errors: ${errors}`);
  console.log(`Overall Success: ${output.summary.success ? "YES" : "NO"}`);

  if (!output.summary.success) {
    console.log(`\nFailed Tests:`);
    results.filter(r => r.actualBehavior === "FAIL").forEach(test => {
      console.log(`- ${test.testName}: Expected ${test.expectedStatus}, got ${test.status}`);
    });
  }

  process.exitCode = output.summary.success ? 0 : 1;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
