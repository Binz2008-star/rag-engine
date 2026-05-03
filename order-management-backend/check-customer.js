const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  try {
    const seller = await prisma.seller.findFirst({ where: { slug: 'demo-store' } });
    const customer = await prisma.customer.findFirst({ where: { sellerId: seller.id } });
    console.log('Seller ID:', seller.id);
    console.log('Customer ID:', customer.id);
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main();
