#!/usr/bin/env node

/**
 * Production Verification Script
 *
 * Verifies that all critical production systems are functioning correctly.
 * Run this after deployment to ensure the system is production-safe.
 */


const PRODUCTION_URL = process.env.PROD_URL || 'https://order-management-backend-one.vercel.app'

interface TestResult {
  name: string
  status: 'PASS' | 'FAIL' | 'SKIP'
  message: string
  duration?: number
}

class ProductionVerifier {
  private results: TestResult[] = []

  private async testEndpoint(path: string, options?: RequestInit): Promise<Response> {
    const url = `${PRODUCTION_URL}${path}`
    const start = Date.now()

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers
        }
      })

      this.results.push({
        name: `HTTP ${options?.method || 'GET'} ${path}`,
        status: response.ok ? 'PASS' : 'FAIL',
        message: `${response.status} ${response.statusText}`,
        duration: Date.now() - start
      })

      return response
    } catch (error) {
      this.results.push({
        name: `HTTP ${options?.method || 'GET'} ${path}`,
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error',
        duration: Date.now() - start
      })

      throw error
    }
  }

  private async testAuthentication() {
    console.log('🔐 Testing Authentication System')

    try {
      // Test login endpoint
      const loginResponse = await this.testEndpoint('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: 'admin@company.com',
          password: 'admin123!@#'
        })
      })

      if (loginResponse.ok) {
        const data = await loginResponse.json()

        if (data.token) {
          this.results.push({
            name: 'JWT Token Generation',
            status: 'PASS',
            message: 'Token generated successfully'
          })

          // Test token validation
          await this.testEndpoint('/api/auth/me', {
            headers: {
              'Authorization': `Bearer ${data.token}`
            }
          })

          return data.token
        } else {
          this.results.push({
            name: 'JWT Token Generation',
            status: 'FAIL',
            message: 'No token in response'
          })
        }
      }
    } catch (error) {
      this.results.push({
        name: 'Authentication Flow',
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    }

    return null
  }

  private async testSeeding(token: string | null) {
    console.log('🌱 Testing Database Seeding')

    try {
      const headers: Record<string, string> = {}

      if (process.env.ADMIN_SEED_TOKEN) {
        headers['Authorization'] = `Bearer ${process.env.ADMIN_SEED_TOKEN}`
      } else if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const seedResponse = await this.testEndpoint('/api/admin/seed', {
        method: 'POST',
        headers
      })

      if (seedResponse.ok) {
        const data = await seedResponse.json()

        this.results.push({
          name: 'Database Seeding',
          status: 'PASS',
          message: `Created: ${JSON.stringify(data.created)}`
        })
      } else {
        const errorData = await seedResponse.json().catch(() => ({}))
        this.results.push({
          name: 'Database Seeding',
          status: 'FAIL',
          message: errorData.error || 'Seeding failed'
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Database Seeding',
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async testRateLimiting() {
    console.log('⚡ Testing Rate Limiting')

    try {
      // Test multiple rapid requests to trigger rate limiting
      const promises = Array.from({ length: 10 }, () =>
        this.testEndpoint('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: 'test@example.com',
            password: 'wrongpassword'
          })
        })
      )

      const responses = await Promise.all(promises)
      const rateLimited = responses.some(r => r.status === 429)

      if (rateLimited) {
        this.results.push({
          name: 'Rate Limiting',
          status: 'PASS',
          message: 'Rate limiting is working (429 responses detected)'
        })
      } else {
        this.results.push({
          name: 'Rate Limiting',
          status: 'FAIL',
          message: 'No rate limiting detected (possible misconfiguration)'
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Rate Limiting',
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async testDatabaseConnectivity() {
    console.log('🗄️ Testing Database Connectivity')

    try {
      const response = await this.testEndpoint('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: 'nonexistent@example.com',
          password: 'testpassword'
        })
      })

      // Should get 401, not 500, indicating database is reachable
      if (response.status === 401) {
        this.results.push({
          name: 'Database Connectivity',
          status: 'PASS',
          message: 'Database is reachable and responding'
        })
      } else if (response.status >= 500) {
        this.results.push({
          name: 'Database Connectivity',
          status: 'FAIL',
          message: `Database error: ${response.status}`
        })
      } else {
        this.results.push({
          name: 'Database Connectivity',
          status: 'PASS',
          message: `Application responding (${response.status})`
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Database Connectivity',
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  private async testOrderFlow(token: string | null) {
    console.log('📦 Testing Order Flow')

    if (!token) {
      this.results.push({
        name: 'Order Flow',
        status: 'SKIP',
        message: 'No authentication token available'
      })
      return
    }

    try {
      // Test order creation
      const orderResponse = await this.testEndpoint('/api/orders', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          customerId: 'test-customer',
          items: [
            {
              productId: 'test-product',
              quantity: 1
            }
          ],
          paymentType: 'CASH_ON_DELIVERY'
        })
      })

      if (orderResponse.ok) {
        this.results.push({
          name: 'Order Creation',
          status: 'PASS',
          message: 'Order creation endpoint responding'
        })
      } else {
        const errorData = await orderResponse.json().catch(() => ({}))
        this.results.push({
          name: 'Order Creation',
          status: 'FAIL',
          message: errorData.error || 'Order creation failed'
        })
      }
    } catch (error) {
      this.results.push({
        name: 'Order Flow',
        status: 'FAIL',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  async runFullVerification() {
    console.log(`🚀 Starting Production Verification for ${PRODUCTION_URL}\n`)

    const startTime = Date.now()

    // Run all tests
    await this.testDatabaseConnectivity()
    console.log()

    const authToken = await this.testAuthentication()
    console.log()

    await this.testSeeding(authToken)
    console.log()

    await this.testRateLimiting()
    console.log()

    await this.testOrderFlow(authToken)
    console.log()

    // Generate report
    this.generateReport(Date.now() - startTime)
  }

  private generateReport(totalDuration: number) {
    const passed = this.results.filter(r => r.status === 'PASS').length
    const failed = this.results.filter(r => r.status === 'FAIL').length
    const skipped = this.results.filter(r => r.status === 'SKIP').length

    console.log('📊 PRODUCTION VERIFICATION REPORT')
    console.log('='.repeat(50))
    console.log(`Total Tests: ${this.results.length}`)
    console.log(`✅ Passed: ${passed}`)
    console.log(`❌ Failed: ${failed}`)
    console.log(`⏭️ Skipped: ${skipped}`)
    console.log(`⏱️ Duration: ${totalDuration}ms`)
    console.log()

    console.log('DETAILED RESULTS:')
    console.log('-'.repeat(50))

    this.results.forEach(result => {
      const icon = result.status === 'PASS' ? '✅' : result.status === 'FAIL' ? '❌' : '⏭️'
      const duration = result.duration ? ` (${result.duration}ms)` : ''
      console.log(`${icon} ${result.name}${duration}`)
      console.log(`   ${result.message}`)
      console.log()
    })

    // Critical assessment
    const criticalFailures = this.results.filter(r =>
      r.status === 'FAIL' && (
        r.name.includes('Authentication') ||
        r.name.includes('Database') ||
        r.name.includes('Seeding')
      )
    )

    if (criticalFailures.length > 0) {
      console.log('🚨 CRITICAL ISSUES FOUND:')
      console.log('The system is NOT production-safe!')
      criticalFailures.forEach(failure => {
        console.log(`❌ ${failure.name}: ${failure.message}`)
      })
      console.log()
      console.log('🎯 REQUIRED ACTIONS:')
      console.log('1. Fix environment variables in Vercel dashboard')
      console.log('2. Redeploy the application')
      console.log('3. Run this verification script again')
      console.log('4. Only proceed with frontend development after ALL critical tests pass')
    } else if (failed > 0) {
      console.log('⚠️ NON-CRITICAL ISSUES FOUND:')
      console.log('System is functional but needs optimization')
    } else {
      console.log('🎉 PRODUCTION READY!')
      console.log('All critical systems are functioning correctly')
      console.log('You can proceed with frontend development')
    }
  }
}

// Run verification if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const verifier = new ProductionVerifier()
  verifier.runFullVerification().catch(console.error)
}

// Always run when executed
const verifier = new ProductionVerifier()
verifier.runFullVerification().catch(console.error)

export { ProductionVerifier }
