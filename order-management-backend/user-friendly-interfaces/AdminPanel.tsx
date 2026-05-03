/**
 * DESIGN: "Operational Clarity"
 * Admin Panel — system-level control
 * Features: system health, AI policy controls, seller management, webhook log
 * Operational Lens: always in "System" mode for admins
 */
import { useState } from "react";
import { useLocation } from "wouter";
import {
  Shield, Activity, Users, Cpu, ChevronLeft, CheckCircle2,
  AlertCircle, XCircle, RefreshCw, Zap, Database, Radio,
  ToggleLeft, ToggleRight, Eye, BarChart2, Clock, ArrowRight,
  Server, Layers
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const AI_SEARCH_IMG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-ai-search-iR3mgUcrqMJU96gqqu3oKS.webp";

const HEALTH_METRICS = [
  { label: "API Server",      status: "healthy",   value: "99.9% uptime",    icon: Server },
  { label: "PostgreSQL",      status: "healthy",   value: "12ms avg query",  icon: Database },
  { label: "Redis",           status: "healthy",   value: "0.3ms latency",   icon: Zap },
  { label: "AI Worker",       status: "warning",   value: "Queue: 47 jobs",  icon: Cpu },
  { label: "BullMQ",          status: "healthy",   value: "3 workers active",icon: Layers },
  { label: "Stripe Webhook",  status: "healthy",   value: "Last: 2m ago",    icon: Radio },
];

const STATUS_ICON: Record<string, { icon: any; color: string; bg: string }> = {
  healthy: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
  warning: { icon: AlertCircle,  color: "text-amber-600",   bg: "bg-amber-50" },
  error:   { icon: XCircle,      color: "text-red-600",     bg: "bg-red-50" },
};

const SELLERS = [
  { id: "s1", name: "Tech Gadgets Plus", slug: "tech-gadgets", status: "ACTIVE",    orders: 1247, revenue: 48320, aiEnabled: true },
  { id: "s2", name: "Aurora Goods",      slug: "aurora-goods", status: "ACTIVE",    orders: 834,  revenue: 31200, aiEnabled: false },
  { id: "s3", name: "Swift Commerce",    slug: "swift-co",     status: "ACTIVE",    orders: 412,  revenue: 18900, aiEnabled: true },
  { id: "s4", name: "Nova Store",        slug: "nova-store",   status: "SUSPENDED", orders: 89,   revenue: 3200,  aiEnabled: false },
];

const WEBHOOK_EVENTS = [
  { id: "wh1", provider: "stripe",    type: "payment_intent.succeeded", status: "PROCESSED", time: "06:02:08", ref: "pi_3Qx..." },
  { id: "wh2", provider: "stripe",    type: "payment_intent.failed",    status: "PROCESSED", time: "05:44:02", ref: "pi_3Qy..." },
  { id: "wh3", provider: "whatsapp",  type: "message.received",         status: "PROCESSED", time: "05:30:00", ref: "wam_..." },
  { id: "wh4", provider: "stripe",    type: "charge.refunded",          status: "PENDING",   time: "04:15:00", ref: "ch_1Q..." },
  { id: "wh5", provider: "whatsapp",  type: "message.delivered",        status: "PROCESSED", time: "03:50:00", ref: "wam_..." },
];

const AI_JOBS = [
  { id: "j1", seller: "Tech Gadgets Plus", type: "FULL_REINDEX",    status: "COMPLETED", chunks: 847,  duration: "2m 14s" },
  { id: "j2", seller: "Swift Commerce",    type: "PARTIAL_REINDEX", status: "RUNNING",   chunks: 234,  duration: "ongoing" },
  { id: "j3", seller: "Aurora Goods",      type: "FULL_REINDEX",    status: "PENDING",   chunks: null, duration: "—" },
];

const TABS = ["Overview", "Sellers", "AI Engine", "Webhooks"];

export default function AdminPanel() {
  const [, navigate] = useLocation();
  const [activeTab, setActiveTab] = useState("Overview");
  const [sellers, setSellers] = useState(SELLERS);

  const toggleSellerAI = (id: string) => {
    setSellers((prev) =>
      prev.map((s) => (s.id === id ? { ...s, aiEnabled: !s.aiEnabled } : s))
    );
    const s = sellers.find((s) => s.id === id);
    toast.success(`AI ${s?.aiEnabled ? "disabled" : "enabled"} for ${s?.name}`);
  };

  const toggleSellerStatus = (id: string) => {
    setSellers((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, status: s.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE" } : s
      )
    );
    const s = sellers.find((s) => s.id === id);
    toast.success(`Seller ${s?.status === "ACTIVE" ? "suspended" : "reactivated"}`, { description: s?.name });
  };

  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/")} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center">
              <ChevronLeft className="w-4 h-4 text-slate-500" />
            </button>
            <div className="w-7 h-7 rounded-md bg-rose-600 flex items-center justify-center">
              <Shield className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <span className="font-semibold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>Admin Panel</span>
              <span className="text-xs text-slate-400 ml-2">System Control</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              All systems operational
            </div>
          </div>
        </div>
        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-6 flex gap-0 border-t border-slate-100">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* OVERVIEW TAB */}
        {activeTab === "Overview" && (
          <div className="space-y-6">
            {/* System Health */}
            <div>
              <h2 className="text-lg font-semibold text-slate-900 mb-3" style={{ fontFamily: 'Sora, sans-serif' }}>System Health</h2>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                {HEALTH_METRICS.map((m) => {
                  const cfg = STATUS_ICON[m.status];
                  const Icon = m.icon;
                  const StatusIcon = cfg.icon;
                  return (
                    <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4 flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                        <Icon className="w-4.5 h-4.5 text-slate-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-sm font-medium text-slate-900">{m.label}</span>
                          <StatusIcon className={`w-4 h-4 ${cfg.color}`} />
                        </div>
                        <span className="font-mono text-xs text-slate-500">{m.value}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Platform Metrics */}
            <div>
              <h2 className="text-lg font-semibold text-slate-900 mb-3" style={{ fontFamily: 'Sora, sans-serif' }}>Platform Metrics</h2>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: "Total Sellers",    value: "4",       icon: Users,     color: "text-indigo-600", bg: "bg-indigo-50" },
                  { label: "Orders Today",     value: "247",     icon: BarChart2, color: "text-emerald-600", bg: "bg-emerald-50" },
                  { label: "AI Queries Today", value: "1,842",   icon: Cpu,       color: "text-violet-600", bg: "bg-violet-50" },
                  { label: "Pending Webhooks", value: "1",       icon: Radio,     color: "text-amber-600",  bg: "bg-amber-50" },
                ].map((m) => {
                  const Icon = m.icon;
                  return (
                    <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4">
                      <div className={`w-8 h-8 rounded-lg ${m.bg} flex items-center justify-center mb-2`}>
                        <Icon className={`w-4 h-4 ${m.color}`} />
                      </div>
                      <div className="text-2xl font-bold text-slate-900 mb-0.5" style={{ fontFamily: 'Sora, sans-serif' }}>{m.value}</div>
                      <div className="text-xs text-slate-500">{m.label}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* AI Search Preview */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-violet-500" />
                  <h2 className="font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>AI Search Interface</h2>
                </div>
                <span className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full font-medium">Hybrid FTS + Vector</span>
              </div>
              <img src={AI_SEARCH_IMG} alt="AI Search" className="w-full" />
            </div>
          </div>
        )}

        {/* SELLERS TAB */}
        {activeTab === "Sellers" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Seller Management</h2>
              <Button
                onClick={() => toast.info("Add Seller", { description: "Feature coming soon" })}
                className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2 text-sm"
              >
                + Add Seller
              </Button>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-medium text-slate-400 px-5 py-3">Seller</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Slug</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Orders</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Revenue</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">AI Search</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {sellers.map((seller) => (
                    <tr key={seller.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                            <span className="text-xs font-bold text-indigo-700">{seller.name[0]}</span>
                          </div>
                          <span className="text-sm font-medium text-slate-900">{seller.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-500">{seller.slug}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-sm text-slate-900">{seller.orders.toLocaleString()}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-sm text-slate-900">${seller.revenue.toLocaleString()}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => toggleSellerAI(seller.id)}
                          className="flex items-center gap-1.5 text-xs font-medium transition-colors"
                        >
                          {seller.aiEnabled ? (
                            <>
                              <ToggleRight className="w-5 h-5 text-indigo-600" />
                              <span className="text-indigo-600">Enabled</span>
                            </>
                          ) : (
                            <>
                              <ToggleLeft className="w-5 h-5 text-slate-400" />
                              <span className="text-slate-400">Disabled</span>
                            </>
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => toggleSellerStatus(seller.id)}
                          className={`text-xs font-medium px-2.5 py-0.5 rounded-full transition-colors ${
                            seller.status === "ACTIVE"
                              ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200"
                              : "bg-red-100 text-red-700 hover:bg-red-200"
                          }`}
                        >
                          {seller.status}
                        </button>
                      </td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={() => toast.info(`View ${seller.name}`, { description: "Feature coming soon" })}
                          className="w-7 h-7 rounded-md hover:bg-slate-100 flex items-center justify-center"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-400" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* AI ENGINE TAB */}
        {activeTab === "AI Engine" && (
          <div className="space-y-5">
            <div className="grid lg:grid-cols-3 gap-4">
              {[
                { label: "Documents Indexed",  value: "12,847", icon: Database, color: "text-indigo-600", bg: "bg-indigo-50" },
                { label: "Vector Dimensions",  value: "384",    icon: Cpu,      color: "text-violet-600", bg: "bg-violet-50" },
                { label: "Avg Query Latency",  value: "120ms",  icon: Zap,      color: "text-amber-600",  bg: "bg-amber-50" },
              ].map((m) => {
                const Icon = m.icon;
                return (
                  <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-5">
                    <div className={`w-9 h-9 rounded-lg ${m.bg} flex items-center justify-center mb-3`}>
                      <Icon className={`w-4.5 h-4.5 ${m.color}`} />
                    </div>
                    <div className="text-2xl font-bold text-slate-900 font-mono mb-0.5">{m.value}</div>
                    <div className="text-xs text-slate-500">{m.label}</div>
                  </div>
                );
              })}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                <h3 className="font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Index Jobs</h3>
                <Button
                  onClick={() => toast.success("Reindex triggered", { description: "Full reindex queued for all sellers" })}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2 text-xs h-8"
                >
                  <RefreshCw className="w-3 h-3" /> Trigger Reindex
                </Button>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-medium text-slate-400 px-5 py-3">Seller</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Job Type</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Chunks</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Duration</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {AI_JOBS.map((job) => (
                    <tr key={job.id} className="border-b border-slate-50">
                      <td className="px-5 py-3.5 text-sm text-slate-800">{job.seller}</td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-600">{job.type}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-sm text-slate-900">{job.chunks ?? "—"}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-500">{job.duration}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          job.status === "COMPLETED" ? "bg-emerald-100 text-emerald-700" :
                          job.status === "RUNNING"   ? "bg-indigo-100 text-indigo-700" :
                                                       "bg-slate-100 text-slate-600"
                        }`}>
                          {job.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* AI Policy note */}
            <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
              <div className="flex items-start gap-3">
                <Cpu className="w-4 h-4 text-violet-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="text-sm font-semibold text-violet-900 mb-1">AI Policy Controls</div>
                  <p className="text-xs text-violet-700 leading-relaxed">
                    Each seller has a <code className="font-mono bg-violet-100 px-1 rounded">SellerAiPolicy</code> record controlling:
                    retrieval enabled, intent routing, catalog normalization, reranking, max chunks per query, and minimum score threshold.
                    Toggle AI per-seller in the Sellers tab. Benchmark gate must pass before retrieval is activated.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* WEBHOOKS TAB */}
        {activeTab === "Webhooks" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Webhook Events</h2>
              <span className="text-xs text-slate-500 font-mono">Stripe · WhatsApp</span>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-medium text-slate-400 px-5 py-3">Provider</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Event Type</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Reference</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Time</th>
                    <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {WEBHOOK_EVENTS.map((ev) => (
                    <tr key={ev.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                      <td className="px-5 py-3.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          ev.provider === "stripe" ? "bg-violet-100 text-violet-700" : "bg-emerald-100 text-emerald-700"
                        }`}>
                          {ev.provider}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-700">{ev.type}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-400">{ev.ref}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className="font-mono text-xs text-slate-500">{ev.time}</span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          ev.status === "PROCESSED" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {ev.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
