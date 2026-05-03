// scripts/release-proof-core-flow.ts
import fs from "node:fs/promises";

type StepResult = {
  name: string;
  method: string;
  url: string;
  requestHeaders?: Record<string, string>;
  requestBody?: unknown;
  status?: number;
  responseBody?: unknown;
  ok: boolean;
  error?: string;
};

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const SELLER_SLUG = process.env.SELLER_SLUG ?? "demo-store";
const LOGIN_EMAIL = process.env.LOGIN_EMAIL ?? "";
const LOGIN_PASSWORD = process.env.LOGIN_PASSWORD ?? "";
const ORDER_ID_FOR_STATUS = process.env.ORDER_ID_FOR_STATUS ?? "";

async function safeJson(res: Response) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
}

async function runStep(
  name: string,
  method: string,
  url: string,
  init?: RequestInit,
): Promise<StepResult> {
  try {
    const res = await fetch(url, { method, ...init });
    const body = await safeJson(res);

    return {
      name,
      method,
      url,
      requestHeaders: (init?.headers as Record<string, string>) ?? undefined,
      requestBody: init?.body ? JSON.parse(String(init.body)) : undefined,
      status: res.status,
      responseBody: body,
      ok: res.ok,
    };
  } catch (error) {
    return {
      name,
      method,
      url,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function main() {
  const results: StepResult[] = [];

  const health = await runStep("health", "GET", `${BASE_URL}/api/health`);
  results.push(health);
  if (!health.ok) throw new Error("Health check failed");

  const publicProducts = await runStep(
    "public-products",
    "GET",
    `${BASE_URL}/api/public/${SELLER_SLUG}/products`,
  );
  results.push(publicProducts);
  if (!publicProducts.ok) throw new Error("Public products failed");

  const products = Array.isArray((publicProducts.responseBody as any)?.products)
    ? (publicProducts.responseBody as any).products
    : Array.isArray(publicProducts.responseBody)
      ? publicProducts.responseBody
      : [];

  if (products.length === 0) {
    throw new Error("No products available for release proof");
  }

  const product = products[0];
  const createOrderPayload = {
    customerName: "Release Proof Customer",
    customerPhone: "+15550001111",
    addressText: "123 Release Proof St",
    items: [{ productId: product.id, quantity: 1 }],
    notes: "release-proof",
  };

  const createOrder = await runStep(
    "create-order",
    "POST",
    `${BASE_URL}/api/public/${SELLER_SLUG}/orders`,
    {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(createOrderPayload),
    },
  );
  results.push(createOrder);

  let createdOrderId =
    (createOrder.responseBody as any)?.order?.id ??
    (createOrder.responseBody as any)?.id;

  const loginPayload = {
    email: LOGIN_EMAIL,
    password: LOGIN_PASSWORD,
  };

  const login = await runStep("login", "POST", `${BASE_URL}/api/auth/login`, {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(loginPayload),
  });
  results.push(login);

  const token =
    (login.responseBody as any)?.token ??
    (login.responseBody as any)?.data?.token;

  if (token) {
    const sellerOrders = await runStep(
      "seller-orders",
      "GET",
      `${BASE_URL}/api/seller/orders`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    results.push(sellerOrders);

    const targetOrderId = createdOrderId || ORDER_ID_FOR_STATUS;
    if (targetOrderId) {
      const updateStatus = await runStep(
        "update-status",
        "PATCH",
        `${BASE_URL}/api/seller/orders/${targetOrderId}/status`,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status: "CONFIRMED" }),
        },
      );
      results.push(updateStatus);
    }
  }

  const output = {
    timestamp: new Date().toISOString(),
    baseUrl: BASE_URL,
    sellerSlug: SELLER_SLUG,
    results,
  };

  const filename = `release-proof-${Date.now()}.json`;
  await fs.writeFile(filename, JSON.stringify(output, null, 2), "utf8");
  console.log(`Saved ${filename}`);

  const failed = results.filter((r) => !r.ok);
  if (failed.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
