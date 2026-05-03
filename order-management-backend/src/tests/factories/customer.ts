import { prisma } from '../setup'

export interface CreateCustomerInput {
  sellerId: string
  name?: string
  phone?: string
  addressText?: string
}

let customerCounter = 0

export function generateUniquePhone(): string {
  customerCounter++
  return `+1555${String(Date.now()).slice(-6)}${customerCounter.toString().padStart(2, '0')}`
}

export async function createCustomer(input: CreateCustomerInput) {
  const {
    sellerId,
    name = 'Test Customer',
    phone = generateUniquePhone(),
    addressText = '123 Test St, Test City, TC 12345',
  } = input

  const customer = await prisma.customer.create({
    data: {
      sellerId,
      name,
      phone,
      addressText,
    },
  })

  return customer
}

export async function deleteCustomer(id: string) {
  await prisma.customer.deleteMany({ where: { id } })
}
