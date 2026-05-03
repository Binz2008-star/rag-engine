import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

async function createDemoSeller() {
  try {
    console.log('Creating demo seller...')

    // Create demo user
    const hashedPassword = await bcrypt.hash('demo123', 12)

    const user = await prisma.user.upsert({
      where: { email: 'demo@seller.com' },
      update: {},
      create: {
        email: 'demo@seller.com',
        fullName: 'Demo Store Owner',
        passwordHash: hashedPassword,
        role: 'SELLER',
        isActive: true,
      },
    })

    console.log('User created:', user.id)

    // Create demo seller
    const seller = await prisma.seller.upsert({
      where: { slug: 'demo-store' },
      update: {},
      create: {
        ownerUserId: user.id,
        brandName: 'Demo Store',
        slug: 'demo-store',
        currency: 'USD',
        status: 'ACTIVE',
        whatsappNumber: '+1234567890',
      },
    })

    console.log('Seller created:', seller.id)

    // Create demo products
    const products = [
      {
        name: 'Canvas Sneakers',
        slug: 'canvas-sneakers',
        description: 'Comfortable canvas sneakers for everyday wear',
        priceMinor: 3499,
        currency: 'USD',
        stockQuantity: 50,
        isActive: true,
      },
      {
        name: 'Classic T-Shirt',
        slug: 'classic-t-shirt',
        description: 'Classic cotton t-shirt in various colors',
        priceMinor: 1999,
        currency: 'USD',
        stockQuantity: 100,
        isActive: true,
      },
      {
        name: 'Denim Jeans',
        slug: 'denim-jeans',
        description: 'Classic denim jeans with modern fit',
        priceMinor: 4999,
        currency: 'USD',
        stockQuantity: 30,
        isActive: true,
      },
    ]

    for (const productData of products) {
      const product = await prisma.product.create({
        data: {
          sellerId: seller.id,
          ...productData,
        },
      })
      console.log('Product created:', product.name)
    }

    console.log('✅ Demo seller and products created successfully!')

  } catch (error) {
    console.error('❌ Error creating demo seller:', error)
  } finally {
    await prisma.$disconnect()
  }
}

createDemoSeller()
