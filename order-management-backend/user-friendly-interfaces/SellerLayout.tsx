/**
 * DESIGN: "Operational Clarity"
 * Shared layout: 240px deep-slate sidebar + 56px topbar + white content
 * Sidebar: matte, low-contrast icons, active = indigo bar + subtle bg
 */
import { ReactNode, useState } from "react";
import { useLocation } from "wouter";
import {
  LayoutDashboard, ShoppingCart, Package, Users,
  Settings, LogOut, Bell, ChevronLeft, Store,
  Shield, Sparkles
} from "lucide-react";
import { toast } from "sonner";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard",  icon: LayoutDashboard, path: "/seller/dashboard" },
  { id: "orders",    label: "Orders",     icon: ShoppingCart,    path: "/seller/orders" },
  { id: "products",  label: "Products",   icon: Package,         path: "/seller/products" },
  { id: "customers", label: "Customers",  icon: Users,           path: "/seller/customers" },
  { id: "settings",  label: "Settings",   icon: Settings,        path: "/seller/settings" },
];

interface SellerLayoutProps {
  children: ReactNode;
  activePage: string;
}

export default function SellerLayout({ children, activePage }: SellerLayoutProps) {
  const [, navigate] = useLocation();
  const [notifCount] = useState(3);

  return (
    <div className="flex h-screen bg-[#F7F8FA] overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 flex flex-col" style={{ background: '#0F172A' }}>
        {/* Brand */}
        <div className="h-14 flex items-center px-5 border-b border-white/5">
          <div className="w-7 h-7 rounded-md bg-indigo-600 flex items-center justify-center mr-2.5">
            <Store className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white" style={{ fontFamily: 'Sora, sans-serif' }}>OrderFlow</div>
            <div className="text-xs text-slate-500">Operations</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.id === "customers" || item.id === "settings") {
                    toast.info(`${item.label}`, { description: "Feature coming soon" });
                  } else {
                    navigate(item.path);
                  }
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all relative ${
                  isActive
                    ? "bg-indigo-600/15 text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-indigo-500 rounded-r-full" />
                )}
                <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-indigo-400' : ''}`} />
                <span style={{ fontFamily: 'DM Sans, sans-serif' }}>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-3 pb-4 space-y-0.5 border-t border-white/5 pt-3">
          <button
            onClick={() => navigate("/")}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Home</span>
          </button>
          <button
            onClick={() => toast.info("Logged out")}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-rose-400 hover:bg-white/5 transition-all"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>Seller</span>
            <span className="text-slate-300">/</span>
            <span className="text-slate-900 font-medium capitalize">{activePage}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="relative w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors"
              onClick={() => toast.info("Notifications", { description: `${notifCount} unread notifications` })}
            >
              <Bell className="w-4 h-4 text-slate-500" />
              {notifCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-rose-500 rounded-full" />
              )}
            </button>
            <div className="flex items-center gap-2 pl-3 border-l border-slate-200">
              <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center">
                <span className="text-xs font-semibold text-indigo-700">AR</span>
              </div>
              <span className="text-sm font-medium text-slate-700">Ahmed R.</span>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-[1280px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
