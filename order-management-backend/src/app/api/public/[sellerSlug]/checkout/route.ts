import { NextRequest, NextResponse } from "next/server";
import { ZodError } from "zod";

import { createPublicOrder } from "@/server/modules/orders/public-checkout.authority";
import { createPublicCheckoutSchema } from "@/server/modules/orders/public-checkout.schema";

type RouteParams = Promise<{ sellerSlug: string }>;

type LegacyCheckoutBody = {
  customer?: {
    name?: string;
    phone?: string;
    addressText?: string;
  };
  customerName?: string;
  customerPhone?: string;
  addressText?: string;
  items?: Array<{ productId: string; quantity: number }>;
  notes?: string;
  [key: string]: unknown;
};

function normalizeCheckoutPayload(
  sellerSlug: string,
  body: LegacyCheckoutBody
) {
  const customer = body.customer ?? {
    name: body.customerName,
    phone: body.customerPhone,
    addressText: body.addressText,
  };

  return {
    sellerSlug,
    customer,
    items: body.items,
    notes: body.notes,
  };
}

export async function POST(request: NextRequest, { params }: { params: RouteParams }) {
  try {
    const { sellerSlug } = await params;
    const rawBody: LegacyCheckoutBody = await request.json();
    const normalizedPayload = normalizeCheckoutPayload(sellerSlug, rawBody);
    const command = createPublicCheckoutSchema.parse(normalizedPayload);

    const order = await createPublicOrder(command);

    return NextResponse.json(
      {
        id: order.id,
        publicOrderNumber: order.publicOrderNumber,
        status: order.status,
        paymentStatus: order.paymentStatus,
        subtotalMinor: order.subtotalMinor,
        deliveryFeeMinor: order.deliveryFeeMinor,
        totalMinor: order.totalMinor,
        currency: order.currency,
        notes: order.notes,
        customer: {
          id: order.customer.id,
          name: order.customer.name,
          phone: order.customer.phone,
          addressText: order.customer.addressText,
        },
        items: order.orderItems,
        createdAt: order.createdAt,
      },
      { status: 201 }
    );
  } catch (error) {
    console.error("Create order error:", error);

    if (error instanceof ZodError) {
      return NextResponse.json(
        {
          error: "Validation failed",
          details: error.flatten(),
        },
        { status: 400 }
      );
    }

    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to create order",
      },
      { status: 500 }
    );
  }
}
