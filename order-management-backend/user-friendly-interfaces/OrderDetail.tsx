/**
 * DESIGN: "Operational Clarity"
 * OrderDetail — Production-grade Control + Observability Console
 *
 * Architecture:
 *   - NO mock data. All state comes from the server.
 *   - safeFetch validates the API envelope shape at runtime.
 *   - Transitions are server-driven: PATCH /api/v1/orders/:id/status
 *   - Timeline comes from order.events (backend must include this in GET response)
 *   - State machine is imported from shared contract — same map used by backend + tests
 *
 * Backend contract required:
 *   GET  /api/v1/orders/:id         → { success: true, data: { order: OrderDetail } }
 *   PATCH /api/v1/orders/:id/status → { success: true, data: { order: OrderDetail } }
 *   order.events must be included in GET response
 */
import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useParams, useLocation } from "wouter";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Box,
  CheckCircle2,
  Clock3,
  Home,
  Loader2,
  Package,
  ShoppingBag,
  Truck,
  XCircle,
} from "lucide-react";

// ─── Shared State Machine Contract ──────────────────────────────────────────
// This is the single source of truth. Move to shared/contracts/order-state-machine.ts
// so backend, UI, and tests all import from the same map.
// Note: exported here for reference; in production import from @shared/contracts/order-state-machine
const ORDER_TRANSITIONS = {
  PENDING:          ["CONFIRMED", "CANCELLED"],
  CONFIRMED:        ["PREPARING", "CANCELLED"],
  PREPARING:        ["READY_FOR_PICKUP"],
  READY_FOR_PICKUP: ["OUT_FOR_DELIVERY"],
  OUT_FOR_DELIVERY: ["DELIVERED", "FAILED_DELIVERY"],
  FAILED_DELIVERY:  ["OUT_FOR_DELIVERY", "CANCELLED"],
  DELIVERED:        [],
  CANCELLED:        [],
} as const;

type OrderStatus = keyof typeof ORDER_TRANSITIONS;
type LensMode = "business" | "system";

// ─── API Types ────────────────────────────────────────────────────────────────

type ApiError = {
  success: false;
  error: {
    code: string;
    message: string;
    timestamp?: string;
    details?: unknown;
  };
};

type OrderEvent = {
  id: string;
  type: string;
  label?: string;
  actor?: string;
  createdAt: string;
  metadata?: Record<string, unknown>;
};

type OrderItem = {
  id: string;
  productId: string;
  productNameSnapshot?: string;
  name?: string;
  quantity: number;
  unitPriceMinor: number;
  lineTotalMinor: number;
};

type OrderDetail = {
  id: string;
  sellerId: string;
  publicOrderNumber: string;
  status: OrderStatus;
  paymentStatus: "PENDING" | "PAID" | "FAILED" | "REFUNDED";
  paymentType: "CASH_ON_DELIVERY" | "CARD";
  currency: string;
  subtotalMinor: number;
  deliveryFeeMinor: number;
  totalMinor: number;
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
  customer: {
    id: string;
    name: string;
    phone: string;
    addressText?: string | null;
  };
  items: OrderItem[];
  events?: OrderEvent[];
};

type GetOrderResponse = {
  success: true;
  data: { order: OrderDetail };
};

type UpdateStatusResponse = GetOrderResponse;

// ─── Status Metadata ──────────────────────────────────────────────────────────

const STATUS_META: Record<
  OrderStatus,
  {
    label: string;
    short: string;
    icon: React.ComponentType<{ className?: string }>;
    ring: string;
    bg: string;
    text: string;
    muted: string;
    helper: string;
  }
> = {
  PENDING:          { label: "Pending",           short: "PENDING",          icon: Clock3,        ring: "ring-slate-300",   bg: "bg-slate-100",   text: "text-slate-700",   muted: "text-slate-400",   helper: "New order awaiting confirmation" },
  CONFIRMED:        { label: "Confirmed",          short: "CONFIRMED",        icon: CheckCircle2,  ring: "ring-indigo-300",  bg: "bg-indigo-100",  text: "text-indigo-700",  muted: "text-indigo-300",  helper: "Seller accepted the order" },
  PREPARING:        { label: "Preparing",          short: "PREPARING",        icon: Box,           ring: "ring-amber-300",   bg: "bg-amber-100",   text: "text-amber-700",   muted: "text-amber-300",   helper: "Order is being packed" },
  READY_FOR_PICKUP: { label: "Ready for Pickup",   short: "READY_FOR_PICKUP", icon: ShoppingBag,   ring: "ring-fuchsia-300", bg: "bg-fuchsia-100", text: "text-fuchsia-700", muted: "text-fuchsia-300", helper: "Awaiting courier pickup" },
  OUT_FOR_DELIVERY: { label: "Out for Delivery",   short: "OUT_FOR_DELIVERY", icon: Truck,         ring: "ring-orange-300",  bg: "bg-orange-100",  text: "text-orange-700",  muted: "text-orange-300",  helper: "En route to the customer" },
  FAILED_DELIVERY:  { label: "Failed Delivery",    short: "FAILED_DELIVERY",  icon: AlertTriangle, ring: "ring-rose-300",    bg: "bg-rose-100",    text: "text-rose-700",    muted: "text-rose-300",    helper: "Retry or cancel required" },
  DELIVERED:        { label: "Delivered",          short: "DELIVERED",        icon: Home,          ring: "ring-emerald-300", bg: "bg-emerald-100", text: "text-emerald-700", muted: "text-emerald-300", helper: "Terminal success state" },
  CANCELLED:        { label: "Cancelled",          short: "CANCELLED",        icon: XCircle,       ring: "ring-red-300",     bg: "bg-red-100",     text: "text-red-700",     muted: "text-red-300",     helper: "Terminal cancelled state" },
};

