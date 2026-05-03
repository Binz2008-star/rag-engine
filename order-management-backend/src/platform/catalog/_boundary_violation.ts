// === PLATFORM VIOLATION TEST ===
// This file is in platform layer - should FAIL ESLint

import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// These should trigger ESLint errors in platform layer
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

console.log("Platform violation - should fail ESLint");
