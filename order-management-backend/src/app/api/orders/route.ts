/**
 * Orders API - Create Order
 * 
 * POST /api/orders
 * Creates a new order with items
 */
import { prisma } from '@/server/db/prisma'
import { generateRequestId } from '@/server/lib/logger'
import { CreateOrderSchema } from '@/server/lib/validation'
import { NextRequest, NextResponse } from 'next/server'
import jwt from 'jsonwebtoken'
import { env } from '@/server/lib/env'

interface JWTPayload {
  id: string
  email: string
  role: string
  sellerId: string | null
}

/**
 * Generate unique public order number
 */
async function generateOrderNumber(sellerId: string): Promise<string> {
  const date = new Date()
  const prefix = `ORD-${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}`
  
  // Count existing orders for this seller today to create sequence
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  const count = await prisma.order.count({
    where: {
      sellerId,
      createdAt: { gte: today },
    },
  })
  
  const sequence = String(count + 1).padStart(4, '0')
  return `${prefix}-${sequence}`
}

/**
 * Verify JWT token and extract user
 */
function verifyToken(request: NextRequest): JWTPayload | null {
  const authHeader = request.headers.get('authorization')
  if (!authHeader?.startsWith('Bearer ')) {
    return null
  }
  
  const token = authHeader.substring(7)
  
  try {
    return jwt.verify(token, env.JWT_SECRET) as JWTPayload
  } catch {
    return null
  }
}

/**
 * POST handler - Create new order
 */
export async function POST(request: NextRequest) {
  const requestId = generateRequestId()
  
  try {
    // Verify authentication
    const user = verifyToken(request)
    if (!user || !user.sellerId) {
      return NextResponse.json(
        { error: 'Unauthorized - Seller access required', code: 'UNAUTHORIZED', requestId },
        { status: 401 }
      )
    }
    
    // Parse and validate body
    const rawBody = await request.json()
    const body = CreateOrderSchema.parse(rawBody)
    
    // Validate products exist and calculate totals
    const productIds = body.items.map(item => item.productId)
    const products = await prisma.product.findMany({
      where: { 
        id: { in: productIds },
        sellerId: user.sellerId,
      },
    })
    
    if (products.length !== productIds.length) {
      return NextResponse.json(
        { error: 'Some products not found', code: 'PRODUCTS_NOT_FOUND', requestId },
        { status: 400 }
      )
    }
    
    // Create order with transaction
    const order = await prisma.$transaction(async (tx) => {
      const orderNumber = await generateOrderNumber(user.sellerId!)
      
      // Calculate total
      const totalMinor = body.items.reduce((sum, item) => {
        return sum + (item.unitPriceMinor * item.quantity)
      }, 0)
      
      // Create order
      const newOrder = await tx.order.create({
        data: {
          publicOrderNumber: orderNumber,
          sellerId: user.sellerId!,
          customerName: body.customerName,
          customerPhone: body.customerPhone,
          customerAddress: body.customerAddress || null,
          totalMinor,
          currency: 'USD',
          status: 'PENDING',
          paymentStatus: 'UNPAID',
          notes: body.notes || null,
        },
      })
      
      // Create order items
      await tx.orderItem.createMany({
        data: body.items.map(item => ({
          orderId: newOrder.id,
          productId: item.productId,
          productNameSnapshot: item.productNameSnapshot,
          unitPriceMinor: item.unitPriceMinor,
          quantity: item.quantity,
        })),
      })
      
      // Create audit event
      await tx.orderEvent.create({
        data: {
          orderId: newOrder.id,
          actorUserId: user.id,
          eventType: 'order_created',
          payload: {
            totalMinor,
            itemCount: body.items.length,
          },
        },
      })
      
      // Return order with items
      return tx.order.findUnique({
        where: { id: newOrder.id },
        include: {
          items: true,
          customer: true,
        },
      })
    })
    
    return NextResponse.json(
      { 
        success: true, 
        order,
        message: 'Order created successfully' 
      },
      { status: 201 }
    )
    
  } catch (error) {
    console.error('CREATE_ORDER_ERROR:', error)
    
    return NextResponse.json(
      { error: 'Failed to create order', code: 'CREATE_FAILED', requestId },
      { status: 500 }
    )
  }
}
