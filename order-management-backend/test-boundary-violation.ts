// === BOUNDARY VIOLATION TEST ===
// This file should trigger ESLint errors
// Run: npm run lint

import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// These should ALL trigger ESLint errors:

// 1. Direct Prisma import (should trigger error)
await prisma.order.findMany();

// 2. Payment access (should trigger error)
await prisma.paymentAttempt.findMany();

// 3. User access (should trigger error)
await prisma.user.findMany();

// 4. Transactional mutations (should trigger error)
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

// 5. Status updates (should trigger error)
await prisma.order.update({
  where: { id: "test" },
  data: { status: "COMPLETED" },
});

console.log("If you see these errors, boundary enforcement is working!");
