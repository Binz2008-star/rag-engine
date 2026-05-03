/**
 * SINGLE SOURCE OF TRUTH — ORDER STATUS
 *
 * This is the ONLY place where order status values and transitions are defined.
 * All backend services, API routes, schemas, and tests MUST import from here.
 *
 * Do NOT duplicate these values anywhere else in the codebase.
 */

// ─── Canonical Status Enum ────────────────────────────────────────────────────

export enum OrderStatus {
  PENDING           = 'PENDING',
  CONFIRMED         = 'CONFIRMED',
  PREPARING         = 'PREPARING',
  READY_FOR_PICKUP  = 'READY_FOR_PICKUP',
  OUT_FOR_DELIVERY  = 'OUT_FOR_DELIVERY',
  DELIVERED         = 'DELIVERED',
  FAILED_DELIVERY   = 'FAILED_DELIVERY',
  CANCELLED         = 'CANCELLED',
}

// Ordered list for display/iteration purposes
export const ORDER_STATUS_LIST = [
  OrderStatus.PENDING,
  OrderStatus.CONFIRMED,
  OrderStatus.PREPARING,
  OrderStatus.READY_FOR_PICKUP,
  OrderStatus.OUT_FOR_DELIVERY,
  OrderStatus.DELIVERED,
  OrderStatus.FAILED_DELIVERY,
  OrderStatus.CANCELLED,
] as const

// Zod-compatible tuple for schema validation
export const ORDER_STATUS_VALUES = [
  'PENDING',
  'CONFIRMED',
  'PREPARING',
  'READY_FOR_PICKUP',
  'OUT_FOR_DELIVERY',
  'DELIVERED',
  'FAILED_DELIVERY',
  'CANCELLED',
] as const

export type OrderStatusValue = typeof ORDER_STATUS_VALUES[number]

// ─── Canonical Transition Map ─────────────────────────────────────────────────

export const ORDER_STATUS_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  [OrderStatus.PENDING]:           [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
  [OrderStatus.CONFIRMED]:         [OrderStatus.PREPARING, OrderStatus.CANCELLED],
  [OrderStatus.PREPARING]:         [OrderStatus.READY_FOR_PICKUP, OrderStatus.CANCELLED],
  [OrderStatus.READY_FOR_PICKUP]:  [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED],
  [OrderStatus.OUT_FOR_DELIVERY]:  [OrderStatus.DELIVERED, OrderStatus.FAILED_DELIVERY],
  [OrderStatus.FAILED_DELIVERY]:   [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED],
  [OrderStatus.DELIVERED]:         [], // Terminal
  [OrderStatus.CANCELLED]:         [], // Terminal
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function isValidOrderTransition(from: OrderStatus, to: OrderStatus): boolean {
  return ORDER_STATUS_TRANSITIONS[from]?.includes(to) ?? false
}

export function isTerminalOrderStatus(status: OrderStatus): boolean {
  return ORDER_STATUS_TRANSITIONS[status].length === 0
}

export function getValidNextStates(status: OrderStatus): OrderStatus[] {
  return ORDER_STATUS_TRANSITIONS[status] ?? []
}

export function isOrderStatus(value: string): value is OrderStatus {
  return ORDER_STATUS_VALUES.includes(value as OrderStatusValue)
}

// ─── Error ────────────────────────────────────────────────────────────────────

export class OrderTransitionError extends Error {
  public readonly from: OrderStatus
  public readonly to: OrderStatus

  constructor(from: OrderStatus, to: OrderStatus) {
    super(`Invalid order transition: ${from} → ${to}`)
    this.name = 'OrderTransitionError'
    this.from = from
    this.to = to
  }
}
