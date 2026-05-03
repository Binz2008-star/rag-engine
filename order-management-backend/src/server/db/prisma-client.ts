import { PrismaClient as GeneratedPrismaClient } from '@prisma/client'

if (!process.env.DATABASE_URL) {
  throw new Error('[DB FATAL] DATABASE_URL is not set. Cannot initialize Prisma client.')
}

export const prisma = new GeneratedPrismaClient({
  datasources: {
    db: {
      url: process.env.DATABASE_URL,
    },
  },
})

export type PrismaClient = GeneratedPrismaClient
