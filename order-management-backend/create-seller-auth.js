const { PrismaClient } = require('@prisma/client');
const jwt = require('jsonwebtoken');

async function createSellerAuth() {
  const prisma = new PrismaClient();
  
  try {
    // Find the seller
    const seller = await prisma.seller.findUnique({
      where: { slug: 'test-store-2' },
      include: { owner: true }
    });
    
    if (!seller) {
      console.log('Seller not found');
      return;
    }
    
    console.log('Found seller:', seller.brandName);
    console.log('Owner user:', seller.owner.email, seller.owner.role);
    
    // Create JWT token for the owner
    const token = jwt.sign(
      {
        id: seller.owner.id,
        email: seller.owner.email,
        role: seller.owner.role,
        sellerId: seller.id
      },
      process.env.JWT_SECRET || 'dev-secret',
      { expiresIn: '7d' }
    );
    
    console.log('Auth token:', token);
    console.log('Use this token for seller API calls');
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

createSellerAuth();
