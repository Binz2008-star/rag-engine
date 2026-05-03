import { z } from 'zod'

// === V1 ORDER DTO SCHEMAS ===
// These define the exact shape of data crossing the API boundary

export const OrderItemDtoSchema = z.object({
  id: z.string(),
  productId: z.string(),
  productNameSnapshot: z.string(),
  unitPriceMinor: z.number(),
  quantity: z.number(),
  lineTotalMinor: z.number(),
})

export const OrderDtoSchema = z.object({
  id: z.string(),
  sellerId: z.string(),
  publicOrderNumber: z.string(),
  status: z.string(),
  paymentStatus: z.string(),
  paymentType: z.string(),
  subtotalMinor: z.number(),
  deliveryFeeMinor: z.number(),
  totalMinor: z.number(),
  currency: z.string(),
  notes: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
  customer: z.object({
    id: z.string(),
    name: z.string(),
    phone: z.string(),
    addressText: z.string().nullable(),
  }),
  items: z.array(OrderItemDtoSchema),
})

// V1 Response envelope schemas
export const V1OrderResponseSchema = z.object({
  order: OrderDtoSchema,
})

export const V1OrderListResponseSchema = z.object({
  orders: z.array(OrderDtoSchema),
  pagination: z.object({
    page: z.number(),
    limit: z.number(),
    total: z.number(),
    totalPages: z.number(),
    hasNext: z.boolean(),
    hasPrev: z.boolean(),
  }),
})

// === TYPE EXPORTS ===

export type OrderItemDto = z.infer<typeof OrderItemDtoSchema>
export type OrderDto = z.infer<typeof OrderDtoSchema>
export type V1OrderResponse = z.infer<typeof V1OrderResponseSchema>
export type V1OrderListResponse = z.infer<typeof V1OrderListResponseSchema>

// === INPUT TYPE FOR MAPPER ===

export type OrderWithRelations = {
  id: string
  sellerId: string
  publicOrderNumber: string
  status: string
  paymentStatus: string
  paymentType: string
  subtotalMinor: number
  deliveryFeeMinor: number
  totalMinor: number
  currency: string | null
  notes: string | null
  createdAt: Date
  updatedAt: Date
  customer: {
    id: string
    name: string
    phone: string
    addressText: string | null
  }
  orderItems: Array<{
    id: string
    productId: string
    productNameSnapshot: string
    unitPriceMinor: number
    quantity: number
    lineTotalMinor: number
  }>
}

export type OrderListWithRelations = {
  orders: OrderWithRelations[]
  pagination: {
    page: number
    limit: number
    total: number
    totalPages: number
    hasNext: boolean
    hasPrev: boolean
  }
}
