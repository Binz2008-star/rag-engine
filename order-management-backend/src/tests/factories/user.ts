import { hashPassword } from '@/server/lib/auth'
import { prisma } from '../setup'

export interface CreateUserInput {
  email?: string
  fullName?: string
  password?: string
  role?: 'STAFF' | 'SELLER' | 'ADMIN'
  isActive?: boolean
}

let userCounter = 0

export function generateUniqueEmail(prefix = 'test'): string {
  userCounter++
  return `${prefix}.${Date.now()}.${userCounter}@test.local`
}

export async function createUser(input: CreateUserInput = {}) {
  const {
    email = generateUniqueEmail(),
    fullName = 'Test User',
    password = 'test-password-123',
    role = 'SELLER',
    isActive = true,
  } = input

  const passwordHash = await hashPassword(password)

  const user = await prisma.user.create({
    data: {
      email,
      fullName,
      passwordHash,
      role,
      isActive,
    },
  })

  return {
    ...user,
    plainPassword: password,
  }
}

export async function createInactiveUser(input: Omit<CreateUserInput, 'isActive'> = {}) {
  return createUser({ ...input, isActive: false })
}

export async function deleteUser(id: string) {
  await prisma.user.deleteMany({ where: { id } })
}
