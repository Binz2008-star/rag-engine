import { OrderResponse, OrderResponseSchema } from '@/shared/schemas/order-response'
import { Prisma } from '@prisma/client'

// Explicit mapper to isolate API contract from internal database model
export class OrderResponseMapper {
  static toApiResponse(order: any): OrderResponse {
    // Validate and transform according to contract schema
    const response = {
      id: order.id,
      sellerId: order.sellerId,
      publicOrderNumber: order.publicOrderNumber,
      status: order.status,
      paymentStatus: order.paymentStatus,
      paymentType: order.paymentType,
      subtotalMinor: order.subtotalMinor,
      deliveryFeeMinor: order.deliveryFeeMinor,
      totalMinor: order.totalMinor,
      currency: order.currency || 'USD', // Default to USD if not set
      notes: order.notes,
      createdAt: order.createdAt.toISOString(),
      updatedAt: order.updatedAt.toISOString(),
      customer: {
        id: order.customer.id,
        name: order.customer.name,
        phone: order.customer.phone,
        addressText: order.customer.addressText,
      },
      items: order.orderItems.map((item: any) => ({
        id: item.id,
        productId: item.productId,
        productNameSnapshot: item.productNameSnapshot,
        unitPriceMinor: item.unitPriceMinor,
        quantity: item.quantity,
        lineTotalMinor: item.lineTotalMinor,
      })),
    }

    // Enforce contract schema validation
    return OrderResponseSchema.parse(response)
  }

  static toOrderListResponse(orders: any[], pagination: any) {
    return {
      success: true as const,
      data: {
        orders: orders.map(order => this.toApiResponse(order)),
        pagination: {
          page: pagination.page,
          limit: pagination.limit,
          total: pagination.total,
          totalPages: pagination.totalPages,
          hasNext: pagination.hasNext,
          hasPrev: pagination.hasPrev,
        },
      },
    }
  }

  static toOrderCreateResponse(order: any) {
    return {
      success: true as const,
      data: {
        order: this.toApiResponse(order),
      },
    }
  }

  static toOrderUpdateResponse(order: any) {
    return {
      success: true as const,
      data: {
        order: this.toApiResponse(order),
      },
    }
  }

  static toErrorResponse(code: string, message: string, statusCode: number, details?: any) {
    return {
      success: false as const,
      error: {
        code,
        message,
        ...(details && { details }),
        timestamp: new Date().toISOString(),
      },
    }
  }
}
