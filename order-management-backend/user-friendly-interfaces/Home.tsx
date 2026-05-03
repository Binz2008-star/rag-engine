/**
 * DESIGN: "Operational Clarity" — Swiss-inspired SaaS
 * Landing page: showcases 3 interface proposals + design principles
 * Fonts: Sora (headings), DM Sans (body), JetBrains Mono (IDs/code)
 */
import { useLocation } from "wouter";
import {
  ArrowRight, LayoutDashboard, ShoppingBag, Shield, Sparkles,
  CheckCircle2, Zap, Users, Eye, Lock, GitBranch, Layers,
  Code2, AlertCircle, Package
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const DASHBOARD_IMG  = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-dashboard-LHfqSE8wfaVW7D4GjYNcV5.webp";
const STOREFRONT_IMG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-storefront-mr2pWw736WR8xdmx88nBHS.webp";
const ORDER_FLOW_IMG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-order-flow-CcHafL6DRdEx7ZX8AkJStC.webp";
const AI_SEARCH_IMG  = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-ai-search-iR3mgUcrqMJU96gqqu3oKS.webp";

const INTERFACES = [
  {
    id: "seller",
    icon: LayoutDashboard,
    label: "Seller Dashboard",
    badge: "Primary Interface",
    badgeClass: "bg-indigo-100 text-indigo-700",
    description: "Full-featured management console for sellers — order lifecycle, product catalog, payments, and AI-powered search.",
    image: DASHBOARD_IMG,
    path: "/seller/dashboard",
    features: ["Order lifecycle management", "State-machine-driven transitions", "Product catalog CRUD", "Payment & refund controls", "AI semantic search"],
    accent: "border-indigo-200 hover:border-indigo-300",
    btnClass: "bg-indigo-600 hover:bg-indigo-700 text-white",
  },
  {
    id: "storefront",
    icon: ShoppingBag,
    label: "Customer Storefront",
    badge: "Public Interface",
    badgeClass: "bg-emerald-100 text-emerald-700",
    description: "Mobile-first public storefront — browse products, place orders, and track delivery. No login required.",
    image: STOREFRONT_IMG,
    path: "/store/demo-seller",
    features: ["Product browsing & cart", "Checkout with validation", "Order confirmation flow", "Mobile-optimized UX", "WhatsApp delivery updates"],
    accent: "border-emerald-200 hover:border-emerald-300",
    btnClass: "bg-emerald-600 hover:bg-emerald-700 text-white",
  },
  {
    id: "admin",
    icon: Shield,
    label: "Admin Panel",
    badge: "Internal Tool",
    badgeClass: "bg-rose-100 text-rose-700",
    description: "System-level control for administrators — seller management, health monitoring, AI policy, and webhook logs.",
    image: AI_SEARCH_IMG,
    path: "/admin",
    features: ["Seller onboarding & management", "System health monitoring", "AI policy per-seller toggle", "Webhook event log", "Index job management"],
    accent: "border-rose-200 hover:border-rose-300",
    btnClass: "bg-rose-600 hover:bg-rose-700 text-white",
  },
];

const DESIGN_PRINCIPLES = [
  {
    icon: Eye,
    title: "State is Always Visible",
    desc: "Order status, payment status, and system state are always shown. No hidden mutations.",
    color: "text-indigo-600",
    bg: "bg-indigo-50",
  },
  {
    icon: Lock,
    title: "Actions are Constrained",
    desc: "Only valid state transitions are shown. The UI enforces the backend state machine — no free-form actions.",
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  {
    icon: GitBranch,
    title: "Every Change is Traceable",
    desc: "Order timeline is always visible with timestamps and actor. No action goes unrecorded.",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
  },
  {
    icon: Layers,
    title: "Operational Lens Toggle",
    desc: "Business view for sellers, System view for developers — same data, different resolution.",
    color: "text-violet-600",
    bg: "bg-violet-50",
  },
];

const COLOR_SEMANTICS = [
  { meaning: "Neutral / Pending",          color: "Slate",   swatch: "bg-slate-400",   example: "bg-slate-100 text-slate-700" },
  { meaning: "In Progress / Action",       color: "Indigo",  swatch: "bg-indigo-500",  example: "bg-indigo-100 text-indigo-700" },
  { meaning: "Warning / Action Required",  color: "Amber",   swatch: "bg-amber-400",   example: "bg-amber-100 text-amber-700" },
  { meaning: "Success / Delivered",        color: "Emerald", swatch: "bg-emerald-500", example: "bg-emerald-100 text-emerald-700" },
  { meaning: "Error / Failure",            color: "Red",     swatch: "bg-red-500",     example: "bg-red-100 text-red-700" },
];

const HIGHLIGHTS = [
  { icon: Zap,          label: "25 API Endpoints",   desc: "All mapped to UI components" },
  { icon: Sparkles,     label: "AI-Powered Search",  desc: "Hybrid vector + full-text" },
  { icon: Users,        label: "Multi-tenant",       desc: "Strict seller isolation" },
  { icon: CheckCircle2, label: "8 Order States",     desc: "Full lifecycle management" },
];

export default function Home() {
  const [, navigate] = useLocation();

  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <Package className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-bold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>OrderFlow</span>

            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/admin")} className="text-xs text-slate-500 hover:text-slate-700 transition-colors">
              Admin Panel
            </button>
            <Button onClick={() => navigate("/seller/dashboard")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-8 px-3 gap-1.5">
              Seller Dashboard <ArrowRight className="w-3 h-3" />
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-16 pb-12">
        <div className="grid lg:grid-cols-2 gap-14 items-center">
          <div>
            <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 text-xs font-medium px-3 py-1.5 rounded-full mb-6 border border-indigo-100">
              <Sparkles className="w-3 h-3" />
              Order Management System
            </div>
            <h1 className="text-5xl font-bold text-slate-900 leading-tight mb-5" style={{ fontFamily: 'Sora, sans-serif' }}>
              Order Management<br />
              <span className="text-indigo-600">OrderFlow</span>
            </h1>
            <p className="text-lg text-slate-600 leading-relaxed mb-8 max-w-lg">
              A production-grade interface design for the Order Management Backend — built around state visibility, constrained actions, and full traceability.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => navigate("/seller/dashboard")} className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2">
                Seller Dashboard <ArrowRight className="w-4 h-4" />
              </Button>
              <Button variant="outline" onClick={() => navigate("/store/demo-seller")} className="gap-2">
                Customer Storefront <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <div className="relative">
            <div className="rounded-2xl overflow-hidden shadow-2xl shadow-slate-200 border border-slate-200">
              <img src={DASHBOARD_IMG} alt="Seller Dashboard Preview" className="w-full" />
            </div>
            <div className="absolute -bottom-4 -left-4 bg-white rounded-xl shadow-lg border border-slate-200 p-3 flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-medium text-slate-700">Backend: Production Ready</span>
            </div>
            <div className="absolute -top-3 -right-3 bg-indigo-600 text-white rounded-xl px-3 py-1.5 text-xs font-medium shadow-lg">
              Live
            </div>
          </div>
        </div>
      </section>

      {/* Highlights */}
      <section className="max-w-7xl mx-auto px-6 pb-12">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {HIGHLIGHTS.map(({ icon: Icon, label, desc }) => (
            <div key={label} className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-indigo-600" />
              </div>
              <div>
                <div className="font-semibold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>{label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Design Principles */}
      <section className="max-w-7xl mx-auto px-6 pb-12">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Design Philosophy</h2>
          <p className="text-slate-500 mt-1 text-sm">
            <span className="font-semibold text-slate-700">Operational Clarity</span> = state visibility + action confidence + zero ambiguity
          </p>
        </div>
        <div className="grid lg:grid-cols-4 gap-4 mb-8">
          {DESIGN_PRINCIPLES.map(({ icon: Icon, title, desc, color, bg }) => (
            <div key={title} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center mb-3`}>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <div className="font-semibold text-slate-900 text-sm mb-1.5" style={{ fontFamily: 'Sora, sans-serif' }}>{title}</div>
              <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Color Semantics */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Code2 className="w-4 h-4 text-slate-500" />
            <h3 className="font-semibold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>Color Semantics — Global & Immutable</h3>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {COLOR_SEMANTICS.map(({ meaning, color, swatch, example }) => (
              <div key={meaning} className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${swatch}`} />
                  <span className="text-xs font-medium text-slate-700">{color}</span>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${example} w-fit`}>{meaning}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                <span><strong>Indigo = action + progression</strong>, NOT success</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span><strong>Emerald = success/delivered only</strong></span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Code2 className="w-3.5 h-3.5 text-slate-400" />
                <span><strong>JetBrains Mono</strong> for IDs, prices, logs</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Interface Cards */}
      <section className="max-w-7xl mx-auto px-6 pb-16">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Three Interfaces</h2>
          <p className="text-slate-500 mt-1 text-sm">Click any interface to enter the live console</p>
        </div>
        <div className="grid lg:grid-cols-3 gap-6">
          {INTERFACES.map((iface) => {
            const Icon = iface.icon;
            return (
              <div
                key={iface.id}
                className={`bg-white rounded-2xl border overflow-hidden hover:shadow-xl hover:shadow-slate-200/60 hover:-translate-y-1 transition-all duration-300 cursor-pointer group ${iface.accent}`}
                onClick={() => navigate(iface.path)}
              >
                <div className="relative overflow-hidden h-44 bg-slate-100">
                  <img
                    src={iface.image}
                    alt={iface.label}
                    className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500"
                  />
                </div>
                <div className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center">
                        <Icon className="w-4 h-4 text-slate-700" />
                      </div>
                      <h3 className="font-semibold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>{iface.label}</h3>
                    </div>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${iface.badgeClass}`}>{iface.badge}</span>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed mb-4">{iface.description}</p>
                  <ul className="space-y-1.5 mb-5">
                    {iface.features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-xs text-slate-600">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Button className={`w-full gap-2 text-sm ${iface.btnClass}`}>
                    Explore Interface <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Order State Machine */}
      <section className="max-w-7xl mx-auto px-6 pb-16">
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="p-6 border-b border-slate-100">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                <Zap className="w-4 h-4 text-indigo-600" />
              </div>
              <h2 className="text-lg font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Order Lifecycle State Machine</h2>
            </div>
            <p className="text-slate-500 text-sm ml-11">The backend enforces strict transitions. The UI surfaces only valid next states — no free-form actions.</p>
          </div>
          <div className="p-5 bg-slate-50 border-b border-slate-100">
            <img src={ORDER_FLOW_IMG} alt="Order Lifecycle" className="w-full rounded-lg" />
          </div>
          <div className="p-6 grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { status: "PENDING",          cls: "bg-slate-100 text-slate-700",    desc: "New order awaiting confirmation" },
              { status: "CONFIRMED",        cls: "bg-indigo-100 text-indigo-700",  desc: "Seller confirmed the order" },
              { status: "PREPARING",        cls: "bg-amber-100 text-amber-700",    desc: "Order being packed" },
              { status: "READY_FOR_PICKUP", cls: "bg-violet-100 text-violet-700",  desc: "Awaiting courier pickup" },
              { status: "OUT_FOR_DELIVERY", cls: "bg-orange-100 text-orange-700",  desc: "En route to customer" },
              { status: "DELIVERED",        cls: "bg-emerald-100 text-emerald-700",desc: "Terminal: success" },
              { status: "FAILED_DELIVERY",  cls: "bg-red-100 text-red-700",        desc: "Can retry or cancel" },
              { status: "CANCELLED",        cls: "bg-gray-100 text-gray-500",      desc: "Terminal: cancelled" },
            ].map(({ status, cls, desc }) => (
              <div key={status} className="flex flex-col gap-1">
                <span className={`font-mono text-xs font-medium px-2 py-0.5 rounded w-fit ${cls}`}>{status}</span>
                <span className="text-xs text-slate-500">{desc}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <span className="text-sm text-slate-500">OrderFlow · Order Management System</span>
          <span className="text-xs font-mono text-slate-400">NestJS · PostgreSQL · Redis · BullMQ · AI/Vectors</span>
        </div>
      </footer>
    </div>
  );
}
