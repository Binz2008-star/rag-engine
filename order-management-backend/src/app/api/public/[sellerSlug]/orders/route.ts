import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/server/db/prisma";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ sellerSlug: string }> }
) {
  try {
    const { sellerSlug } = await params;

    const seller = await prisma.seller.findUnique({
      where: { slug: sellerSlug },
      select: {
        id: true,
        brandName: true,
        slug: true,
      },
    });

    if (!seller) {
      return NextResponse.json({ error: "Seller not found" }, { status: 404 });
    }

    const orders = await prisma.order.findMany({
      where: { sellerId: seller.id },
      orderBy: { createdAt: "desc" },
      take: 20,
      select: {
        id: true,
        publicOrderNumber: true,
        status: true,
        paymentStatus: true,
        totalMinor: true,
        currency: true,
        createdAt: true,
      },
    });

    return NextResponse.json({
      seller,
      orders,
    });
  } catch (error) {
    console.error("Get orders error:", error);

    return NextResponse.json(
      { error: "Failed to get orders" },
      { status: 500 }
    );
  }
}
