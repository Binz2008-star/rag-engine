import {
  OrderDto,
  OrderDtoSchema,
  OrderListWithRelations,
  OrderWithRelations,
  V1OrderListResponse,
  V1OrderListResponseSchema,
  V1OrderResponse,
  V1OrderResponseSchema
} from '@/shared/schemas/v1-order-dto'

/**
 * Clean V1 API Contract Mapper
 *
 * Enforces exact V1 response shape with proper typing.
 * No 'any' types, no duplication, clean boundaries.
 */

function toV1OrderDto(order: OrderWithRelations): OrderDto {
  return OrderDtoSchema.parse({
    id: order.id,
    sellerId: order.sellerId,
    publicOrderNumber: order.publicOrderNumber,
    status: order.status,
    paymentStatus: order.paymentStatus,
    paymentType: order.paymentType,
    subtotalMinor: order.subtotalMinor,
    deliveryFeeMinor: order.deliveryFeeMinor,
    totalMinor: order.totalMinor,
    currency: order.currency ?? 'USD',
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
  })
}

export function toV1OrderResponse(order: OrderWithRelations): V1OrderResponse {
  return V1OrderResponseSchema.parse({
    order: toV1OrderDto(order),
  })
}

export function toV1OrderListResponse(data: OrderListWithRelations): V1OrderListResponse {
  return V1OrderListResponseSchema.parse({
    orders: data.orders.map(order => toV1OrderDto(order)),
    pagination: data.pagination,
  })
}

export function toV1ErrorResponse(message: string): { error: string } {
  return { error: message }
}
