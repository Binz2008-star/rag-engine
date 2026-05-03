import { prisma } from '@/server/db/prisma'
import { ApiError } from '@/server/http/api-error'
import { generateToken, verifyPassword } from '@/server/lib/auth'
import { generateRequestId } from '@/server/lib/logger'
import { LoginSchema } from '@/server/lib/validation'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const requestId = generateRequestId()
  
  try {
    // Parse and validate JSON body
    const rawBody = await request.json()
    const body = LoginSchema.parse(rawBody)
    
    // Find user
    const user = await prisma.user.findUnique({
      where: { email: body.email.toLowerCase().trim() },
      include: {
        ownedSeller: {
          select: { id: true },
        },
      },
    })

    if (!user || !user.isActive) {
      return NextResponse.json(
        { error: 'Invalid credentials', code: 'INVALID_CREDENTIALS', requestId },
        { status: 401, headers: { 'X-Request-ID': requestId } }
      )
    }

    // Verify password
    const isValidPassword = await verifyPassword(body.password, user.passwordHash)

    if (!isValidPassword) {
      return NextResponse.json(
        { error: 'Invalid credentials', code: 'INVALID_CREDENTIALS', requestId },
        { status: 401, headers: { 'X-Request-ID': requestId } }
      )
    }

    // Generate token
    const authUser = {
      id: user.id,
      email: user.email,
      role: user.role as 'STAFF' | 'SELLER' | 'ADMIN',
      sellerId: user.ownedSeller?.id ?? null,
    }
    
    const token = generateToken(authUser)

    return NextResponse.json(
      { user: authUser, token },
      { status: 200, headers: { 'X-Request-ID': requestId } }
    )
  } catch (error) {
    console.error('LOGIN_ERROR:', error)
    
    if (error instanceof ApiError) {
      return NextResponse.json(
        { error: error.message, code: error.code, requestId },
        { status: error.statusCode, headers: { 'X-Request-ID': requestId } }
      )
    }
    
    return NextResponse.json(
      { error: 'Login failed', code: 'INTERNAL_ERROR', requestId },
      { status: 500, headers: { 'X-Request-ID': requestId } }
    )
  }
}
