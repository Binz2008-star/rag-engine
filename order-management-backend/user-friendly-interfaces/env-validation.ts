// Production environment validation
// This file validates that all required production environment variables are set

interface EnvValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
}

function looksLikePlaceholderSecret(value: string): boolean {
  const normalized = value.trim().toLowerCase()

  return normalized.includes('change-in-production')
    || normalized.includes('change-me')
    || normalized.includes('your-')
    || normalized.includes('replace-with-real')
}

export function validateProductionEnvironment(): EnvValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  // Required environment variables
  const required = [
    'JWT_SECRET',
    'NEXTAUTH_SECRET',
    'DATABASE_URL'
  ]

  const optional = [
    'STRIPE_WEBHOOK_SECRET',
    'WHATSAPP_WEBHOOK_SECRET',
    'CRON_SECRET',
    'CRON_RECONCILE_LIMIT'
  ]

  // Check required variables
  for (const envVar of required) {
    if (!process.env[envVar]) {
      errors.push(`Missing required environment variable: ${envVar}`)
    } else if (envVar.includes('SECRET') && process.env[envVar]!.length < 32) {
      errors.push(`${envVar} must be at least 32 characters for security`)
    } else if (envVar.includes('SECRET') && looksLikePlaceholderSecret(process.env[envVar]!)) {
      errors.push(`${envVar} cannot use a placeholder value`)
    }
  }

  // Check optional variables
  for (const envVar of optional) {
    if (!process.env[envVar]) {
      warnings.push(`Optional environment variable not set: ${envVar}`)
    }
  }

  // Production-specific hard requirements
  if (process.env.NODE_ENV === 'production') {
    // Redis is REQUIRED in production — in-memory fallback is not safe for multi-instance/serverless.
    // Each instance would have its own counter, making rate limits per-instance instead of global.
    const hasRedis = !!process.env.REDIS_URL || !!process.env.UPSTASH_REDIS_REST_URL
    if (!hasRedis) {
      errors.push(
        'REDIS_URL or UPSTASH_REDIS_REST_URL is required in production. ' +
        'In-memory rate limiting is not safe for multi-instance deployments. ' +
        'Set one of these environment variables before deploying.'
      )
    } else if (process.env.UPSTASH_REDIS_REST_URL && !process.env.UPSTASH_REDIS_REST_TOKEN) {
      errors.push('UPSTASH_REDIS_REST_TOKEN is required when UPSTASH_REDIS_REST_URL is configured')
    }

    if (process.env.DATABASE_URL?.includes('dev.db')) {
      errors.push('DATABASE_URL points to a development SQLite file. Use a PostgreSQL URL in production.')
    }

    if (!process.env.CRON_SECRET) {
      warnings.push('CRON_SECRET is not set - scheduled payment reconciliation endpoint will reject cron calls')
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings
  }
}

// Auto-validate on import in production
if (process.env.NODE_ENV === 'production') {
  const validation = validateProductionEnvironment()
  
  if (!validation.isValid) {
    process.stderr.write(
      JSON.stringify({
        level: 'ERROR',
        message: 'Production environment validation failed',
        errors: validation.errors,
      }) + '\n'
    )
    throw new Error(
      `Production environment validation failed:\n${validation.errors.map((e) => `  - ${e}`).join('\n')}`
    )
  }

  if (validation.warnings.length > 0) {
    process.stderr.write(
      JSON.stringify({
        level: 'WARN',
        message: 'Production environment warnings',
        warnings: validation.warnings,
      }) + '\n'
    )
  }
  
  process.stdout.write(JSON.stringify({ level: 'INFO', message: 'Production environment validation passed' }) + '\n')
}
