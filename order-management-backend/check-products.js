const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  try {
    const seller = await prisma.seller.findUnique({
      where: { slug: 'test-store-2' },
      select: { id: true, brandName: true }
    });
    
    if (!seller) {
      console.log('Seller not found');
      return;
    }
    
    console.log('Seller:', seller);
    
    const products = await prisma.product.findMany({
      where: { 
        sellerId: seller.id,
        isActive: true 
      },
      select: { 
        id: true, 
        name: true, 
        priceMinor: true,
        stockQuantity: true
      }
    });
    
    console.log('Available products:', JSON.stringify(products, null, 2));
    
    if (products.length === 0) {
      console.log('No active products found. Creating a test product...');
      
      const newProduct = await prisma.product.create({
        data: {
          sellerId: seller.id,
          name: 'Test Product',
          description: 'A test product for business flow validation',
          priceMinor: 999,
          currency: 'USD',
          stockQuantity: 10,
          isActive: true
        }
      });
      
      console.log('Created test product:', JSON.stringify(newProduct, null, 2));
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
