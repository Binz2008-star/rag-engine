import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { listSellerOrders } from '@/server/modules/orders/order-list.query'
import { createV1Order } from '@/server/modules/orders/v1-order.authority'
import { OrderCreateResponseSchema, OrderResponseSchema } from '@/shared/schemas/order-response'
import { CreateOrderSchema, GetOrdersSchema } from '@/shared/schemas/orders'
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

export const runtime = 'nodejs'

// === V1 ORDERS API ===
// Versioned API - NEVER BREAK COMPATIBILITY IN V1

type ApiErrorLike = Error & { code?: string; statusCode?: number }

// GET /api/v1/orders - List orders
export async function GET(request: NextRequest) {
  try {
    console.log('GET /api/v1/orders - processing request');
    const user = await getCurrentUser(request)
    console.log('GET /api/v1/orders - user authenticated:', !!user);
    requireSeller(user)
    console.log('GET /api/v1/orders - seller verified');

    const { searchParams } = new URL(request.url)
    const query = GetOrdersSchema.parse({
      page: searchParams.get('page') || undefined,
      limit: searchParams.get('limit') || undefined,
      status: searchParams.get('status') || undefined,
      paymentStatus: searchParams.get('paymentStatus') || undefined,
      customerId: searchParams.get('customerId') || undefined,
    })

    const { page, limit } = query

    const { orders, total } = await listSellerOrders({
      sellerId: user.sellerId!,
      page,
      limit,
      status: query.status,
      paymentStatus: query.paymentStatus,
      customerId: query.customerId,
    })

    const totalPages = Math.ceil(total / limit)

    // Build response according to V1 contract
    const response = {
      success: true,
      data: {
        orders: orders.map(order => ({
          id: order.id,
          sellerId: order.sellerId,
          publicOrderNumber: order.publicOrderNumber,
          status: order.status,
          paymentStatus: order.paymentStatus,
          paymentType: order.paymentType,
          subtotalMinor: order.subtotalMinor,
          deliveryFeeMinor: order.deliveryFeeMinor,
          totalMinor: order.totalMinor,
          currency: order.currency,
          notes: order.notes,
          createdAt: order.createdAt.toISOString(),
          updatedAt: order.updatedAt.toISOString(),
          customer: {
            id: order.customer.id,
            name: order.customer.name,
            phone: order.customer.phone,
            addressText: order.customer.addressText,
          },
          items: order.orderItems.map(item => ({
            id: item.id,
            productId: item.productId,
            productNameSnapshot: item.productNameSnapshot,
            unitPriceMinor: item.unitPriceMinor,
            quantity: item.quantity,
            lineTotalMinor: item.lineTotalMinor,
          })),
        })),
        pagination: {
          page,
          limit,
          total,
          totalPages,
          hasNext: page < totalPages,
          hasPrev: page > 1,
        },
      },
    }

    // Enforce V1 response contract
    const safe = z.object({
      success: z.literal(true),
      data: z.object({
        orders: z.array(OrderResponseSchema),
        pagination: z.object({
          page: z.number().int().positive(),
          limit: z.number().int().positive(),
          total: z.number().int().nonnegative(),
          totalPages: z.number().int().nonnegative(),
          hasNext: z.boolean(),
          hasPrev: z.boolean(),
        }),
      }),
    }).parse(response)

    return NextResponse.json(safe)
  } catch (error: unknown) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid request data",
          details: error.issues,
          timestamp: new Date().toISOString(),
        },
      }, { status: 400 })
    }

    console.error("V1 Orders GET error:", error)
    if (error instanceof Error) {
      console.error("Stack trace:", error.stack)
      console.error("Error type:", error.constructor.name)
      console.error("Error message:", error.message)
    }

    // Handle ApiError instances with proper status codes
    if (error instanceof Error && error.constructor.name === 'ApiError') {
      const apiError = error as ApiErrorLike;
      return NextResponse.json({
        success: false,
        error: {
          code: apiError.code || "INTERNAL_ERROR",
          message: apiError.message,
          timestamp: new Date().toISOString(),
        },
      }, { status: apiError.statusCode || 500 })
    }

    return NextResponse.json({
      success: false,
      error: {
        code: "INTERNAL_ERROR",
        message: "Failed to fetch orders",
        details: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString(),
      },
    }, { status: 500 })
  }
}

// POST /api/v1/orders - Create order
export async function POST(request: NextRequest) {
  try {
    const user = await getCurrentUser(request)
    requireSeller(user)

    const body = await request.json()

    // Validate input using external ID schema
    const validatedData = CreateOrderSchema.parse(body)

    // Translate external IDs to internal CUIDs
    const command = {
      sellerId: validatedData.sellerId,
      customerId: validatedData.customerId,
      paymentType: validatedData.paymentType,
      paymentStatus: "PENDING",
      notes: validatedData.notes,
      items: validatedData.items.map(item => ({
        productId: item.productId,
        quantity: item.quantity,
      })),
    }

    const order = await createV1Order(command, user.sellerId!)

    // Build V1 contract response: { order: {...} }
    const orderResponse = {
      id: order.id,
      sellerId: order.sellerId,
      publicOrderNumber: order.publicOrderNumber,
      status: order.status,
      paymentStatus: order.paymentStatus,
      paymentType: order.paymentType,
      subtotalMinor: order.subtotalMinor,
      deliveryFeeMinor: order.deliveryFeeMinor,
      totalMinor: order.totalMinor,
      currency: order.currency,
      notes: order.notes,
      createdAt: order.createdAt.toISOString(),
      updatedAt: order.updatedAt.toISOString(),
      customer: {
        id: order.customer.id,
        name: order.customer.name,
        phone: order.customer.phone,
        addressText: order.customer.addressText,
      },
      items: order.orderItems.map((item) => ({
        id: item.id,
        productId: item.productId,
        productNameSnapshot: item.productNameSnapshot,
        unitPriceMinor: item.unitPriceMinor,
        quantity: item.quantity,
        lineTotalMinor: item.lineTotalMinor,
      })),
    }

    // Enforce V1 response contract
    const safe = OrderResponseSchema.parse(orderResponse)

    const responseBody = OrderCreateResponseSchema.parse({
      success: true,
      data: {
        order: safe,
      },
    })

    return NextResponse.json(responseBody)
  } catch (error: unknown) {
    if (error instanceof z.ZodError) {
      console.error("ZOD CONTRACT ERROR:", error.issues)
      return NextResponse.json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid input data",
          details: error.issues,
          timestamp: new Date().toISOString(),
        },
      }, { status: 400 })
    }

    console.error("V1 Orders POST error:", error);
    if (error instanceof Error) {
      console.error("message:", error.message);
      console.error("stack:", error.stack);
    }

    return NextResponse.json({
      success: false,
      error: {
        code: "INTERNAL_ERROR",
        message: "Failed to create order",
        timestamp: new Date().toISOString(),
      },
    }, { status: 500 })
  }
}
