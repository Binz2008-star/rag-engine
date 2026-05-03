import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

async function debugSeed() {
  try {
    console.log('🔍 Debug seeding process...')
    
    // Start transaction
    const result = await prisma.$transaction(async (tx) => {
      console.log('📝 Step 1: Creating user...')
      
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
      
      console.log('📝 Step 2: Creating seller...')
      
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
      
      console.log('📝 Step 3: Verifying seller exists before creating products...')
      
      const sellerCheck = await tx.seller.findUnique({
        where: { id: seller.id },
        select: { id: true, brandName: true }
      })
      
      console.log('✅ Seller verification:', sellerCheck)
      
      console.log('📝 Step 4: Creating first product...')
      
      const product = await tx.product.create({
        data: {
          sellerId: seller.id,
          name: 'Canvas Sneakers',
          slug: 'canvas-sneakers',
          description: 'Comfortable canvas sneakers',
          priceMinor: 3499,
          currency: 'USD',
          stockQuantity: 50,
          isActive: true,
        },
      })
      
      console.log('✅ Product created:', product.id)
      
      return { user, seller, product }
    })
    
    console.log('🎉 Transaction completed successfully!')
    console.log('User:', result.user.id)
    console.log('Seller:', result.seller.id)
    console.log('Product:', result.product.id)
    
  } catch (error) {
    console.error('❌ Debug seed failed:', error)
    console.error('Error details:', error.message)
    if (error.code) {
      console.error('Prisma error code:', error.code)
    }
  } finally {
    await prisma.$disconnect()
  }
}

debugSeed()
