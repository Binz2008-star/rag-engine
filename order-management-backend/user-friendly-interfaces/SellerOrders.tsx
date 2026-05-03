/**
 * DESIGN: "Operational Clarity"
 * Orders page — full order management with:
 * - Constrained status transitions (state machine enforced)
 * - Order timeline (vertical, timestamped, actor visible)
 * - Operational Lens toggle (Business / System view)
 * - Confirmation dialogs on all state transitions
 * - Skeleton loaders
 */
import { useState } from "react";
import { useLocation } from "wouter";
import {
  Search, Filter, ChevronRight, Clock, CheckCircle2, XCircle,
  Truck, Package, AlertCircle, Eye, RefreshCw, CreditCard,
  MoreHorizontal, X, ChevronDown, Layers, Code2, ArrowRight, ExternalLink
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import SellerLayout from "@/components/SellerLayout";

// ─── Global, immutable status config ───────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; className: string; dot: string }> = {
  PENDING:           { label: "Pending",          className: "bg-slate-100 text-slate-700",   dot: "bg-slate-400" },
  CONFIRMED:         { label: "Confirmed",         className: "bg-indigo-100 text-indigo-700", dot: "bg-indigo-500" },
  PREPARING:         { label: "Preparing",         className: "bg-amber-100 text-amber-700",   dot: "bg-amber-500" },
  READY_FOR_PICKUP:  { label: "Ready for Pickup",  className: "bg-violet-100 text-violet-700", dot: "bg-violet-500" },
  OUT_FOR_DELIVERY:  { label: "Out for Delivery",  className: "bg-orange-100 text-orange-700", dot: "bg-orange-500" },
  DELIVERED:         { label: "Delivered",         className: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500" },
  FAILED_DELIVERY:   { label: "Failed Delivery",   className: "bg-red-100 text-red-700",       dot: "bg-red-500" },
  CANCELLED:         { label: "Cancelled",         className: "bg-gray-100 text-gray-500",     dot: "bg-gray-400" },
};

// State machine — mirrors backend exactly
const VALID_TRANSITIONS: Record<string, string[]> = {
  PENDING:           ["CONFIRMED", "CANCELLED"],
  CONFIRMED:         ["PREPARING", "CANCELLED"],
  PREPARING:         ["READY_FOR_PICKUP", "CANCELLED"],
  READY_FOR_PICKUP:  ["OUT_FOR_DELIVERY", "CANCELLED"],
  OUT_FOR_DELIVERY:  ["DELIVERED", "FAILED_DELIVERY"],
  FAILED_DELIVERY:   ["OUT_FOR_DELIVERY", "CANCELLED"],
  DELIVERED:         [],
  CANCELLED:         [],
};

const PAYMENT_STATUS: Record<string, { label: string; className: string }> = {
  PENDING:   { label: "Pending",   className: "bg-slate-100 text-slate-600" },
  PAID:      { label: "Paid",      className: "bg-emerald-100 text-emerald-700" },
  FAILED:    { label: "Failed",    className: "bg-red-100 text-red-700" },
  REFUNDED:  { label: "Refunded",  className: "bg-violet-100 text-violet-700" },
};

interface Order {
  id: string;
  publicOrderNumber: string;
  customer: string;
  phone: string;
  amount: number;
  currency: string;
  status: string;
  paymentStatus: string;
  paymentType: string;
  items: { name: string; qty: number; price: number }[];
  createdAt: string;
  updatedAt: string;
  notes?: string;
  events: { type: string; actor: string; time: string; payload?: string }[];
}

const MOCK_ORDERS: Order[] = [
  {
    id: "clx1a2b3c",
    publicOrderNumber: "ORD-2847",
    customer: "Ahmed Al-Rashidi",
    phone: "+966501234567",
    amount: 12400,
    currency: "USD",
    status: "PENDING",
    paymentStatus: "PENDING",
    paymentType: "CASH_ON_DELIVERY",
    items: [
      { name: "Wireless Phone Charger", qty: 2, price: 2999 },
      { name: "USB-C Cable Set",        qty: 1, price: 2499 },
    ],
    createdAt: "2026-04-09T06:02:00Z",
    updatedAt: "2026-04-09T06:02:00Z",
    notes: "Please deliver after 5 PM",
    events: [
      { type: "ORDER_CREATED",   actor: "customer",       time: "06:02:00", payload: '{"source":"public_api"}' },
      { type: "PAYMENT_PENDING", actor: "system",         time: "06:02:01", payload: '{"provider":"cod"}' },
    ],
  },
  {
    id: "clx1a2b3d",
    publicOrderNumber: "ORD-2846",
    customer: "Sara Mohammed",
    phone: "+966509876543",
    amount: 6750,
    currency: "USD",
    status: "CONFIRMED",
    paymentStatus: "PAID",
    paymentType: "STRIPE",
    items: [{ name: "Bluetooth Earbuds Pro", qty: 1, price: 6750 }],
    createdAt: "2026-04-09T05:44:00Z",
    updatedAt: "2026-04-09T05:50:00Z",
    events: [
      { type: "ORDER_CREATED",     actor: "customer",   time: "05:44:00", payload: '{"source":"public_api"}' },
      { type: "PAYMENT_INITIATED", actor: "system",     time: "05:44:02", payload: '{"provider":"stripe","amount":6750}' },
      { type: "PAYMENT_CONFIRMED", actor: "stripe",     time: "05:44:08", payload: '{"reference":"pi_3Qx...","status":"succeeded"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR",  time: "05:50:00", payload: '{"from":"PENDING","to":"CONFIRMED"}' },
    ],
  },
  {
    id: "clx1a2b3e",
    publicOrderNumber: "ORD-2845",
    customer: "Khalid Hassan",
    phone: "+966555123456",
    amount: 21000,
    currency: "USD",
    status: "PREPARING",
    paymentStatus: "PAID",
    paymentType: "STRIPE",
    items: [
      { name: "Wireless Mouse",     qty: 2, price: 4999 },
      { name: "Mechanical Keyboard",qty: 1, price: 11999 },
    ],
    createdAt: "2026-04-09T05:00:00Z",
    updatedAt: "2026-04-09T05:30:00Z",
    events: [
      { type: "ORDER_CREATED",     actor: "customer",  time: "05:00:00", payload: '{"source":"public_api"}' },
      { type: "PAYMENT_CONFIRMED", actor: "stripe",    time: "05:00:05", payload: '{"reference":"pi_3Qy..."}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "05:15:00", payload: '{"from":"PENDING","to":"CONFIRMED"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "05:30:00", payload: '{"from":"CONFIRMED","to":"PREPARING"}' },
    ],
  },
  {
    id: "clx1a2b3f",
    publicOrderNumber: "ORD-2844",
    customer: "Fatima Al-Zahra",
    phone: "+966503456789",
    amount: 8999,
    currency: "USD",
    status: "OUT_FOR_DELIVERY",
    paymentStatus: "PAID",
    paymentType: "STRIPE",
    items: [{ name: "Smart Watch Band", qty: 1, price: 8999 }],
    createdAt: "2026-04-09T03:00:00Z",
    updatedAt: "2026-04-09T04:45:00Z",
    events: [
      { type: "ORDER_CREATED",     actor: "customer",  time: "03:00:00", payload: '{"source":"public_api"}' },
      { type: "PAYMENT_CONFIRMED", actor: "stripe",    time: "03:00:04", payload: '{"reference":"pi_3Qz..."}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "03:20:00", payload: '{"from":"PENDING","to":"CONFIRMED"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "04:00:00", payload: '{"from":"CONFIRMED","to":"PREPARING"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "04:30:00", payload: '{"from":"PREPARING","to":"READY_FOR_PICKUP"}' },
      { type: "STATUS_CHANGED",    actor: "system",    time: "04:45:00", payload: '{"from":"READY_FOR_PICKUP","to":"OUT_FOR_DELIVERY"}' },
    ],
  },
  {
    id: "clx1a2b3g",
    publicOrderNumber: "ORD-2843",
    customer: "Omar Nasser",
    phone: "+966507654321",
    amount: 4500,
    currency: "USD",
    status: "DELIVERED",
    paymentStatus: "PAID",
    paymentType: "CASH_ON_DELIVERY",
    items: [{ name: "Phone Case Premium", qty: 1, price: 4500 }],
    createdAt: "2026-04-09T01:00:00Z",
    updatedAt: "2026-04-09T03:30:00Z",
    events: [
      { type: "ORDER_CREATED",     actor: "customer",  time: "01:00:00", payload: '{"source":"public_api"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "01:10:00", payload: '{"from":"PENDING","to":"CONFIRMED"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "01:45:00", payload: '{"from":"CONFIRMED","to":"PREPARING"}' },
      { type: "STATUS_CHANGED",    actor: "seller:AR", time: "02:30:00", payload: '{"from":"PREPARING","to":"READY_FOR_PICKUP"}' },
      { type: "STATUS_CHANGED",    actor: "system",    time: "02:45:00", payload: '{"from":"READY_FOR_PICKUP","to":"OUT_FOR_DELIVERY"}' },
      { type: "STATUS_CHANGED",    actor: "system",    time: "03:30:00", payload: '{"from":"OUT_FOR_DELIVERY","to":"DELIVERED"}' },
      { type: "PAYMENT_COLLECTED", actor: "seller:AR", time: "03:30:00", payload: '{"method":"cash","amount":4500}' },
    ],
  },
];

const EVENT_ICONS: Record<string, { icon: any; color: string }> = {
  ORDER_CREATED:     { icon: Package,       color: "text-indigo-500" },
  PAYMENT_INITIATED: { icon: CreditCard,    color: "text-amber-500" },
  PAYMENT_CONFIRMED: { icon: CheckCircle2,  color: "text-emerald-500" },
  PAYMENT_COLLECTED: { icon: CheckCircle2,  color: "text-emerald-500" },
  PAYMENT_FAILED:    { icon: AlertCircle,   color: "text-red-500" },
  STATUS_CHANGED:    { icon: RefreshCw,     color: "text-indigo-400" },
  REFUND_ISSUED:     { icon: RefreshCw,     color: "text-violet-500" },
};

const STATUS_FILTERS = ["ALL", "PENDING", "CONFIRMED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"];

export default function SellerOrders() {
  const [orders, setOrders] = useState<Order[]>(MOCK_ORDERS);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [lensMode, setLensMode] = useState<"business" | "system">("business");
  const [pendingTransition, setPendingTransition] = useState<{ order: Order; to: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [, navigate] = useLocation();

  const filteredOrders = orders.filter((o) => {
    const matchesStatus = statusFilter === "ALL" || o.status === statusFilter;
    const matchesSearch =
      !searchQuery ||
      o.publicOrderNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.customer.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const handleTransitionConfirm = () => {
    if (!pendingTransition) return;
    const { order, to } = pendingTransition;
    setIsLoading(true);
    setTimeout(() => {
      setOrders((prev) =>
        prev.map((o) =>
          o.id === order.id
            ? {
                ...o,
                status: to,
                events: [
                  ...o.events,
                  {
                    type: "STATUS_CHANGED",
                    actor: "seller:AR",
                    time: new Date().toTimeString().slice(0, 8),
                    payload: JSON.stringify({ from: o.status, to }),
                  },
                ],
              }
            : o
        )
      );
      if (selectedOrder?.id === order.id) {
        setSelectedOrder((prev) => prev ? { ...prev, status: to } : null);
      }
      toast.success(`Order ${order.publicOrderNumber} updated`, {
        description: `${STATUS_CONFIG[order.status].label} → ${STATUS_CONFIG[to].label}`,
      });
      setPendingTransition(null);
      setIsLoading(false);
    }, 800);
  };

  const formatAmount = (minor: number, currency: string) =>
    `${currency === "USD" ? "$" : currency}${(minor / 100).toFixed(2)}`;

  return (
    <SellerLayout activePage="orders">
      {/* Confirmation Dialog */}
      {pendingTransition && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h3 className="font-semibold text-slate-900 mb-1" style={{ fontFamily: 'Sora, sans-serif' }}>Confirm Status Change</h3>
            <p className="text-sm text-slate-500 mb-5">This action will be recorded in the order timeline and cannot be undone.</p>
            <div className="flex items-center gap-3 bg-slate-50 rounded-xl p-4 mb-5">
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_CONFIG[pendingTransition.order.status].className}`}>
                {STATUS_CONFIG[pendingTransition.order.status].label}
              </span>
              <ArrowRight className="w-4 h-4 text-slate-400" />
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_CONFIG[pendingTransition.to].className}`}>
                {STATUS_CONFIG[pendingTransition.to].label}
              </span>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1" onClick={() => setPendingTransition(null)}>Cancel</Button>
              <Button
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white"
                onClick={handleTransitionConfirm}
                disabled={isLoading}
              >
                {isLoading ? "Updating..." : "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Orders</h1>
          <p className="text-slate-500 text-sm mt-0.5">{orders.length} total orders</p>
        </div>
        {/* Operational Lens Toggle */}
        <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg p-1">
          <button
            onClick={() => setLensMode("business")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              lensMode === "business" ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Layers className="w-3.5 h-3.5" /> Business
          </button>
          <button
            onClick={() => setLensMode("system")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              lensMode === "system" ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Code2 className="w-3.5 h-3.5" /> System
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by order # or customer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300"
          />
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                statusFilter === f
                  ? "bg-slate-900 text-white"
                  : "bg-white border border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {f === "ALL" ? "All" : STATUS_CONFIG[f]?.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main layout */}
      <div className={`flex gap-5 ${selectedOrder ? "h-[calc(100vh-220px)]" : ""}`}>
        {/* Orders Table */}
        <div className={`bg-white rounded-xl border border-slate-200 overflow-hidden ${selectedOrder ? "flex-1 overflow-y-auto" : "w-full"}`}>
          <table className="w-full">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b border-slate-100">
                <th className="text-left text-xs font-medium text-slate-400 px-5 py-3">Order</th>
                <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Customer</th>
                {lensMode === "system" && (
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Order ID</th>
                )}
                <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Amount</th>
                <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
                {lensMode === "system" && (
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Payment</th>
                )}
                <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filteredOrders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-16 text-slate-400 text-sm">
                    No orders match your filters
                  </td>
                </tr>
              ) : (
                filteredOrders.map((order) => {
                  const st = STATUS_CONFIG[order.status];
                  const ps = PAYMENT_STATUS[order.paymentStatus];
                  const isSelected = selectedOrder?.id === order.id;
                  return (
                    <tr
                      key={order.id}
                      className={`border-b border-slate-50 transition-colors cursor-pointer ${
                        isSelected ? "bg-indigo-50/60" : "hover:bg-slate-50/60"
                      }`}
                      onClick={() => setSelectedOrder(isSelected ? null : order)}
                    >
                      <td className="px-5 py-3.5">
                        <span className="font-mono text-xs font-semibold text-slate-800">{order.publicOrderNumber}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="text-sm text-slate-800">{order.customer}</div>
                        {lensMode === "system" && (
                          <div className="font-mono text-xs text-slate-400">{order.phone}</div>
                        )}
                      </td>
                      {lensMode === "system" && (
                        <td className="px-4 py-3.5">
                          <span className="font-mono text-xs text-slate-400">{order.id}</span>
                        </td>
                      )}
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-sm font-medium text-slate-900">
                          {formatAmount(order.amount, order.currency)}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-0.5 rounded-full ${st.className}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                          {st.label}
                        </span>
                      </td>
                      {lensMode === "system" && (
                        <td className="px-4 py-3.5">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded ${ps.className}`}>{ps.label}</span>
                        </td>
                      )}
                      <td className="px-4 py-3.5">
                        <span className="text-xs text-slate-400 font-mono">
                          {new Date(order.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/seller/orders/${order.publicOrderNumber}`); }}
                            className="p-1 rounded hover:bg-indigo-50 text-slate-300 hover:text-indigo-600 transition-colors"
                            title="Open full detail page"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </button>
                          <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? "text-indigo-500 rotate-90" : "text-slate-300"}`} />
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Order Detail Panel */}
        {selectedOrder && (
          <div className="w-96 flex-shrink-0 bg-white rounded-xl border border-slate-200 overflow-y-auto flex flex-col">
            {/* Panel Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <div>
                <div className="font-mono text-sm font-semibold text-slate-900">{selectedOrder.publicOrderNumber}</div>
                <div className="text-xs text-slate-500 mt-0.5">{selectedOrder.customer}</div>
              </div>
              <button onClick={() => setSelectedOrder(null)} className="w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center">
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            {/* Status + Action Surface */}
            <div className="px-5 py-4 border-b border-slate-100">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-xs text-slate-400 mb-1">Order Status</div>
                  <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_CONFIG[selectedOrder.status].className}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${STATUS_CONFIG[selectedOrder.status].dot}`} />
                    {STATUS_CONFIG[selectedOrder.status].label}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-slate-400 mb-1">Payment</div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${PAYMENT_STATUS[selectedOrder.paymentStatus].className}`}>
                    {PAYMENT_STATUS[selectedOrder.paymentStatus].label}
                  </span>
                </div>
              </div>

              {/* Constrained Action Surface */}
              {VALID_TRANSITIONS[selectedOrder.status].length > 0 && (
                <div className="space-y-2 mt-3">
                  <div className="text-xs font-medium text-slate-500 mb-1.5">Valid Actions</div>
                  {VALID_TRANSITIONS[selectedOrder.status].map((nextStatus) => (
                    <button
                      key={nextStatus}
                      onClick={() => setPendingTransition({ order: selectedOrder, to: nextStatus })}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg border text-sm font-medium transition-all hover:shadow-sm ${
                        nextStatus === "CANCELLED"
                          ? "border-red-200 text-red-600 hover:bg-red-50"
                          : "border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                      }`}
                    >
                      <span>Change to: {STATUS_CONFIG[nextStatus].label}</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  ))}
                  <button
                    onClick={() => toast.info("Refund", { description: "Feature coming soon" })}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-all"
                  >
                    <span>Issue Refund</span>
                    <CreditCard className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              {VALID_TRANSITIONS[selectedOrder.status].length === 0 && (
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400 bg-slate-50 rounded-lg px-3 py-2">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Terminal state — no further transitions
                </div>
              )}
            </div>

            {/* Order Items */}
            <div className="px-5 py-4 border-b border-slate-100">
              <div className="text-xs font-medium text-slate-500 mb-3">Items</div>
              <div className="space-y-2">
                {selectedOrder.items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div>
                      <div className="text-sm text-slate-800">{item.name}</div>
                      <div className="text-xs text-slate-400">Qty: {item.qty}</div>
                    </div>
                    <span className="font-mono text-sm font-medium text-slate-900">
                      {formatAmount(item.price * item.qty, selectedOrder.currency)}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-sm font-semibold text-slate-900">Total</span>
                  <span className="font-mono text-sm font-bold text-slate-900">
                    {formatAmount(selectedOrder.amount, selectedOrder.currency)}
                  </span>
                </div>
              </div>
              {selectedOrder.notes && (
                <div className="mt-3 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 text-xs text-amber-700">
                  Note: {selectedOrder.notes}
                </div>
              )}
            </div>

            {/* Timeline */}
            <div className="px-5 py-4 flex-1">
              <div className="text-xs font-medium text-slate-500 mb-4">Order Timeline</div>
              <div className="relative">
                <div className="absolute left-3.5 top-0 bottom-0 w-px bg-slate-100" />
                <div className="space-y-4">
                  {selectedOrder.events.map((event, i) => {
                    const cfg = EVENT_ICONS[event.type] || { icon: RefreshCw, color: "text-slate-400" };
                    const Icon = cfg.icon;
                    return (
                      <div key={i} className="flex items-start gap-3 relative">
                        <div className="w-7 h-7 rounded-full bg-white border border-slate-200 flex items-center justify-center flex-shrink-0 z-10">
                          <Icon className={`w-3.5 h-3.5 ${cfg.color}`} />
                        </div>
                        <div className="flex-1 min-w-0 pt-0.5">
                          <div className="text-xs font-medium text-slate-800">
                            {event.type.replace(/_/g, " ")}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-slate-400 font-mono">{event.time}</span>
                            <span className="text-xs text-slate-400">·</span>
                            <span className="text-xs text-slate-500">{event.actor}</span>
                          </div>
                          {lensMode === "system" && event.payload && (
                            <div className="mt-1.5 bg-slate-50 rounded px-2 py-1.5 font-mono text-xs text-slate-500 break-all">
                              {event.payload}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </SellerLayout>
  );
}
