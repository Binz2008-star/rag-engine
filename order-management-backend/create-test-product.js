const { PrismaClient } = require('@prisma/client');

async function createTestProduct() {
  const prisma = new PrismaClient();

  try {
    // Find the seller
    const seller = await prisma.seller.findUnique({
      where: { slug: 'test-store-2' },
      select: { id: true, brandName: true, currency: true }
    });

    if (!seller) {
      console.log('Seller not found');
      return;
    }

    console.log('Found seller:', seller);

    // Create a test product
    const product = await prisma.product.create({
      data: {
        sellerId: seller.id,
        name: 'Test Product for Validation',
        slug: 'test-product-validation',
        description: 'A test product for business flow validation',
        priceMinor: 999,
        currency: seller.currency || 'USD',
        stockQuantity: 10,
        isActive: true
      }
    });

    console.log('Created test product:', {
      id: product.id,
      name: product.name,
      price: product.priceMinor,
      currency: product.currency,
      stock: product.stockQuantity
    });

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

createTestProduct();
