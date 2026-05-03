import { prisma } from "@/server/db/prisma";
import type { Prisma } from "@prisma/client";

export interface ListSellerOrdersParams {
  sellerId: string;
  page: number;
  limit: number;
  status?: string;
  paymentStatus?: string;
  customerId?: string;
}

export interface ListedOrder {
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
  _count: {
    events: number;
  };
}

export interface ListSellerOrdersResult {
  orders: ListedOrder[];
  total: number;
}

export async function listSellerOrders(params: ListSellerOrdersParams): Promise<ListSellerOrdersResult> {
  const { sellerId, page, limit, status, paymentStatus, customerId } = params;
  const skip = (page - 1) * limit;

  const where: Prisma.OrderWhereInput = {
    sellerId,
    ...(status && { status }),
    ...(paymentStatus && { paymentStatus }),
    ...(customerId && { customerId }),
  };

  const [orders, total] = await Promise.all([
    prisma.order.findMany({
      where,
      include: {
        customer: true,
        orderItems: {
          select: {
            id: true,
            productId: true,
            productNameSnapshot: true,
            unitPriceMinor: true,
            quantity: true,
            lineTotalMinor: true,
          },
        },
        _count: {
          select: {
            events: true,
          },
        },
      },
      orderBy: { createdAt: "desc" },
      skip,
      take: limit,
    }),
    prisma.order.count({ where }),
  ]);

  return { orders, total };
}
