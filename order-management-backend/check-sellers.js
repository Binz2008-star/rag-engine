const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  try {
    const sellers = await prisma.seller.findMany({ 
      select: { slug: true, brandName: true }, 
      take: 5 
    });
    console.log('Sellers:', JSON.stringify(sellers, null, 2));
    
    // Also check products
    const products = await prisma.product.findMany({
      select: { id: true, name: true, sellerId: true, isActive: true },
      take: 5
    });
    console.log('Products:', JSON.stringify(products, null, 2));
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
