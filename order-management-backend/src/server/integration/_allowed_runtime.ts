// === RUNTIME ALLOWED TEST ===
// This file is in runtime core - should PASS ESLint

import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// These should be ALLOWED in runtime core
await prisma.order.findMany();
await prisma.paymentAttempt.findMany();
await prisma.user.findMany();

await prisma.order.create({
  data: {
    sellerId: "test",
    customerId: "test",
    publicOrderNumber: "TEST-001",
    subtotalMinor: 1000,
    totalMinor: 1000,
    currency: "USD",
  },
});

console.log("Runtime allowed - should pass ESLint");
