import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

async function fixSeed() {
  try {
    console.log('🔧 Fixing seed with transaction...')
    
    const result = await prisma.$transaction(async (tx) => {
      // 1. User
      console.log('📝 Creating user...')
      const user = await tx.user.create({
        data: {
          email: 'demo@seller.com',
          fullName: 'Demo Seller',
          role: 'SELLER',
          isActive: true,
          passwordHash: await bcrypt.hash('demo123', 12),
        },
      })
      console.log('✅ User created:', user.id)

      // 2. Seller
      console.log('📝 Creating seller...')
      const seller = await tx.seller.create({
        data: {
          ownerUserId: user.id,
          brandName: 'Demo Store',
          slug: 'demo-store',
          currency: 'USD',
          status: 'ACTIVE',
          whatsappNumber: '+1234567890',
        },
      })
      console.log('✅ Seller created:', seller.id)

      // 3. Products
      console.log('📝 Creating products...')
      const productsData = [
        { name: 'Classic T-Shirt', slug: 'classic-tshirt', priceMinor: 1999 },
        { name: 'Denim Jeans', slug: 'denim-jeans', priceMinor: 4999 },
        { name: 'Canvas Sneakers', slug: 'canvas-sneakers', priceMinor: 3499 },
      ]

      const products = []
      for (const p of productsData) {
        const product = await tx.product.create({
          data: {
            sellerId: seller.id,
            name: p.name,
            slug: p.slug,
            priceMinor: p.priceMinor,
            currency: 'USD',
            stockQuantity: 50,
            isActive: true,
          },
        })
        products.push(product)
        console.log('✅ Product created:', product.name)
      }

      // 4. Customer
      console.log('📝 Creating customer...')
      const customer = await tx.customer.create({
        data: {
          sellerId: seller.id,
          name: 'John Doe',
          phone: '+11234567890',
          addressText: '123 Main St, Demo City, DC 12345',
        },
      })
      console.log('✅ Customer created:', customer.name)

      return { user, seller, products, customer }
    })

    console.log('🎉 Fix seed completed!')
    console.log(`Users: 1`)
    console.log(`Sellers: 1`)
    console.log(`Products: ${result.products.length}`)
    console.log(`Customers: 1`)
    
  } catch (error) {
    console.error('❌ Fix seed failed:', error)
    process.exit(1)
  } finally {
    await prisma.$disconnect()
  }
}

fixSeed()
