import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function completeSeed() {
  try {
    console.log('🌱 Completing demo data seeding...')

    // Get existing seller
    const sellers = await prisma.seller.findMany({
      select: { id: true, brandName: true, slug: true }
    })
    console.log('Available sellers:', sellers)

    const seller = await prisma.seller.findFirst({
      where: { slug: 'demo-store' }
    })

    if (!seller) {
      throw new Error('Demo seller not found. Run debug-seed.ts first.')
    }

    console.log('✅ Found seller:', seller.brandName)

    // Create remaining products
    const productsData = [
      {
        name: 'Classic T-Shirt',
        slug: 'classic-t-shirt',
        description: 'Classic cotton t-shirt in various colors',
        priceMinor: 1999,
        stockQuantity: 100,
      },
      {
        name: 'Denim Jeans',
        slug: 'denim-jeans',
        description: 'Classic denim jeans with modern fit',
        priceMinor: 4999,
        stockQuantity: 30,
      },
    ]

    for (const productData of productsData) {
      const product = await prisma.product.create({
        data: {
          sellerId: seller.id,
          ...productData,
          currency: 'USD',
          isActive: true,
        },
      })
      console.log('✅ Product created:', product.name)
    }

    // Create demo customer
    const customer = await prisma.customer.create({
      data: {
        sellerId: seller.id,
        name: 'John Doe',
        phone: '+11234567890',
        addressText: '123 Main St, Demo City, DC 12345',
      },
    })

    console.log('✅ Customer created:', customer.name)

    // Verify final state
    const finalCounts = await prisma.$transaction({
      users: () => prisma.user.count(),
      sellers: () => prisma.seller.count(),
      products: () => prisma.product.count(),
      customers: () => prisma.customer.count(),
    })

    console.log('📊 Final database state:')
    console.log(`Users: ${finalCounts.users}`)
    console.log(`Sellers: ${finalCounts.sellers}`)
    console.log(`Products: ${finalCounts.products}`)
    console.log(`Customers: ${finalCounts.customers}`)

    console.log('🎉 Demo data seeding completed successfully!')

  } catch (error) {
    console.error('❌ Complete seed failed:', error)
  } finally {
    await prisma.$disconnect()
  }
}

completeSeed()
