import { prisma } from "@/server/db/prisma";
import { createOrderEvent } from "@/server/modules/orders/order-events.authority";

export interface CreateV1OrderCommand {
  sellerId: string;
  customerId: string;
  paymentType: string;
  paymentStatus: string;
  notes?: string;
  items: Array<{
    productId: string;
    quantity: number;
  }>;
}

export interface V1OrderResult {
  id: string;
  sellerId: string;
  publicOrderNumber: string;
  status: string;
  paymentStatus: string;
  paymentType: string;
  subtotalMinor: number;
  deliveryFeeMinor: number;
  totalMinor: number;
  currency: string;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
  customer: {
    id: string;
    name: string;
    phone: string;
    addressText: string | null;
  };
  orderItems: Array<{
    id: string;
    productId: string;
    productNameSnapshot: string;
    unitPriceMinor: number;
    quantity: number;
    lineTotalMinor: number;
  }>;
}

function calculateTotals(items: Array<{ quantity: number }>) {
  // TODO: Replace with real product price lookups from platform catalog
  const subtotalMinor = items.reduce((sum, item) => sum + item.quantity * 1000, 0);
  const deliveryFeeMinor = 500;
  const totalMinor = subtotalMinor + deliveryFeeMinor;
  return { subtotalMinor, deliveryFeeMinor, totalMinor };
}

export async function createV1Order(command: CreateV1OrderCommand, actorSellerId: string): Promise<V1OrderResult> {
  // Verify the requested seller matches the authenticated seller
  if (command.sellerId !== actorSellerId) {
    throw new Error(
      `Seller ID mismatch: requested ${command.sellerId}, but authenticated user is ${actorSellerId}`
    );
  }

  return prisma.$transaction(async (tx) => {
    // Verify customer belongs to the authenticated seller
    const customer = await tx.customer.findFirst({
      where: {
        id: command.customerId,
        sellerId: actorSellerId,
      },
    });

    if (!customer) {
      throw new Error("Customer not found or does not belong to seller");
    }

    const totals = calculateTotals(command.items);

    const order = await tx.order.create({
      data: {
        sellerId: actorSellerId,
        customerId: command.customerId,
        publicOrderNumber: `ORD-${Date.now()}`,
        status: "PENDING",
        paymentType: command.paymentType,
        paymentStatus: command.paymentStatus,
        subtotalMinor: totals.subtotalMinor,
        deliveryFeeMinor: totals.deliveryFeeMinor,
        totalMinor: totals.totalMinor,
        currency: "USD",
        notes: command.notes,
        orderItems: {
          // TODO: Replace with real product snapshots from platform catalog
          create: command.items.map((item) => ({
            productId: item.productId,
            productNameSnapshot: `Product ${item.productId}`,
            unitPriceMinor: 1000,
            quantity: item.quantity,
            lineTotalMinor: item.quantity * 1000,
          })),
        },
      },
      include: {
        customer: true,
        orderItems: true,
      },
    });

    await createOrderEvent(tx, {
      orderId: order.id,
      eventType: "order_created",
      payload: {
        source: "v1_api",
        itemCount: order.orderItems.length,
      },
    });

    return order;
  });
}
