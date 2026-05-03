import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
  try {
    const orderId = 'cmnr5p7kl00137s2hfm7clnn4';
    console.log('Checking order:', orderId);
    
    // Check if order exists at all
    const anyOrder = await prisma.order.findFirst({
      where: { id: orderId },
    });
    console.log('Order exists in database:', !!anyOrder);
    
    if (anyOrder) {
      console.log('Order details:', {
        id: anyOrder.id,
        sellerId: anyOrder.sellerId,
        publicOrderNumber: anyOrder.publicOrderNumber,
        status: anyOrder.status,
      });
    }
    
    // Check with seller filter
    const sellerOrder = await prisma.order.findFirst({
      where: {
        id: orderId,
        sellerId: 'cmnr4cnhi0002r794t4fmc8kq',
      },
    });
    console.log('Order exists for seller:', !!sellerOrder);
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
