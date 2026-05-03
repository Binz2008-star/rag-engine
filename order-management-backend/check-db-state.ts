import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function checkDbState() {
  try {
    console.log('🔍 Checking database state...')

    const userCount = await prisma.user.count()
    const sellerCount = await prisma.seller.count()
    const productCount = await prisma.product.count()
    const customerCount = await prisma.customer.count()

    console.log(`Users: ${userCount}`)
    console.log(`Sellers: ${sellerCount}`)
    console.log(`Products: ${productCount}`)
    console.log(`Customers: ${customerCount}`)

    if (sellerCount > 0) {
      const sellers = await prisma.seller.findMany({
        select: {
          id: true,
          brandName: true,
          slug: true,
          ownerUserId: true,
        }
      })
      console.log('Sellers:', sellers)

      // Check if demo-store exists
      const demoSeller = sellers.find(s => s.slug === 'demo-store')
      if (demoSeller) {
        console.log('✅ demo-store seller exists:', demoSeller.id)
      } else {
        console.log('❌ demo-store seller NOT found')
      }
    }

    if (userCount > 0) {
      const users = await prisma.user.findMany({
        select: {
          id: true,
          email: true,
          role: true,
        }
      })
      console.log('Users:', users)
    }

  } catch (error) {
    console.error('❌ Error checking DB state:', error)
  } finally {
    await prisma.$disconnect()
  }
}

checkDbState()
