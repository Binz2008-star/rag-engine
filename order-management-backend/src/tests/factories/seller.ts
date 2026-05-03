import { prisma } from '../setup'

export interface CreateSellerInput {
  ownerUserId: string
  brandName?: string
  slug?: string
  whatsappNumber?: string
  currency?: string
  status?: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED'
}

let sellerCounter = 0

export function generateUniqueSlug(prefix = 'test-store'): string {
  sellerCounter++
  return `${prefix}-${Date.now()}-${sellerCounter}`
}

export async function createSeller(input: CreateSellerInput) {
  const {
    ownerUserId,
    brandName = 'Test Store',
    slug = generateUniqueSlug(),
    whatsappNumber = '+1234567890',
    currency = 'USD',
    status = 'ACTIVE',
  } = input

  const seller = await prisma.seller.create({
    data: {
      ownerUserId,
      brandName,
      slug,
      whatsappNumber,
      currency,
      status,
    },
  })

  return seller
}

export async function deleteSeller(id: string) {
  await prisma.seller.deleteMany({ where: { id } })
}
