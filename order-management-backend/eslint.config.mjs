import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  ...nextVitals,
  ...nextTs,

  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "node_modules/**",
  ]),

  // === RUNTIME CORE - ALLOW Prisma (database layer) ===
  // This is the ONLY place where Prisma should be allowed
  {
    files: [
      "src/server/db/**",
      "src/app/api/**",
      "src/modules/**",
      "src/server/**",
      "src/tests/**",
      "prisma/**",
      "scripts/**",
      "**/*.test.ts",
      "**/*.test.tsx",
      "**/*.spec.ts",
    ],
    rules: {
      "no-restricted-imports": "off",
      "no-restricted-syntax": "off",
    },
  },

  // === PLATFORM LAYER (sellora) - STRICT BOUNDARY ENFORCEMENT ===
  // This blocks Prisma usage in platform layer only
  {
    files: [
      "src/**/*.ts",
      "src/**/*.tsx",
    ],
    ignores: [
      "src/server/**",
      "src/app/api/**",
      "src/modules/**",
      "prisma/**",
      "scripts/**",
      "**/*.test.ts",
      "**/*.test.tsx",
      "**/*.spec.ts",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "error",

      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],

      // === BLOCK Prisma in platform layer ===
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@prisma/client",
              message:
                "Direct Prisma access forbidden. Use runtime API.",
            },
          ],
        },
      ],

      // === BLOCK transactional mutations ===
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "MemberExpression[object.name='prisma'][property.name=/order|payment|user/i]",
          message:
            "Transactional DB access forbidden in platform layer",
        },
      ],
    },
  },

  // === TESTS - Allow Prisma for testing ===
  {
    files: ["src/tests/**"],
    rules: {
      "no-restricted-imports": "off",
      "no-restricted-syntax": "off",
    },
  },

  // === GATEWAY ENFORCEMENT - Block all bypassable HTTP patterns ===
  {
    files: [
      "src/**/*.ts",
      "src/**/*.tsx",
    ],
    ignores: [
      "src/shared/runtime-client/gateway-client.ts",
      "src/shared/runtime-client/safe-fetch.ts",
      "src/shared/runtime-client/orders.ts",
      "src/server/lib/rate-limiting*.ts",
      "src/server/lib/observability.ts",
      "scripts/**",
      "**/*.test.ts",
      "**/*.test.tsx",
      "**/*.spec.ts",
    ],
    rules: {
      // Block raw fetch usage - must use gateway
      "no-restricted-globals": [
        "error",
        {
          name: "fetch",
          message: "Direct fetch usage forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
      ],

      // Block forbidden HTTP imports
      "no-restricted-imports": [
        "error",
        {
          name: "node-fetch",
          message: "node-fetch import forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          name: "axios",
          message: "axios import forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          name: "got",
          message: "got import forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          name: "undici",
          message: "undici import forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          name: "superagent",
          message: "superagent import forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
      ],

      // Block all bypassable HTTP syntax patterns
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch']",
          message: "Direct fetch usage forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          selector: "MemberExpression[object.name='globalThis'][property.name='fetch']",
          message: "globalThis.fetch usage forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          selector: "MemberExpression[object.name='window'][property.name='fetch']",
          message: "window.fetch usage forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          selector: "CallExpression[callee.property.name='fetch']",
          message: "fetch method call forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          selector: "VariableDeclarator[id.name=/^(fetch|http|request)$/]",
          message: "Variable name 'fetch/http/request' reserved for gateway enforcement. Use different name.",
        },
        {
          selector: "AssignmentExpression[left.name=/^(fetch|http|request)$/]",
          message: "Assignment to 'fetch/http/request' forbidden. Use different variable name.",
        },
      ],

      // Block HTTP-related global access
      "no-restricted-properties": [
        "error",
        {
          object: "globalThis",
          property: "fetch",
          message: "globalThis.fetch access forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
        {
          object: "window",
          property: "fetch",
          message: "window.fetch access forbidden. Use GatewayClient or safeFetch wrapper from runtime-client.",
        },
      ],
    },
  },
]);
