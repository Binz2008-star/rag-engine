const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function removeForeignKey() {
  try {
    console.log('Removing foreign key constraint from order_items...');
    
    await prisma.$executeRaw`ALTER TABLE order_items DROP CONSTRAINT IF EXISTS order_items_product_id_fkey`;
    
    console.log('Foreign key constraint removed successfully');
  } catch (error) {
    console.error('Error removing foreign key:', error);
  } finally {
    await prisma.$disconnect();
  }
}

removeForeignKey();
