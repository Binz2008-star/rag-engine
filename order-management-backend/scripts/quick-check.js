#!/usr/bin/env node

/**
 * Quick Production Check
 * 
 * Fast verification of critical endpoints
 */

const PROD_URL = 'https://order-management-backend-one.vercel.app'

async function quickCheck() {
  console.log('🚀 Quick Production Check')
  console.log('========================\n')
  
  // Test 1: Health Check
  try {
    const healthResponse = await fetch(`${PROD_URL}/api/health`)
    console.log(`Health Check: ${healthResponse.status} ${healthResponse.statusText}`)
    
    if (healthResponse.ok) {
      const health = await healthResponse.json()
      console.log(`✅ Database: ${health.database}`)
      console.log(`✅ Status: ${health.status}`)
    } else {
      console.log('❌ Health check failed')
    }
  } catch (error) {
    console.log('❌ Health check error:', error.message)
  }
  
  console.log()
  
  // Test 2: Authentication
  try {
    const authResponse = await fetch(`${PROD_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'wrongpassword'
      })
    })
    
    console.log(`Auth Test: ${authResponse.status} ${authResponse.statusText}`)
    
    if (authResponse.status === 401) {
      console.log('✅ Authentication working (correctly rejects wrong password)')
    } else if (authResponse.status === 503) {
      console.log('❌ Authentication broken (503 Service Unavailable)')
      console.log('🚨 Environment variables missing in Vercel!')
    } else if (authResponse.status === 500) {
      console.log('❌ Authentication error (500 Internal Server Error)')
    } else {
      const data = await authResponse.json()
      console.log('Response:', data)
    }
  } catch (error) {
    console.log('❌ Authentication test error:', error.message)
  }
  
  console.log()
  
  // Test 3: Seed Endpoint
  try {
    const seedResponse = await fetch(`${PROD_URL}/api/admin/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: 'test-token' })
    })
    
    console.log(`Seed Test: ${seedResponse.status} ${seedResponse.statusText}`)
    
    if (seedResponse.ok) {
      console.log('✅ Seeding endpoint working')
    } else if (seedResponse.status === 401) {
      console.log('✅ Seeding endpoint working (correctly rejects invalid token)')
    } else if (seedResponse.status === 503) {
      console.log('❌ Seeding broken (503 Service Unavailable)')
    } else {
      const data = await seedResponse.json()
      console.log('Response:', data)
    }
  } catch (error) {
    console.log('❌ Seed test error:', error.message)
  }
  
  console.log('\n🎯 SUMMARY:')
  console.log('If you see 503 errors → Environment variables missing in Vercel')
  console.log('If you see 401/404 errors → System working, need proper credentials')
  console.log('If you see 200 errors → System fully functional')
  
  console.log('\n📋 NEXT ACTIONS:')
  console.log('1. Add environment variables to Vercel (see CRITICAL_ENV_SETUP.md)')
  console.log('2. Redeploy the application')
  console.log('3. Run this check again')
  console.log('4. Proceed with frontend development when working')
}

quickCheck().catch(console.error)
