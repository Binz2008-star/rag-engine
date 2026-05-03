/**
 * DESIGN: "Operational Clarity"
 * Seller Dashboard — main hub for order management
 * Layout: Fixed dark sidebar (240px) + light content area
 */
import { useState } from "react";
import { useLocation } from "wouter";
import {
  LayoutDashboard, ShoppingCart, Package, Users, BarChart2,
  Settings, LogOut, Bell, Search, TrendingUp, TrendingDown,
  Clock, CheckCircle2, XCircle, Truck, ArrowRight, Sparkles,
  ChevronRight, MoreHorizontal, RefreshCw, AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import SellerLayout from "@/components/SellerLayout";

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  PENDING:           { label: "Pending",          className: "bg-slate-100 text-slate-700" },
  CONFIRMED:         { label: "Confirmed",         className: "bg-blue-50 text-blue-700" },
  PREPARING:         { label: "Preparing",         className: "bg-amber-50 text-amber-700" },
  READY_FOR_PICKUP:  { label: "Ready for Pickup",  className: "bg-purple-50 text-purple-700" },
  OUT_FOR_DELIVERY:  { label: "Out for Delivery",  className: "bg-orange-50 text-orange-700" },
  DELIVERED:         { label: "Delivered",         className: "bg-emerald-50 text-emerald-700" },
  FAILED_DELIVERY:   { label: "Failed Delivery",   className: "bg-rose-50 text-rose-700" },
  CANCELLED:         { label: "Cancelled",         className: "bg-gray-100 text-gray-500" },
};

const MOCK_ORDERS = [
  { id: "ORD-2847", customer: "Ahmed Al-Rashidi", amount: "$124.00", status: "PENDING",          time: "2 min ago",  items: 3 },
  { id: "ORD-2846", customer: "Sara Mohammed",    amount: "$67.50",  status: "CONFIRMED",        time: "18 min ago", items: 1 },
  { id: "ORD-2845", customer: "Khalid Hassan",    amount: "$210.00", status: "PREPARING",        time: "1 hr ago",   items: 4 },
  { id: "ORD-2844", customer: "Fatima Al-Zahra",  amount: "$89.99",  status: "OUT_FOR_DELIVERY", time: "3 hr ago",   items: 2 },
  { id: "ORD-2843", customer: "Omar Nasser",      amount: "$45.00",  status: "DELIVERED",        time: "5 hr ago",   items: 1 },
  { id: "ORD-2842", customer: "Layla Ibrahim",    amount: "$178.00", status: "DELIVERED",        time: "8 hr ago",   items: 5 },
];

const METRICS = [
  { label: "Total Orders",    value: "1,247",   change: "+12%", up: true,  icon: ShoppingCart,  color: "text-indigo-600",  bg: "bg-indigo-50" },
  { label: "Revenue (Month)", value: "$48,320", change: "+8%",  up: true,  icon: TrendingUp,    color: "text-emerald-600", bg: "bg-emerald-50" },
  { label: "Pending Orders",  value: "34",      change: "-5%",  up: false, icon: Clock,         color: "text-amber-600",   bg: "bg-amber-50" },
  { label: "Delivered Today", value: "89",      change: "+23%", up: true,  icon: CheckCircle2,  color: "text-emerald-600", bg: "bg-emerald-50" },
];

const ACTIVITY = [
  { icon: ShoppingCart, text: "New order #ORD-2847 from Ahmed Al-Rashidi", time: "2m", color: "text-indigo-500" },
  { icon: Truck,        text: "Order #ORD-2844 is now out for delivery",   time: "3h", color: "text-orange-500" },
  { icon: CheckCircle2, text: "Order #ORD-2843 delivered successfully",    time: "5h", color: "text-emerald-500" },
  { icon: AlertCircle,  text: "Payment failed for order #ORD-2839",        time: "6h", color: "text-rose-500" },
  { icon: RefreshCw,    text: "Refund processed for order #ORD-2835",      time: "1d", color: "text-slate-500" },
];

