import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
  try {
    const seller = await prisma.seller.findFirst({ where: { slug: 'demo-store' } });
    console.log('Seller ID:', seller.id);
    
    const customer = await prisma.customer.findFirst({ 
      where: { 
        id: 'cmnr4x2mj0004o5jq3xjwtw4l',
        sellerId: seller.id 
      } 
    });
    
    if (customer) {
      console.log('Customer found and belongs to seller:', customer.name);
    } else {
      console.log('Customer NOT found or does not belong to seller');
      
      // Check all customers for this seller
      const allCustomers = await prisma.customer.findMany({ 
        where: { sellerId: seller.id } 
      });
      console.log('All customers for this seller:', allCustomers.map(c => ({ id: c.id, name: c.name })));
    }
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
