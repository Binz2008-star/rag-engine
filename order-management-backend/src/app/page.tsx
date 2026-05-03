'use client'

import Link from 'next/link'
import { useState } from 'react'

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  return (
    <main className="flex min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-slate-900/80 backdrop-blur-lg">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-indigo-500" />
              <span className="text-xl font-semibold text-white">OrderFlow</span>
            </div>
            <div className="flex items-center gap-4">
              {isLoggedIn ? (
                <>
                  <Link
                    href="/dashboard"
                    className="rounded-lg px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
                  >
                    Dashboard
                  </Link>
                  <button
                    onClick={() => setIsLoggedIn(false)}
                    className="rounded-lg px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <Link
                  href="/login"
                  className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600"
                >
                  Login
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="mx-auto flex w-full max-w-7xl flex-col justify-center gap-12 px-6 py-32 md:px-10">
        <div className="max-w-3xl space-y-8">
          <div className="inline-flex items-center rounded-full border border-indigo-400/30 bg-indigo-400/10 px-4 py-2 text-sm font-medium text-indigo-300">
            Order Management System
          </div>

          <div className="space-y-6">
            <h1 className="text-5xl font-semibold tracking-tight text-white md:text-7xl">
              Manage Orders
              <span className="block text-indigo-400">With Confidence</span>
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-300">
              A powerful order management platform for sellers. Track orders, manage products,
              and handle payments with ease.
            </p>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row">
            <Link
              href={isLoggedIn ? '/dashboard' : '/login'}
              className="inline-flex items-center justify-center rounded-xl bg-indigo-500 px-8 py-4 text-sm font-semibold text-white transition hover:bg-indigo-600"
            >
              {isLoggedIn ? 'Go to Dashboard' : 'Get Started'}
            </Link>
            <a
              className="inline-flex items-center justify-center rounded-xl border border-white/20 px-8 py-4 text-sm font-semibold text-white transition hover:bg-white/10"
              href="/api/health"
            >
              Check API Status
            </a>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid w-full max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <div className="mb-4 h-12 w-12 rounded-xl bg-indigo-500/20" />
            <h3 className="mb-2 text-lg font-semibold text-white">Order Tracking</h3>
            <p className="text-sm leading-6 text-slate-400">
              Track orders from creation to delivery with real-time status updates.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <div className="mb-4 h-12 w-12 rounded-xl bg-emerald-500/20" />
            <h3 className="mb-2 text-lg font-semibold text-white">Product Management</h3>
            <p className="text-sm leading-6 text-slate-400">
              Manage your product catalog with ease. Add, edit, and organize products.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <div className="mb-4 h-12 w-12 rounded-xl bg-amber-500/20" />
            <h3 className="mb-2 text-lg font-semibold text-white">Payment Processing</h3>
            <p className="text-sm leading-6 text-slate-400">
              Integrated payment processing with secure transaction handling.
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}