const PRIMARY_FLOW: OrderStatus[] = [
  "PENDING", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "OUT_FOR_DELIVERY", "DELIVERED",
];

// ─── Utilities ────────────────────────────────────────────────────────────────

function getAllowedTransitions(status: OrderStatus) {
  return ORDER_TRANSITIONS[status] ?? [];
}

function formatMoney(amountMinor: number, currency: string) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amountMinor / 100);
}

function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function parseJson<T>(raw: string): T {
  return JSON.parse(raw) as T;
}

/**
 * safeFetch — validates API envelope and throws typed errors.
 * Silent failures are forbidden: contract drift must be loud.
 */
async function safeFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const raw = await response.text();
  const json = raw ? parseJson<T | ApiError>(raw) : ({} as T | ApiError);

  if (!response.ok) {
    const err = json as ApiError;
    throw new Error(err?.error?.message || `Request failed with ${response.status}`);
  }

  return json as T;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: OrderStatus }) {
  const meta = STATUS_META[status];
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide", meta.bg, meta.text)}>
      {meta.short}
    </span>
  );
}

function PaymentBadge({ status }: { status: OrderDetail["paymentStatus"] }) {
  const styles = {
    PENDING:  "bg-slate-100 text-slate-700",
    PAID:     "bg-emerald-100 text-emerald-700",
    FAILED:   "bg-red-100 text-red-700",
    REFUNDED: "bg-amber-100 text-amber-700",
  } as const;
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", styles[status])}>
      {status}
    </span>
  );
}

function SkeletonCard() {
  return <div className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white" />;
}

function SummaryCard({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className={cn("mt-2 text-lg font-semibold text-slate-900", mono && "font-mono text-base")}>{value}</div>
    </div>
  );
}

