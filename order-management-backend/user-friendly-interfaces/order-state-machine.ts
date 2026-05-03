/**
 * SHARED CONTRACT — Order State Machine
 * ======================================
 * Single source of truth for order state transitions.
 * Used by:
 *   - Frontend (UI enforcement)
 *   - Backend (API enforcement)
 *   - Contract tests (validation)
 *
 * ⚠️  NEVER duplicate this logic. Import from here.
 *
 * Backend guard (NestJS example):
 *   import { ORDER_TRANSITIONS } from '@shared/contracts/order-state-machine';
 *   if (!ORDER_TRANSITIONS[currentStatus].includes(nextStatus)) {
 *     throw new BadRequestException({
 *       code: 'INVALID_TRANSITION',
 *       message: `Cannot move from ${currentStatus} to ${nextStatus}`,
 *     });
 *   }
 */

export const ORDER_TRANSITIONS = {
  PENDING:           ["CONFIRMED", "CANCELLED"],
  CONFIRMED:         ["PREPARING", "CANCELLED"],
  PREPARING:         ["READY_FOR_PICKUP", "CANCELLED"],
  READY_FOR_PICKUP:  ["OUT_FOR_DELIVERY", "CANCELLED"],
  OUT_FOR_DELIVERY:  ["DELIVERED", "FAILED_DELIVERY"],
  FAILED_DELIVERY:   ["OUT_FOR_DELIVERY", "CANCELLED"],   // retry or cancel
  DELIVERED:         [],   // terminal — success
  CANCELLED:         [],   // terminal — cancelled
} as const;

export type OrderStatus = keyof typeof ORDER_TRANSITIONS;
export type AllowedNext<S extends OrderStatus> = typeof ORDER_TRANSITIONS[S][number];

/** Returns only valid next states for a given current status */
export function getAllowedTransitions(status: OrderStatus): readonly OrderStatus[] {
  return ORDER_TRANSITIONS[status] as readonly OrderStatus[];
}

/** Returns true if the transition from → to is valid */
export function isValidTransition(from: OrderStatus, to: OrderStatus): boolean {
  return (ORDER_TRANSITIONS[from] as readonly string[]).includes(to);
}

/** Terminal states — no further transitions possible */
export const TERMINAL_STATES: readonly OrderStatus[] = ["DELIVERED", "CANCELLED"] as const;

export function isTerminalState(status: OrderStatus): boolean {
  return TERMINAL_STATES.includes(status);
}

/** Happy-path flow for visualizer */
export const PRIMARY_FLOW: readonly OrderStatus[] = [
  "PENDING",
  "CONFIRMED",
  "PREPARING",
  "READY_FOR_PICKUP",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
] as const;
