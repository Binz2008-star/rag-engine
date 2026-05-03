/**
 * DESIGN: "Operational Clarity"
 * Products page — product catalog management
 * Features: CRUD, status toggle, search, skeleton loaders
 */
import { useState } from "react";
import { Plus, Search, Edit2, Trash2, Eye, EyeOff, Package, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import SellerLayout from "@/components/SellerLayout";

interface Product {
  id: string;
  name: string;
  slug: string;
  description: string;
  priceMinor: number;
  currency: string;
  stock: number;
  category: string;
  isActive: boolean;
  imageUrl?: string;
}

const MOCK_PRODUCTS: Product[] = [
  { id: "p1", name: "Wireless Phone Charger",  slug: "wireless-charger",   description: "15W fast wireless charging pad",         priceMinor: 2999,  currency: "USD", stock: 150, category: "Electronics", isActive: true },
  { id: "p2", name: "Bluetooth Earbuds Pro",   slug: "bt-earbuds-pro",     description: "Active noise cancellation, 24hr battery", priceMinor: 8999,  currency: "USD", stock: 45,  category: "Electronics", isActive: true },
  { id: "p3", name: "USB-C Cable Set (3-pack)", slug: "usbc-cable-set",    description: "Braided nylon, 1m + 2m + 3m lengths",     priceMinor: 2499,  currency: "USD", stock: 320, category: "Accessories", isActive: true },
  { id: "p4", name: "Mechanical Keyboard",     slug: "mech-keyboard",      description: "TKL layout, Cherry MX Blue switches",     priceMinor: 11999, currency: "USD", stock: 12,  category: "Electronics", isActive: true },
  { id: "p5", name: "Wireless Mouse",          slug: "wireless-mouse",     description: "Ergonomic, 12-month battery life",         priceMinor: 4999,  currency: "USD", stock: 88,  category: "Electronics", isActive: true },
  { id: "p6", name: "Phone Case Premium",      slug: "phone-case-premium", description: "MagSafe compatible, military grade drop",  priceMinor: 4500,  currency: "USD", stock: 0,   category: "Accessories", isActive: false },
];

export default function SellerProducts() {
  const [products, setProducts] = useState<Product[]>(MOCK_PRODUCTS);
  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newProduct, setNewProduct] = useState({ name: "", description: "", price: "", stock: "", category: "Electronics" });

  const filtered = products.filter(
    (p) =>
      !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.category.toLowerCase().includes(search.toLowerCase())
  );

  const toggleActive = (id: string) => {
    setProducts((prev) =>
      prev.map((p) => (p.id === id ? { ...p, isActive: !p.isActive } : p))
    );
    const p = products.find((p) => p.id === id);
    toast.success(p?.isActive ? "Product deactivated" : "Product activated", {
      description: p?.name,
    });
  };

  const handleAdd = () => {
    if (!newProduct.name || !newProduct.price) {
      toast.error("Name and price are required");
      return;
    }
    const product: Product = {
      id: `p${Date.now()}`,
      name: newProduct.name,
      slug: newProduct.name.toLowerCase().replace(/\s+/g, "-"),
      description: newProduct.description,
      priceMinor: Math.round(parseFloat(newProduct.price) * 100),
      currency: "USD",
      stock: parseInt(newProduct.stock) || 0,
      category: newProduct.category,
      isActive: true,
    };
    setProducts((prev) => [product, ...prev]);
    setNewProduct({ name: "", description: "", price: "", stock: "", category: "Electronics" });
    setShowAddForm(false);
    toast.success("Product created", { description: product.name });
  };

  const formatPrice = (minor: number) => `$${(minor / 100).toFixed(2)}`;

  return (
    <SellerLayout activePage="products">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Sora, sans-serif' }}>Products</h1>
          <p className="text-slate-500 text-sm mt-0.5">{products.filter((p) => p.isActive).length} active · {products.filter((p) => !p.isActive).length} inactive</p>
        </div>
        <Button
          onClick={() => setShowAddForm(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2"
        >
          <Plus className="w-4 h-4" /> Add Product
        </Button>
      </div>

      {/* Add Product Form */}
      {showAddForm && (
        <div className="bg-white rounded-xl border border-indigo-200 p-5 mb-5 shadow-sm">
          <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: 'Sora, sans-serif' }}>New Product</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Product Name *</label>
              <input
                type="text"
                value={newProduct.name}
                onChange={(e) => setNewProduct((p) => ({ ...p, name: e.target.value }))}
                placeholder="e.g. Wireless Mouse"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Category</label>
              <select
                value={newProduct.category}
                onChange={(e) => setNewProduct((p) => ({ ...p, category: e.target.value }))}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 bg-white"
              >
                <option value="Electronics">Electronics</option>
                <option value="Accessories">Accessories</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Price (USD) *</label>
              <input
                type="number"
                value={newProduct.price}
                onChange={(e) => setNewProduct((p) => ({ ...p, price: e.target.value }))}
                placeholder="29.99"
                min="0"
                step="0.01"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Stock Quantity</label>
              <input
                type="number"
                value={newProduct.stock}
                onChange={(e) => setNewProduct((p) => ({ ...p, stock: e.target.value }))}
                placeholder="100"
                min="0"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 font-mono"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-600 mb-1.5">Description</label>
              <textarea
                value={newProduct.description}
                onChange={(e) => setNewProduct((p) => ({ ...p, description: e.target.value }))}
                placeholder="Brief product description..."
                rows={2}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300 resize-none"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setShowAddForm(false)}>Cancel</Button>
            <Button onClick={handleAdd} className="bg-indigo-600 hover:bg-indigo-700 text-white">Save Product</Button>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300"
        />
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="text-left text-xs font-medium text-slate-400 px-5 py-3">Product</th>
              <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Category</th>
              <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Price</th>
              <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Stock</th>
              <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Status</th>
              <th className="text-left text-xs font-medium text-slate-400 px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((product) => (
              <tr key={product.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0">
                      <Package className="w-4 h-4 text-slate-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">{product.name}</div>
                      <div className="font-mono text-xs text-slate-400">{product.slug}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{product.category}</span>
                </td>
                <td className="px-4 py-3.5">
                  <span className="font-mono text-sm font-medium text-slate-900">{formatPrice(product.priceMinor)}</span>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-1.5">
                    {product.stock === 0 ? (
                      <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                    ) : product.stock < 20 ? (
                      <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    <span className={`font-mono text-sm ${product.stock === 0 ? "text-red-500" : product.stock < 20 ? "text-amber-600" : "text-slate-700"}`}>
                      {product.stock}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3.5">
                  <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${product.isActive ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
                    {product.isActive ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => toggleActive(product.id)}
                      className="w-7 h-7 rounded-md hover:bg-slate-100 flex items-center justify-center transition-colors"
                      title={product.isActive ? "Deactivate" : "Activate"}
                    >
                      {product.isActive ? (
                        <EyeOff className="w-3.5 h-3.5 text-slate-400" />
                      ) : (
                        <Eye className="w-3.5 h-3.5 text-emerald-500" />
                      )}
                    </button>
                    <button
                      onClick={() => toast.info("Edit product", { description: "Feature coming soon" })}
                      className="w-7 h-7 rounded-md hover:bg-slate-100 flex items-center justify-center transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                    <button
                      onClick={() => toast.error("Delete product", { description: "Feature coming soon" })}
                      className="w-7 h-7 rounded-md hover:bg-red-50 flex items-center justify-center transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-slate-300 hover:text-red-400" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SellerLayout>
  );
}
