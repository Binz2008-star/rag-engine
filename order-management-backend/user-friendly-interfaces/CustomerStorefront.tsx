/**
 * DESIGN: "Operational Clarity" — Customer-facing variant
 * Public storefront: mobile-first, no login required
 * Features: product grid, cart, checkout flow, order confirmation
 */
import { useState } from "react";
import { useLocation } from "wouter";
import {
  ShoppingCart, Plus, Minus, X, ArrowLeft, ArrowRight,
  CheckCircle2, Package, Truck, MapPin, Phone, User, ChevronLeft
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const STOREFRONT_IMG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663052390397/mTfbMJ8gX2qEDAanKjCPFK/hero-storefront-mr2pWw736WR8xdmx88nBHS.webp";

const PRODUCTS = [
  { id: "p1", name: "Wireless Phone Charger",   price: 2999,  stock: 150, emoji: "🔋", desc: "15W fast wireless charging" },
  { id: "p2", name: "Bluetooth Earbuds Pro",    price: 8999,  stock: 45,  emoji: "🎧", desc: "ANC, 24hr battery life" },
  { id: "p3", name: "USB-C Cable Set (3-pack)", price: 2499,  stock: 320, emoji: "🔌", desc: "Braided nylon, 1m/2m/3m" },
  { id: "p4", name: "Wireless Mouse",           price: 4999,  stock: 88,  emoji: "🖱️", desc: "Ergonomic, 12-month battery" },
  { id: "p5", name: "Phone Case Premium",       price: 4500,  stock: 200, emoji: "📱", desc: "MagSafe compatible" },
  { id: "p6", name: "Smart Watch Band",         price: 8999,  stock: 60,  emoji: "⌚", desc: "Silicone, multiple colors" },
];

type Step = "browse" | "cart" | "checkout" | "confirmation";

interface CartItem {
  id: string;
  name: string;
  price: number;
  qty: number;
  emoji: string;
}

interface CheckoutForm {
  name: string;
  phone: string;
  address: string;
  notes: string;
}

const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;

export default function CustomerStorefront() {
  const [, navigate] = useLocation();
  const [step, setStep] = useState<Step>("browse");
  const [cart, setCart] = useState<CartItem[]>([]);
  const [form, setForm] = useState<CheckoutForm>({ name: "", phone: "", address: "", notes: "" });
  const [errors, setErrors] = useState<Partial<CheckoutForm>>({});
  const [orderNumber] = useState(() => `ORD-${Math.floor(Math.random() * 9000 + 1000)}`);

  const cartCount = cart.reduce((s, i) => s + i.qty, 0);
  const cartTotal = cart.reduce((s, i) => s + i.price * i.qty, 0);

  const addToCart = (product: typeof PRODUCTS[0]) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.id === product.id);
      if (existing) {
        return prev.map((i) => i.id === product.id ? { ...i, qty: i.qty + 1 } : i);
      }
      return [...prev, { id: product.id, name: product.name, price: product.price, qty: 1, emoji: product.emoji }];
    });
    toast.success("Added to cart", { description: product.name });
  };

  const updateQty = (id: string, delta: number) => {
    setCart((prev) => {
      const updated = prev.map((i) => i.id === id ? { ...i, qty: Math.max(0, i.qty + delta) } : i);
      return updated.filter((i) => i.qty > 0);
    });
  };

  const validate = () => {
    const e: Partial<CheckoutForm> = {};
    if (!form.name.trim()) e.name = "Name is required";
    if (!form.phone.trim()) e.phone = "Phone number is required";
    else if (!/^\+?[\d\s\-()]{8,}$/.test(form.phone)) e.phone = "Enter a valid phone number";
    if (!form.address.trim()) e.address = "Delivery address is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handlePlaceOrder = () => {
    if (!validate()) return;
    setStep("confirmation");
  };

  return (
    <div className="min-h-screen bg-[#F7F8FA]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => navigate("/")} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center">
              <ChevronLeft className="w-4 h-4 text-slate-500" />
            </button>
            <div>
              <div className="font-semibold text-slate-900 text-sm" style={{ fontFamily: 'Sora, sans-serif' }}>Tech Gadgets Plus</div>
              <div className="text-xs text-emerald-600 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                Open now
              </div>
            </div>
          </div>
          {step === "browse" && (
            <button
              onClick={() => cartCount > 0 ? setStep("cart") : toast.info("Your cart is empty")}
              className="relative w-9 h-9 rounded-xl bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"
            >
              <ShoppingCart className="w-4.5 h-4.5 text-slate-700" />
              {cartCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-indigo-600 text-white text-xs rounded-full flex items-center justify-center font-medium">
                  {cartCount}
                </span>
              )}
            </button>
          )}
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* STEP: Browse */}
        {step === "browse" && (
          <>
            <div className="mb-5">
              <h1 className="text-xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Products</h1>
              <p className="text-sm text-slate-500 mt-0.5">{PRODUCTS.length} items available</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {PRODUCTS.map((product) => {
                const inCart = cart.find((i) => i.id === product.id);
                return (
                  <div key={product.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md hover:shadow-slate-100 transition-all">
                    <div className="h-28 bg-slate-50 flex items-center justify-center text-4xl">
                      {product.emoji}
                    </div>
                    <div className="p-3">
                      <div className="text-sm font-medium text-slate-900 leading-tight mb-0.5">{product.name}</div>
                      <div className="text-xs text-slate-400 mb-2">{product.desc}</div>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-bold text-slate-900">{formatPrice(product.price)}</span>
                        {inCart ? (
                          <div className="flex items-center gap-1.5">
                            <button onClick={() => updateQty(product.id, -1)} className="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center hover:bg-slate-200">
                              <Minus className="w-3 h-3 text-slate-600" />
                            </button>
                            <span className="font-mono text-xs font-semibold text-slate-900 w-4 text-center">{inCart.qty}</span>
                            <button onClick={() => updateQty(product.id, 1)} className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center hover:bg-indigo-700">
                              <Plus className="w-3 h-3 text-white" />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => addToCart(product)}
                            className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center hover:bg-indigo-700 transition-colors"
                          >
                            <Plus className="w-3.5 h-3.5 text-white" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {cartCount > 0 && (
              <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-sm px-4">
                <button
                  onClick={() => setStep("cart")}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl py-3.5 flex items-center justify-between px-5 shadow-lg shadow-indigo-200 transition-colors"
                >
                  <span className="bg-indigo-500 text-white text-xs font-bold w-6 h-6 rounded-lg flex items-center justify-center">{cartCount}</span>
                  <span className="font-semibold text-sm">View Cart</span>
                  <span className="font-mono font-bold text-sm">{formatPrice(cartTotal)}</span>
                </button>
              </div>
            )}
          </>
        )}

        {/* STEP: Cart */}
        {step === "cart" && (
          <>
            <div className="flex items-center gap-3 mb-5">
              <button onClick={() => setStep("browse")} className="w-8 h-8 rounded-lg hover:bg-slate-200 flex items-center justify-center">
                <ArrowLeft className="w-4 h-4 text-slate-600" />
              </button>
              <h1 className="text-xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Your Cart</h1>
            </div>
            {cart.length === 0 ? (
              <div className="text-center py-16 text-slate-400">
                <ShoppingCart className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Your cart is empty</p>
                <button onClick={() => setStep("browse")} className="mt-3 text-indigo-600 text-sm font-medium">Browse products</button>
              </div>
            ) : (
              <>
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden mb-4">
                  {cart.map((item, i) => (
                    <div key={item.id} className={`flex items-center gap-3 px-4 py-3.5 ${i < cart.length - 1 ? "border-b border-slate-100" : ""}`}>
                      <div className="w-10 h-10 rounded-lg bg-slate-50 flex items-center justify-center text-xl flex-shrink-0">{item.emoji}</div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-slate-900 truncate">{item.name}</div>
                        <div className="font-mono text-xs text-slate-500">{formatPrice(item.price)} each</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => updateQty(item.id, -1)} className="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center hover:bg-slate-200">
                          <Minus className="w-3 h-3 text-slate-600" />
                        </button>
                        <span className="font-mono text-sm font-semibold text-slate-900 w-5 text-center">{item.qty}</span>
                        <button onClick={() => updateQty(item.id, 1)} className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center hover:bg-indigo-700">
                          <Plus className="w-3 h-3 text-white" />
                        </button>
                      </div>
                      <span className="font-mono text-sm font-bold text-slate-900 w-16 text-right">{formatPrice(item.price * item.qty)}</span>
                    </div>
                  ))}
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-slate-500">Subtotal</span>
                    <span className="font-mono font-medium text-slate-900">{formatPrice(cartTotal)}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-3">
                    <span className="text-slate-500">Delivery</span>
                    <span className="font-mono text-emerald-600 font-medium">Free</span>
                  </div>
                  <div className="flex justify-between font-semibold border-t border-slate-100 pt-3">
                    <span className="text-slate-900">Total</span>
                    <span className="font-mono text-slate-900">{formatPrice(cartTotal)}</span>
                  </div>
                </div>
                <Button onClick={() => setStep("checkout")} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white gap-2 py-3">
                  Proceed to Checkout <ArrowRight className="w-4 h-4" />
                </Button>
              </>
            )}
          </>
        )}

        {/* STEP: Checkout */}
        {step === "checkout" && (
          <>
            <div className="flex items-center gap-3 mb-5">
              <button onClick={() => setStep("cart")} className="w-8 h-8 rounded-lg hover:bg-slate-200 flex items-center justify-center">
                <ArrowLeft className="w-4 h-4 text-slate-600" />
              </button>
              <h1 className="text-xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Checkout</h1>
            </div>
            <div className="space-y-4 mb-5">
              <div>
                <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600 mb-1.5">
                  <User className="w-3.5 h-3.5" /> Full Name *
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => { setForm((f) => ({ ...f, name: e.target.value })); setErrors((e2) => ({ ...e2, name: "" })); }}
                  placeholder="Ahmed Al-Rashidi"
                  className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 ${errors.name ? "border-red-300 bg-red-50" : "border-slate-200"}`}
                />
                {errors.name && <p className="text-xs text-red-500 mt-1 flex items-center gap-1"><X className="w-3 h-3" />{errors.name}</p>}
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600 mb-1.5">
                  <Phone className="w-3.5 h-3.5" /> Phone Number *
                </label>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => { setForm((f) => ({ ...f, phone: e.target.value })); setErrors((e2) => ({ ...e2, phone: "" })); }}
                  placeholder="+966 50 123 4567"
                  className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 font-mono ${errors.phone ? "border-red-300 bg-red-50" : "border-slate-200"}`}
                />
                {errors.phone && <p className="text-xs text-red-500 mt-1 flex items-center gap-1"><X className="w-3 h-3" />{errors.phone}</p>}
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600 mb-1.5">
                  <MapPin className="w-3.5 h-3.5" /> Delivery Address *
                </label>
                <textarea
                  value={form.address}
                  onChange={(e) => { setForm((f) => ({ ...f, address: e.target.value })); setErrors((e2) => ({ ...e2, address: "" })); }}
                  placeholder="Street, building, city..."
                  rows={2}
                  className={`w-full px-3 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 resize-none ${errors.address ? "border-red-300 bg-red-50" : "border-slate-200"}`}
                />
                {errors.address && <p className="text-xs text-red-500 mt-1 flex items-center gap-1"><X className="w-3 h-3" />{errors.address}</p>}
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">Order Notes (optional)</label>
                <input
                  type="text"
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="e.g. Please deliver after 5 PM"
                  className="w-full px-3 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>
            </div>
            <div className="bg-slate-50 rounded-xl p-4 mb-5 border border-slate-200">
              <div className="text-xs font-medium text-slate-500 mb-2">Order Summary</div>
              {cart.map((item) => (
                <div key={item.id} className="flex justify-between text-sm mb-1">
                  <span className="text-slate-700">{item.name} × {item.qty}</span>
                  <span className="font-mono text-slate-900">{formatPrice(item.price * item.qty)}</span>
                </div>
              ))}
              <div className="flex justify-between font-semibold text-sm border-t border-slate-200 pt-2 mt-2">
                <span>Total</span>
                <span className="font-mono">{formatPrice(cartTotal)}</span>
              </div>
            </div>
            <Button onClick={handlePlaceOrder} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white gap-2 py-3">
              Place Order (Cash on Delivery) <CheckCircle2 className="w-4 h-4" />
            </Button>
          </>
        )}

        {/* STEP: Confirmation */}
        {step === "confirmation" && (
          <div className="text-center py-10">
            <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-emerald-600" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-1" style={{ fontFamily: 'Sora, sans-serif' }}>Order Placed!</h2>
            <p className="text-slate-500 text-sm mb-4">Your order has been received and is being processed.</p>
            <div className="bg-white rounded-xl border border-slate-200 p-5 text-left mb-5 max-w-sm mx-auto">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500">Order Number</span>
                <span className="font-mono text-sm font-bold text-slate-900">{orderNumber}</span>
              </div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500">Customer</span>
                <span className="text-sm text-slate-800">{form.name}</span>
              </div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-slate-500">Total</span>
                <span className="font-mono text-sm font-bold text-slate-900">{formatPrice(cartTotal)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Status</span>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">Pending</span>
              </div>
            </div>
            <div className="flex flex-col gap-2 max-w-sm mx-auto">
              <div className="flex items-center gap-3 bg-slate-50 rounded-xl p-3 text-left">
                <Package className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                <span className="text-xs text-slate-600">Seller will confirm your order shortly</span>
              </div>
              <div className="flex items-center gap-3 bg-slate-50 rounded-xl p-3 text-left">
                <Truck className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <span className="text-xs text-slate-600">You'll receive delivery updates via WhatsApp</span>
              </div>
            </div>
            <button onClick={() => navigate("/")} className="mt-6 text-indigo-600 text-sm font-medium">
              ← Back to Home
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
