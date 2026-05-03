import { prisma } from '@/server/db/prisma';
import { NextResponse } from 'next/server';

export async function GET() {
  try {
    const orderId = 'cmnr5p7kl00137s2hfm7clnn4';
    const sellerId = 'cmnr4cnhi0002r794t4fmc8kq';

    // Test basic database connection
    const totalOrders = await prisma.order.count();
    console.log('Test endpoint - total orders:', totalOrders);

    // Test order exists
    const orderExists = await prisma.order.findFirst({
      where: { id: orderId },
    });

    // Test order with seller
    const orderWithSeller = await prisma.order.findFirst({
      where: {
        id: orderId,
        sellerId: sellerId,
      },
    });

    return NextResponse.json({
      success: true,
      data: {
        totalOrders,
        orderExists: !!orderExists,
        orderWithSeller: !!orderWithSeller,
        orderDetails: orderExists ? {
          id: orderExists.id,
          sellerId: orderExists.sellerId,
          status: orderExists.status,
        } : null,
      },
    });
  } catch (error) {
    console.error('Test endpoint error:', error);
    return NextResponse.json({
      success: false,
      error: {
        code: "INTERNAL_ERROR",
        message: "Test failed",
        details: error instanceof Error ? error.message : String(error),
      },
    }, { status: 500 });
  }
}