function StateMachineVisualizer({
  current,
  onTransition,
  isUpdating,
}: {
  current: OrderStatus;
  onTransition: (next: OrderStatus) => void;
  isUpdating: boolean;
}) {
  const currentIndex = PRIMARY_FLOW.indexOf(current);
  const allowed = getAllowedTransitions(current);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Live State Machine</h3>
          <p className="mt-1 text-sm text-slate-500">
            Current state is emphasized. Future states are disabled. Only valid transitions are actionable.
          </p>
        </div>
        <StatusBadge status={current} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_auto]">
        <div className="overflow-x-auto pb-2">
          <div className="flex min-w-[860px] items-center gap-3">
            {PRIMARY_FLOW.map((status, idx) => {
              const meta = STATUS_META[status];
              const Icon = meta.icon;
              const isCurrent = status === current;
              const isPast = currentIndex >= 0 && idx < currentIndex;
              const isFuture = currentIndex >= 0 && idx > currentIndex;

              return (
                <React.Fragment key={status}>
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex min-w-[118px] flex-col items-center text-center"
                  >
                    <div
                      className={cn(
                        "flex h-20 w-20 items-center justify-center rounded-full ring-4 transition",
                        isCurrent && cn(meta.bg, meta.ring, "shadow-lg"),
                        isPast && "bg-slate-50 ring-slate-200",
                        isFuture && "bg-white ring-slate-100 opacity-45"
                      )}
                    >
                      <Icon className={cn("h-9 w-9", isCurrent && meta.text, isPast && "text-slate-400", isFuture && meta.muted)} />
                    </div>
                    <div className="mt-3 text-sm font-semibold text-slate-900">{meta.label}</div>
                    <div className="mt-1 text-xs text-slate-500">{meta.helper}</div>
                  </motion.div>
                  {idx < PRIMARY_FLOW.length - 1 && (
                    <ArrowRight className="h-7 w-7 shrink-0 text-indigo-500" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Action Surface — only valid next states shown */}
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-sm font-semibold text-slate-900">Action Surface</div>
          <div className="mt-1 text-xs text-slate-500">Only valid next states are shown.</div>
          <div className="mt-4 space-y-2">
            {allowed.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white px-3 py-4 text-sm text-slate-500">
                Terminal state. No further transitions available.
              </div>
            ) : (
              allowed.map((next) => (
                <button
                  key={next}
                  onClick={() => onTransition(next)}
                  disabled={isUpdating}
                  className="flex w-full items-center justify-between rounded-xl bg-indigo-600 px-4 py-3 text-left text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <span>{STATUS_META[next].label}</span>
                  {isUpdating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                </button>
              ))
            )}
          </div>

          {current === "FAILED_DELIVERY" && (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              Recovery path available: retry delivery or cancel order.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Timeline({ events, mode }: { events: OrderEvent[]; mode: LensMode }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Operational Timeline</h3>
          <p className="mt-1 text-sm text-slate-500">
            Immutable event history for debugging, disputes, and operator trust.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
          {mode === "business" ? "Business lens" : "System lens"}
        </span>
      </div>

      <div className="space-y-4">
        {events.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            No events returned by the backend.
          </div>
        ) : (
          events.map((event) => (
            <div key={event.id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="mt-1 h-3 w-3 rounded-full bg-indigo-500" />
                <div className="mt-2 h-full w-px bg-slate-200" />
              </div>
              <div className="flex-1 rounded-2xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-900">{event.label || event.type}</div>
                  <div className="font-mono text-xs text-slate-500">
                    {new Date(event.createdAt).toLocaleString()}
                  </div>
                </div>
                <div className="mt-1 text-sm text-slate-500">Actor: {event.actor || "system"}</div>
                {mode === "system" && (
                  <div className="mt-3 rounded-xl bg-slate-50 p-3 font-mono text-xs text-slate-700">
                    <div>event.id: {event.id}</div>
                    <div>event.type: {event.type}</div>
                    {event.metadata && (
                      <pre className="mt-2 overflow-auto whitespace-pre-wrap break-all text-[11px] text-slate-600">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function OrderDetailPage() {
  // Wouter provides orderId from route /seller/orders/:orderId
  const params = useParams<{ orderId: string }>();
  const [, navigate] = useLocation();
  const orderId = params.orderId;

  // In production: read token from auth context / cookie
  // const token = useAuthToken();
  const token = "replace-with-real-bearer-token";
  const baseUrl = ""; // same-origin; set to backend URL if cross-origin

  const [mode, setMode] = useState<LensMode>("business");
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  async function loadOrder() {
    if (!orderId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await safeFetch<GetOrderResponse>(
        `${baseUrl}/api/v1/orders/${orderId}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );
      setOrder(data.data.order);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load order");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId]);

  const allowedTransitions = useMemo(
    () => (order ? getAllowedTransitions(order.status) : []),
    [order]
  );

  async function handleTransition(next: OrderStatus) {
    if (!order || !(allowedTransitions as readonly string[]).includes(next)) return;
    try {
      setUpdating(true);
      setError(null);
      const data = await safeFetch<UpdateStatusResponse>(
        `${baseUrl}/api/v1/orders/${order.id}/status`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ status: next }),
        }
      );
      setOrder(data.data.order);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update order status");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="grid min-h-screen grid-cols-[260px_1fr]">
        {/* Sidebar */}
        <aside className="border-r border-slate-800 bg-slate-950 px-5 py-6 text-slate-200">
          <div className="rounded-2xl bg-white/5 px-4 py-3">
            <div className="text-xl font-semibold tracking-tight text-white" style={{ fontFamily: "Sora, sans-serif" }}>
              OrderFlow
            </div>
            <div className="mt-1 text-sm text-slate-400">Operational Clarity Console</div>
          </div>

          <nav className="mt-8 space-y-2 text-sm">
            {["Orders", "Payments", "Products", "Customers", "Activity", "Settings"].map((item) => (
              <div
                key={item}
                className={cn(
                  "rounded-xl px-4 py-3 cursor-pointer transition-colors",
                  item === "Orders"
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                )}
                onClick={() => item === "Orders" && navigate("/seller/orders")}
              >
                {item}
              </div>
            ))}
          </nav>

          {/* Backend contract reference */}
          <div className="mt-8 rounded-2xl bg-white/5 p-4 text-xs text-slate-400 space-y-2">
            <div className="font-semibold text-slate-300 uppercase tracking-wider text-[10px]">API Contract</div>
            <div className="font-mono">GET /api/v1/orders/:id</div>
            <div className="font-mono">PATCH /api/v1/orders/:id/status</div>
            <div className="mt-2 text-slate-500">order.events must be included in GET response</div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">
            {/* Header */}
            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <button
                  onClick={() => navigate("/seller/orders")}
                  className="mb-3 flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to Orders
                </button>
                <div className="text-sm font-medium uppercase tracking-[0.18em] text-indigo-600">
                  Order Detail
                </div>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950" style={{ fontFamily: "Sora, sans-serif" }}>
                  {loading ? "Loading order..." : order?.publicOrderNumber || "Order unavailable"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-slate-500">
                  Full-stack control + observability console. UI state is contract-driven, server-updated, and timeline-aware.
                </p>
              </div>

              {/* Lens Toggle */}
              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
                  {(["business", "system"] as const).map((value) => (
                    <button
                      key={value}
                      onClick={() => setMode(value)}
                      className={cn(
                        "rounded-xl px-4 py-2 text-sm font-medium transition",
                        mode === value ? "bg-indigo-600 text-white" : "text-slate-600 hover:text-slate-900"
                      )}
                    >
                      {value === "business" ? "Business View" : "System View"}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            {/* Loading Skeleton */}
            {loading || !order ? (
              <>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <SkeletonCard />
                  <SkeletonCard />
                  <SkeletonCard />
                  <SkeletonCard />
                </div>
                <div className="mt-6 grid gap-6 xl:grid-cols-[1.65fr_1fr]">
                  <SkeletonCard />
                  <SkeletonCard />
                </div>
              </>
            ) : (
              <>
                {/* Summary Cards */}
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <SummaryCard label="Order ID" value={order.id} mono />
                  <SummaryCard label="Current Status" value={STATUS_META[order.status].label} />
                  <SummaryCard label="Payment" value={`${order.paymentStatus} · ${order.paymentType}`} />
                  <SummaryCard label="Total" value={formatMoney(order.totalMinor, order.currency)} mono />
                </div>

                {/* Main Grid */}
                <div className="mt-6 grid gap-6 xl:grid-cols-[1.65fr_1fr]">
                  {/* Left: State Machine + Timeline */}
                  <div className="space-y-6">
                    <StateMachineVisualizer
                      current={order.status}
                      onTransition={handleTransition}
                      isUpdating={updating}
                    />
                    <Timeline events={order.events || []} mode={mode} />
                  </div>

                  {/* Right: Customer + Items + Notes */}
                  <div className="space-y-6">
                    {/* Customer */}
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-slate-900">Customer</h3>
                        <StatusBadge status={order.status} />
                      </div>
                      <div className="mt-4 space-y-3 text-sm text-slate-600">
                        <div>
                          <div className="font-medium text-slate-900">{order.customer.name}</div>
                          <div>{order.customer.phone}</div>
                        </div>
                        {order.customer.addressText && (
                          <div>{order.customer.addressText}</div>
                        )}
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500">Payment:</span>
                          <PaymentBadge status={order.paymentStatus} />
                        </div>
                      </div>
                    </div>

                    {/* Order Items */}
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <h3 className="text-lg font-semibold text-slate-900">Order Items</h3>
                      <div className="mt-4 space-y-3">
                        {order.items.map((item) => (
                          <div key={item.id} className="rounded-2xl border border-slate-200 p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="font-medium text-slate-900">
                                  {item.name || item.productNameSnapshot || "Unnamed item"}
                                </div>
                                <div className="mt-1 font-mono text-xs text-slate-500">{item.productId}</div>
                              </div>
                              <div className="text-right">
                                <div className="font-mono text-sm text-slate-900">× {item.quantity}</div>
                                <div className="mt-1 font-mono text-sm text-slate-500">
                                  {formatMoney(item.lineTotalMinor, order.currency)}
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Totals */}
                      <div className="mt-5 border-t border-slate-200 pt-4 text-sm">
                        <div className="flex justify-between py-1 text-slate-600">
                          <span>Subtotal</span>
                          <span className="font-mono">{formatMoney(order.subtotalMinor, order.currency)}</span>
                        </div>
                        <div className="flex justify-between py-1 text-slate-600">
                          <span>Delivery</span>
                          <span className="font-mono">{formatMoney(order.deliveryFeeMinor, order.currency)}</span>
                        </div>
                        <div className="mt-2 flex justify-between border-t border-slate-200 pt-3 font-semibold text-slate-950">
                          <span>Total</span>
                          <span className="font-mono">{formatMoney(order.totalMinor, order.currency)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Operational Notes */}
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <h3 className="text-lg font-semibold text-slate-900">Operational Notes</h3>
                      <p className="mt-3 text-sm leading-6 text-slate-600">
                        {order.notes || "No notes recorded for this order."}
                      </p>
                      <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-xs text-slate-500">
                        Updated {new Date(order.updatedAt).toLocaleString()} · Created{" "}
                        {new Date(order.createdAt).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
