'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

interface Order {
  id: string
  publicOrderNumber: string
  status: string
  paymentStatus: string
  totalMinor: number
  currency: string
  createdAt: string
  customer: {
    name: string
    phone: string
  }
}

export default function DashboardPage() {
  const router = useRouter()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
      return
    }

    fetchOrders(token)
  }, [router])

  const fetchOrders = async (token: string) => {
    try {
      const response = await fetch('/api/seller/orders', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Failed to fetch orders')
      }

      const data = await response.json()
      setOrders(data.orders || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch orders')
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/')
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PENDING':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30'
      case 'CONFIRMED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
      case 'PACKED':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30'
      case 'OUT_FOR_DELIVERY':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30'
      case 'DELIVERED':
        return 'bg-green-500/20 text-green-300 border-green-500/30'
      case 'CANCELLED':
        return 'bg-red-500/20 text-red-300 border-red-500/30'
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/30'
    }
  }

  const formatPrice = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount / 100)
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-slate-900/80 backdrop-blur-lg">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-indigo-500" />
              <span className="text-xl font-semibold text-white">OrderFlow</span>
            </div>
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="rounded-lg px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
              >
                Home
              </Link>
              <button
                onClick={handleLogout}
                className="rounded-lg px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Dashboard Content */}
      <section className="mx-auto max-w-7xl px-6 py-32 md:px-10">
        <div className="mb-8">
          <h1 className="text-4xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-slate-400">Manage your orders and track their status</p>
        </div>

        {/* Stats Cards */}
        <div className="mb-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <p className="text-sm font-medium text-slate-400">Total Orders</p>
            <p className="mt-2 text-3xl font-semibold text-white">{orders.length}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <p className="text-sm font-medium text-slate-400">Pending</p>
            <p className="mt-2 text-3xl font-semibold text-amber-400">
              {orders.filter(o => o.status === 'PENDING').length}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <p className="text-sm font-medium text-slate-400">Confirmed</p>
            <p className="mt-2 text-3xl font-semibold text-emerald-400">
              {orders.filter(o => o.status === 'CONFIRMED').length}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <p className="text-sm font-medium text-slate-400">Delivered</p>
            <p className="mt-2 text-3xl font-semibold text-green-400">
              {orders.filter(o => o.status === 'DELIVERED').length}
            </p>
          </div>
        </div>

        {/* Orders Table */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm">
          <div className="border-b border-white/10 px-6 py-4">
            <h2 className="text-lg font-semibold text-white">Recent Orders</h2>
          </div>

          {loading ? (
            <div className="p-6 text-center text-slate-400">Loading orders...</div>
          ) : error ? (
            <div className="p-6 text-center text-red-400">{error}</div>
          ) : orders.length === 0 ? (
            <div className="p-6 text-center text-slate-400">No orders found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10 text-left text-sm font-medium text-slate-400">
                    <th className="px-6 py-4">Order #</th>
                    <th className="px-6 py-4">Customer</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Payment</th>
                    <th className="px-6 py-4">Total</th>
                    <th className="px-6 py-4">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id} className="border-b border-white/10 text-sm text-white">
                      <td className="px-6 py-4 font-mono">{order.publicOrderNumber}</td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium">{order.customer.name}</p>
                          <p className="text-slate-400">{order.customer.phone}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${getStatusColor(order.status)}`}>
                          {order.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${
                          order.paymentStatus === 'COMPLETED'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        }`}>
                          {order.paymentStatus}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono">{formatPrice(order.totalMinor, order.currency)}</td>
                      <td className="px-6 py-4 text-slate-400">
                        {new Date(order.createdAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
