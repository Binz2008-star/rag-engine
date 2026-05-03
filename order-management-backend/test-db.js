const { PrismaClient } = require('@prisma/client');

async function testConnection() {
  let prisma;
  try {
    console.log('Testing database connection...');
    prisma = new PrismaClient();
    
    // Test basic connection
    const result = await prisma.$queryRaw`SELECT 1 as test`;
    console.log('Database connection successful:', result);
    
    // Test seller query
    const sellers = await prisma.seller.findMany({ 
      select: { slug: true, brandName: true }, 
      take: 5 
    });
    console.log('Sellers found:', sellers.length);
    console.log('First seller:', sellers[0]);
    
    // Test if there are products for the first seller
    if (sellers.length > 0) {
      const products = await prisma.product.findMany({
        where: { 
          sellerId: sellers[0].id,
          isActive: true 
        },
        select: { 
          id: true, 
          name: true, 
          priceMinor: true,
          stockQuantity: true
        },
        take: 5
      });
      console.log('Products for seller', sellers[0].slug, ':', products.length);
      
      if (products.length === 0) {
        console.log('Creating a test product...');
        const newProduct = await prisma.product.create({
          data: {
            sellerId: sellers[0].id,
            name: 'Test Product for Flow',
            description: 'A test product for business flow validation',
            priceMinor: 999,
            currency: sellers[0].currency || 'USD',
            stockQuantity: 10,
            isActive: true
          }
        });
        console.log('Created test product:', { id: newProduct.id, name: newProduct.name, price: newProduct.priceMinor });
      }
    }
    
  } catch (error) {
    console.error('Database connection failed:', error);
  } finally {
    if (prisma) {
      await prisma.$disconnect();
    }
  }
}

testConnection();
