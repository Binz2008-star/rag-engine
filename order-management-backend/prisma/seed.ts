import { assertSeedingAllowed } from '@/server/lib/env-guard'
import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

// Block seeding in production environments
assertSeedingAllowed()

const prisma = new PrismaClient()

async function main() {
  try {
    console.log('🌱 Starting production-safe seed...')

    // Precompute password hash
    const passwordHash = await bcrypt.hash('demo123', 12)

    // 1. User
    console.log('📝 Creating/upserting demo user...')
    const user = await prisma.user.upsert({
      where: { email: 'demo@seller.com' },
      update: {
        fullName: 'Demo Seller',
        role: 'SELLER',
        isActive: true,
        passwordHash,
      },
      create: {
        email: 'demo@seller.com',
        fullName: 'Demo Seller',
        role: 'SELLER',
        isActive: true,
        passwordHash,
      },
    })
    console.log('✅ User created/upserted:', user.email)

    // 2. Seller
    console.log('📝 Creating/upserting demo seller...')
    const seller = await prisma.seller.upsert({
      where: { slug: 'demo-store' },
      update: {
        ownerUserId: user.id,
        brandName: 'Demo Store',
        whatsappNumber: '+1234567890',
        currency: 'USD',
        status: 'ACTIVE',
      },
      create: {
        ownerUserId: user.id,
        brandName: 'Demo Store',
        slug: 'demo-store',
        whatsappNumber: '+1234567890',
        currency: 'USD',
        status: 'ACTIVE',
      },
    })
    console.log('✅ Seller created/upserted:', seller.brandName)

    console.log('Products now handled by platform layer - skipping runtime seed')

    // 4. Customer - only after seller exists
    console.log('📝 Creating/upserting customer...')
    // Use existing unique constraint @@unique([sellerId, phone])
    const customer = await prisma.customer.upsert({
      where: {
        sellerId_phone: {
          sellerId: seller.id,
          phone: '+11234567890',
        },
      },
      update: {
        name: 'John Doe',
        addressText: '123 Main St, Demo City, DC 12345',
      },
      create: {
        sellerId: seller.id,
        name: 'John Doe',
        phone: '+11234567890',
        addressText: '123 Main St, Demo City, DC 12345',
      },
    })
    console.log('✅ Customer created/upserted:', customer.name)

    console.log('🎉 Production-safe seed completed successfully!')

  } catch (error) {
    console.error('❌ Seed failed:', error)
    process.exit(1)
  } finally {
    await prisma.$disconnect()
  }
}

main()