export default function SellerDashboard() {
  const [, navigate] = useLocation();
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <SellerLayout activePage="dashboard">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">Wednesday, April 9, 2026</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search orders, customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg w-64 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300"
            />
          </div>
          <Button
            onClick={() => toast.success("AI Search activated", { description: "Semantic search powered by vector embeddings" })}
            className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2 text-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI Search
          </Button>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {METRICS.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:shadow-slate-100 transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className={`w-9 h-9 rounded-lg ${m.bg} flex items-center justify-center`}>
                  <Icon className={`w-4.5 h-4.5 ${m.color}`} />
                </div>
                <span className={`text-xs font-medium flex items-center gap-0.5 ${m.up ? 'text-emerald-600' : 'text-rose-500'}`}>
                  {m.up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {m.change}
                </span>
              </div>
              <div className="text-2xl font-bold text-slate-900 mb-0.5" style={{ fontFamily: 'Sora, sans-serif' }}>{m.value}</div>
              <div className="text-xs text-slate-500">{m.label}</div>
            </div>
          );
        })}
      </div>

      {/* Main Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent Orders Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Recent Orders</h2>
            <Button
              variant="ghost"
              size="sm"
              className="text-indigo-600 hover:text-indigo-700 gap-1 text-xs"
              onClick={() => navigate("/seller/orders")}
            >
              View all <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left text-xs font-medium text-slate-400 px-6 py-3">Order</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Customer</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Amount</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
                  <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Time</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {MOCK_ORDERS.map((order, i) => {
                  const st = STATUS_CONFIG[order.status];
                  return (
                    <tr
                      key={order.id}
                      className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors cursor-pointer"
                      onClick={() => navigate(`/seller/orders/${order.id}`)}
                    >
                      <td className="px-6 py-3.5">
                        <span className="font-mono text-xs font-medium text-slate-700">{order.id}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="text-sm text-slate-700">{order.customer}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-sm font-medium text-slate-900">{order.amount}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${st.className}`}>{st.label}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="text-xs text-slate-400">{order.time}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          className="text-slate-300 hover:text-slate-600 transition-colors"
                          onClick={(e) => { e.stopPropagation(); toast.info("Actions menu"); }}
                        >
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Activity Feed */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Activity</h2>
            <Bell className="w-4 h-4 text-slate-400" />
          </div>
          <div className="divide-y divide-slate-50">
            {ACTIVITY.map((a, i) => {
              const Icon = a.icon;
              return (
                <div key={i} className="flex items-start gap-3 px-5 py-3.5 hover:bg-slate-50/60 transition-colors">
                  <div className={`w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 mt-0.5`}>
                    <Icon className={`w-3.5 h-3.5 ${a.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-700 leading-snug">{a.text}</p>
                    <span className="text-xs text-slate-400 mt-0.5 block">{a.time}</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="px-5 py-3 border-t border-slate-100">
            <Button variant="ghost" size="sm" className="w-full text-xs text-slate-500 gap-1">
              View all activity <ArrowRight className="w-3 h-3" />
            </Button>
          </div>
        </div>
      </div>

      {/* Status Distribution */}
      <div className="mt-6 bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Sora, sans-serif' }}>Order Status Distribution</h2>
        <div className="flex items-center gap-2 mb-3">
          {[
            { status: "DELIVERED",        count: 891, pct: 71 },
            { status: "OUT_FOR_DELIVERY", count: 156, pct: 13 },
            { status: "PREPARING",        count: 89,  pct: 7  },
            { status: "CONFIRMED",        count: 67,  pct: 5  },
            { status: "PENDING",          count: 34,  pct: 3  },
            { status: "CANCELLED",        count: 10,  pct: 1  },
          ].map(({ status, pct }) => {
            const colorMap: Record<string, string> = {
              DELIVERED: "bg-emerald-500",
              OUT_FOR_DELIVERY: "bg-orange-400",
              PREPARING: "bg-amber-400",
              CONFIRMED: "bg-blue-400",
              PENDING: "bg-slate-300",
              CANCELLED: "bg-gray-200",
            };
            return (
              <div
                key={status}
                className={`h-3 rounded-full ${colorMap[status]} transition-all`}
                style={{ width: `${pct}%` }}
                title={`${STATUS_CONFIG[status]?.label}: ${pct}%`}
              />
            );
          })}
        </div>
        <div className="flex flex-wrap gap-4">
          {[
            { status: "DELIVERED",        count: 891, color: "bg-emerald-500" },
            { status: "OUT_FOR_DELIVERY", count: 156, color: "bg-orange-400" },
            { status: "PREPARING",        count: 89,  color: "bg-amber-400" },
            { status: "CONFIRMED",        count: 67,  color: "bg-blue-400" },
            { status: "PENDING",          count: 34,  color: "bg-slate-300" },
            { status: "CANCELLED",        count: 10,  color: "bg-gray-200" },
          ].map(({ status, count, color }) => (
            <div key={status} className="flex items-center gap-1.5">
              <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
              <span className="text-xs text-slate-600">{STATUS_CONFIG[status]?.label}</span>
              <span className="text-xs font-mono font-medium text-slate-900">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </SellerLayout>
  );
}
