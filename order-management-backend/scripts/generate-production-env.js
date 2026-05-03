#!/usr/bin/env node

/**
 * Production Environment Variable Generator
 *
 * Generates secure environment variables for production deployment.
 * Run this script to get properly configured environment variables.
 */

import crypto from 'crypto'

function generateSecureSecret(length = 64) {
  return crypto.randomBytes(length).toString('base64')
}

function generateSeedToken() {
  const timestamp = Date.now().toString()
  const random = crypto.randomBytes(32).toString('hex')
  return Buffer.from(`${timestamp}:${random}`).toString('base64')
}

console.log('🔐 PRODUCTION ENVIRONMENT VARIABLES\n')
console.log('⚠️  Copy these values to your Vercel environment variables:\n')

console.log('# JWT Secret for authentication')
console.log(`JWT_SECRET="${generateSecureSecret(64)}"`)
console.log()

console.log('# NextAuth configuration')
console.log(`NEXTAUTH_SECRET="${generateSecureSecret(64)}"`)
console.log(`NEXTAUTH_URL="https://your-domain.vercel.app"`)
console.log()

console.log('# Admin seed token for production seeding')
console.log(`ADMIN_SEED_TOKEN="${generateSeedToken()}"`)
console.log()

console.log('# Optional: Stripe webhook (configure in Stripe dashboard)')
console.log('STRIPE_WEBHOOK_SECRET="whsec_your_stripe_webhook_secret"')
console.log()

console.log('# Optional: WhatsApp webhook (configure in Meta Business Suite)')
console.log('WHATSAPP_WEBHOOK_SECRET="your_whatsapp_webhook_secret"')
console.log()

console.log('# Redis configuration for production rate limiting')
console.log('# Option 1: Standard Redis (recommended for self-hosted)')
console.log('# REDIS_URL="redis://user:pass@host:port"')
console.log()
console.log('# Option 2: Upstash Redis (recommended for Vercel)')
console.log('# UPSTASH_REDIS_REST_URL="https://your-upstash-redis-url.upstash.io"')
console.log('# UPSTASH_REDIS_REST_TOKEN="your-upstash-token"')
console.log()

console.log('🚨 CRITICAL REMINDERS:')
console.log('1. Replace "https://your-domain.vercel.app" with your actual domain')
console.log('2. Configure Redis for rate limiting (Upstash recommended for Vercel)')
console.log('3. Store these values securely - they cannot be recovered')
console.log('4. Update NEXTAUTH_URL after deployment')
console.log('5. Test the /api/admin/seed endpoint after deployment')
