import { NextRequest } from 'next/server'
import {
  type AdminAuthUser,
  type AuthUser,
  type SellerAuthUser,
  getCurrentUser,
  requireAdmin,
  requireSeller,
} from '@/server/lib/auth'

export async function requireRequestUser(request: NextRequest): Promise<AuthUser> {
  return getCurrentUser(request)
}

export async function requireRequestSeller(request: NextRequest): Promise<SellerAuthUser> {
  return requireSeller(await getCurrentUser(request))
}

export async function requireRequestAdmin(request: NextRequest): Promise<AdminAuthUser> {
  return requireAdmin(await getCurrentUser(request))
}

