import { prisma } from "@/server/db/prisma";
import { calculateOrderTotal, generatePublicOrderNumber } from "@/server/lib/utils";
import type { Prisma } from "@prisma/client";

import { createOrderEvent } from "./order-events.authority";
import type {
  CreatePublicCheckoutInput,
} from "./public-checkout.schema";
import type {
  HydratedPublicCheckoutOrder,
  PublicCheckoutPricedItem,
} from "./public-checkout.types";

const DEFAULT_PAYMENT_TYPE = "CASH_ON_DELIVERY";
const DEFAULT_SOURCE = "public_api";

async function findSellerBySlug(
  tx: Prisma.TransactionClient,
  sellerSlug: string
) {
  const seller = await tx.seller.findUnique({
    where: { slug: sellerSlug },
    select: {
      id: true,
      slug: true,
      currency: true,
      status: true,
    },
  });

  if (!seller) {
    throw new Error("Seller not found");
  }

  if (seller.status !== "ACTIVE") {
    throw new Error("Seller is not active");
  }

  return seller;
}

function buildPricedItems(
  items: CreatePublicCheckoutInput["items"]
): PublicCheckoutPricedItem[] {
  return items.map((item) => ({
    productId: item.productId,
    productNameSnapshot: `Product ${item.productId}`,
    unitPriceMinor: 0,
    quantity: item.quantity,
    lineTotalMinor: 0,
  }));
}

async function upsertCustomer(
  tx: Prisma.TransactionClient,
  sellerId: string,
  customer: CreatePublicCheckoutInput["customer"]
) {
  return tx.customer.upsert({
    where: {
      sellerId_phone: {
        sellerId,
        phone: customer.phone,
      },
    },
    update: {
      name: customer.name,
      addressText: customer.addressText,
    },
    create: {
      sellerId,
      name: customer.name,
      phone: customer.phone,
      addressText: customer.addressText,
    },
  });
}

async function createOrderAggregate(
  tx: Prisma.TransactionClient,
  args: {
    sellerId: string;
    customerId: string;
    pricedItems: PublicCheckoutPricedItem[];
    currency: string;
    notes?: string;
  }
) {
  const totals = calculateOrderTotal(
    args.pricedItems.map((item) => ({
      unitPriceMinor: item.unitPriceMinor,
      quantity: item.quantity,
    })),
    0
  );

  const order = await tx.order.create({
    data: {
      sellerId: args.sellerId,
      customerId: args.customerId,
      publicOrderNumber: generatePublicOrderNumber(),
      status: "PENDING",
      paymentType: DEFAULT_PAYMENT_TYPE,
      paymentStatus: "PENDING",
      subtotalMinor: totals.subtotalMinor,
      deliveryFeeMinor: totals.deliveryFeeMinor,
      totalMinor: totals.totalMinor,
      currency: args.currency,
      source: DEFAULT_SOURCE,
      notes: args.notes,
    },
  });

  await tx.orderItem.createMany({
    data: args.pricedItems.map((item) => ({
      orderId: order.id,
      productId: item.productId,
      productNameSnapshot: item.productNameSnapshot,
      unitPriceMinor: item.unitPriceMinor,
      quantity: item.quantity,
      lineTotalMinor: item.lineTotalMinor,
    })),
  });

  return order;
}

async function hydrateOrder(
  tx: Prisma.TransactionClient,
  orderId: string
): Promise<HydratedPublicCheckoutOrder> {
  const order = await tx.order.findUnique({
    where: { id: orderId },
    include: {
      customer: true,
      orderItems: true,
    },
  });

  if (!order) {
    throw new Error("Failed to hydrate created order");
  }

  return order as HydratedPublicCheckoutOrder;
}

export async function createPublicOrder(
  input: CreatePublicCheckoutInput
): Promise<HydratedPublicCheckoutOrder> {
  return prisma.$transaction(async (tx) => {
    const seller = await findSellerBySlug(tx, input.sellerSlug);
    const pricedItems = buildPricedItems(input.items);
    const customer = await upsertCustomer(tx, seller.id, input.customer);

    const order = await createOrderAggregate(tx, {
      sellerId: seller.id,
      customerId: customer.id,
      pricedItems,
      currency: seller.currency,
      notes: input.notes,
    });

    await createOrderEvent(tx, {
      orderId: order.id,
      eventType: "order_created",
      payload: {
        source: DEFAULT_SOURCE,
        sellerId: seller.id,
        customerId: customer.id,
        itemCount: pricedItems.length,
      },
    });

    return hydrateOrder(tx, order.id);
  });
}
