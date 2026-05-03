/**
 * ORDER STATE MACHINE — Global, Immutable
 * Mirrors the backend state machine exactly.
 * UI must ONLY show transitions that are valid per this map.
 */

export type OrderStatus =
  | "PENDING"
  | "CONFIRMED"
  | "PREPARING"
  | "READY_FOR_PICKUP"
  | "OUT_FOR_DELIVERY"
  | "DELIVERED"
  | "FAILED_DELIVERY"
  | "CANCELLED";

export type PaymentStatus = "PENDING" | "PAID" | "FAILED" | "REFUNDED";

/** Strict transition map — only valid next states per current state */
export const ALLOWED_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  PENDING:           ["CONFIRMED", "CANCELLED"],
  CONFIRMED:         ["PREPARING", "CANCELLED"],
  PREPARING:         ["READY_FOR_PICKUP", "CANCELLED"],
  READY_FOR_PICKUP:  ["OUT_FOR_DELIVERY", "CANCELLED"],
  OUT_FOR_DELIVERY:  ["DELIVERED", "FAILED_DELIVERY"],
  FAILED_DELIVERY:   ["OUT_FOR_DELIVERY", "CANCELLED"],   // retry or cancel
  DELIVERED:         [],  // terminal
  CANCELLED:         [],  // terminal
};

/** Terminal states — no further transitions possible */
export const TERMINAL_STATES: OrderStatus[] = ["DELIVERED", "CANCELLED"];

/** Ordered flow for the state machine visualizer (happy path) */
export const STATE_FLOW: OrderStatus[] = [
  "PENDING",
  "CONFIRMED",
  "PREPARING",
  "READY_FOR_PICKUP",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
];

/** All states including off-path */
export const ALL_STATES: OrderStatus[] = [
  "PENDING",
  "CONFIRMED",
  "PREPARING",
  "READY_FOR_PICKUP",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "FAILED_DELIVERY",
  "CANCELLED",
];

/** Visual config — global and immutable */
export const STATUS_CONFIG: Record<OrderStatus, {
  label: string;
  className: string;      // badge bg + text
  dotClass: string;       // status dot color
  nodeActive: string;     // state machine node — active
  nodePast: string;       // state machine node — past
  nodeFuture: string;     // state machine node — future/disabled
}> = {
  PENDING: {
    label: "Pending",
    className: "bg-slate-100 text-slate-700",
    dotClass: "bg-slate-400",
    nodeActive: "bg-slate-700 text-white border-slate-700",
    nodePast: "bg-slate-200 text-slate-400 border-slate-200",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  CONFIRMED: {
    label: "Confirmed",
    className: "bg-indigo-100 text-indigo-700",
    dotClass: "bg-indigo-500",
    nodeActive: "bg-indigo-600 text-white border-indigo-600",
    nodePast: "bg-indigo-100 text-indigo-300 border-indigo-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  PREPARING: {
    label: "Preparing",
    className: "bg-amber-100 text-amber-700",
    dotClass: "bg-amber-500",
    nodeActive: "bg-amber-500 text-white border-amber-500",
    nodePast: "bg-amber-100 text-amber-300 border-amber-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  READY_FOR_PICKUP: {
    label: "Ready for Pickup",
    className: "bg-violet-100 text-violet-700",
    dotClass: "bg-violet-500",
    nodeActive: "bg-violet-600 text-white border-violet-600",
    nodePast: "bg-violet-100 text-violet-300 border-violet-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  OUT_FOR_DELIVERY: {
    label: "Out for Delivery",
    className: "bg-orange-100 text-orange-700",
    dotClass: "bg-orange-500",
    nodeActive: "bg-orange-500 text-white border-orange-500",
    nodePast: "bg-orange-100 text-orange-300 border-orange-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  DELIVERED: {
    label: "Delivered",
    className: "bg-emerald-100 text-emerald-700",
    dotClass: "bg-emerald-500",
    nodeActive: "bg-emerald-600 text-white border-emerald-600",
    nodePast: "bg-emerald-100 text-emerald-300 border-emerald-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  FAILED_DELIVERY: {
    label: "Failed Delivery",
    className: "bg-red-100 text-red-700",
    dotClass: "bg-red-500",
    nodeActive: "bg-red-600 text-white border-red-600",
    nodePast: "bg-red-100 text-red-300 border-red-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
  CANCELLED: {
    label: "Cancelled",
    className: "bg-gray-100 text-gray-500",
    dotClass: "bg-gray-400",
    nodeActive: "bg-gray-600 text-white border-gray-600",
    nodePast: "bg-gray-100 text-gray-300 border-gray-100",
    nodeFuture: "bg-white text-slate-300 border-slate-200",
  },
};

export const PAYMENT_STATUS_CONFIG: Record<PaymentStatus, { label: string; className: string }> = {
  PENDING:  { label: "Pending",  className: "bg-slate-100 text-slate-600" },
  PAID:     { label: "Paid",     className: "bg-emerald-100 text-emerald-700" },
  FAILED:   { label: "Failed",   className: "bg-red-100 text-red-700" },
  REFUNDED: { label: "Refunded", className: "bg-violet-100 text-violet-700" },
};

/** Get the position of a state in the happy-path flow (for past/future determination) */
export function getFlowIndex(status: OrderStatus): number {
  return STATE_FLOW.indexOf(status);
}

/** Determine if a state is "past" relative to current */
export function isStatePast(state: OrderStatus, current: OrderStatus): boolean {
  const stateIdx = getFlowIndex(state);
  const currentIdx = getFlowIndex(current);
  if (stateIdx === -1 || currentIdx === -1) return false;
  return stateIdx < currentIdx;
}

/** Determine if a state is "future" relative to current */
export function isStateFuture(state: OrderStatus, current: OrderStatus): boolean {
  const stateIdx = getFlowIndex(state);
  const currentIdx = getFlowIndex(current);
  if (stateIdx === -1 || currentIdx === -1) return false;
  return stateIdx > currentIdx;
}
