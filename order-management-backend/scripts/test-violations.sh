#!/bin/bash

# L1 Violation Test Script
# Purpose: Test hardened enforcement by creating intentional violations

set -e

echo "=== L1 Violation Testing Script ==="
echo "This script creates intentional violations to test enforcement"

# Backup original files
echo "Creating backups..."
cp -r src/app src/app.backup
cp -r src/server src/server.backup

VIOLATION_TEST_BRANCH="test/l1-violations-$(date +%s)"
VIOLATIONS_CREATED=0

# Create test branch
echo "Creating test branch: $VIOLATION_TEST_BRANCH"
git checkout -b "$VIOLATION_TEST_BRANCH" 2>/dev/null || git checkout -b "$VIOLATION_TEST_BRANCH"

# === Test 1: Cross-Domain Import Violation ===
echo "## Test 1: Cross-Domain Import Violation"
cat > src/app/api/test-cross-domain/route.ts << 'EOF'
import { Request, Response } from 'next'
import { someServerFunction } from '../../../server/lib/auth'

export async function GET(request: Request) {
  // VIOLATION: Importing from server layer
  const result = await someServerFunction()
  return Response.json({ message: 'Cross-domain import test', result })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created cross-domain import violation"

# === Test 2: Schema Duplication Violation ===
echo "## Test 2: Schema Duplication Violation"
cat > src/app/test-schema.prisma << 'EOF'
// VIOLATION: Schema file outside prisma/ directory
model User {
  id    String @id @default(cuid())
  email String @unique
  name  String
}

model DuplicateModel {
  id String @id @default(cuid())
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created schema duplication violation"

# === Test 3: Auth Logic Violation ===
echo "## Test 3: Auth Logic Violation"
cat > src/app/api/test-auth/route.ts << 'EOF'
import { Request, Response } from 'next'
import bcrypt from 'bcrypt'
import jwt from 'jsonwebtoken'

export async function POST(request: Request) {
  const { password } = await request.json()
  
  // VIOLATION: Auth logic in API route
  const hashedPassword = await bcrypt.hash(password, 10)
  const token = jwt.sign({ hashedPassword }, 'secret')
  
  return Response.json({ token, hashedPassword })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created auth logic violation"

# === Test 4: Rate Limiting Violation ===
echo "## Test 4: Rate Limiting Violation"
cat > src/app/api/test-rate-limit/route.ts << 'EOF'
import { Request, Response } from 'next'

// VIOLATION: In-memory rate limiting
const rateLimitMap = new Map<string, { count: number; resetTime: number }>()

export async function GET(request: Request) {
  const clientId = request.headers.get('x-client-id') || 'anonymous'
  const now = Date.now()
  const windowMs = 60000 // 1 minute
  const maxRequests = 100
  
  const clientData = rateLimitMap.get(clientId)
  
  if (!clientData || now > clientData.resetTime) {
    rateLimitMap.set(clientId, { count: 1, resetTime: now + windowMs })
  } else if (clientData.count < maxRequests) {
    clientData.count++
  } else {
    return Response.json({ error: 'Rate limit exceeded' }, { status: 429 })
  }
  
  return Response.json({ message: 'Rate limit test' })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created rate limiting violation"

# === Test 5: Environment Variable Violation ===
echo "## Test 5: Environment Variable Violation"
cat > src/app/api/test-env/route.ts << 'EOF'
import { Request, Response } from 'next'

export async function GET(request: Request) {
  // VIOLATION: Direct process.env usage
  const dbUrl = process.env.DATABASE_URL
  const jwtSecret = process.env.JWT_SECRET || 'fallback-secret'
  const hardcodedSecret = 'super-secret-key-that-is-way-too-long'
  
  return Response.json({ 
    dbConfigured: !!dbUrl,
    jwtConfigured: !!jwtSecret,
    hasHardcodedSecret: hardcodedSecret.length > 20
  })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created environment variable violation"

# === Test 6: Password Handling Violation ===
echo "## Test 6: Password Handling Violation"
cat > src/app/api/test-password/route.ts << 'EOF'
import { Request, Response } from 'next'
import crypto from 'crypto'

export async function POST(request: Request) {
  const { password } = await request.json()
  
  // VIOLATION: Password hashing in API route
  const salt = crypto.randomBytes(16).toString('hex')
  const hash = crypto.pbkdf2Sync(password, salt, 10000, 64, 'sha512').toString('hex')
  
  // Another violation pattern
  const passwordHash = `hash_${password}_salt_${salt}`
  
  return Response.json({ hash, passwordHash, salt })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created password handling violation"

# === Test 7: Session Management Violation ===
echo "## Test 7: Session Management Violation"
cat > src/app/api/test-session/route.ts << 'EOF'
import { Request, Response } from 'next'

// VIOLATION: Session management in API route
const sessionStore = new Map<string, { data: any; expires: number }>()

export async function POST(request: Request) {
  const { sessionId, data } = await request.json()
  
  const expires = Date.now() + (24 * 60 * 60 * 1000) // 24 hours
  sessionStore.set(sessionId, { data, expires })
  
  return Response.json({ message: 'Session stored', sessionId })
}

export async function GET(request: Request) {
  const sessionId = request.nextUrl.searchParams.get('sessionId')
  
  if (!sessionId) {
    return Response.json({ error: 'Session ID required' }, { status: 400 })
  }
  
  const session = sessionStore.get(sessionId)
  
  if (!session || Date.now() > session.expires) {
    sessionStore.delete(sessionId)
    return Response.json({ error: 'Session expired or not found' }, { status: 404 })
  }
  
  return Response.json({ session: session.data })
}
EOF
VIOLATIONS_CREATED=$((VIOLATIONS_CREATED + 1))
echo "Created session management violation"

# === Summary ===
echo "=== Violation Test Summary ==="
echo "Created $VIOLATIONS_CREATED intentional violations"
echo "Branch: $VIOLATION_TEST_BRANCH"
echo ""
echo "Violations created:"
echo "1. Cross-domain import (src/app/api/test-cross-domain/route.ts)"
echo "2. Schema duplication (src/app/test-schema.prisma)"
echo "3. Auth logic (src/app/api/test-auth/route.ts)"
echo "4. Rate limiting (src/app/api/test-rate-limit/route.ts)"
echo "5. Environment variables (src/app/api/test-env/route.ts)"
echo "6. Password handling (src/app/api/test-password/route.ts)"
echo "7. Session management (src/app/api/test-session/route.ts)"
echo ""
echo "Next steps:"
echo "1. Commit changes: git add . && git commit -m 'test: create L1 violations'"
echo "2. Push branch: git push origin $VIOLATION_TEST_BRANCH"
echo "3. Create PR to test CI enforcement"
echo "4. Verify CI fails with appropriate violations"
echo "5. Clean up: git checkout main && git branch -D $VIOLATION_TEST_BRANCH"
echo ""
echo "To restore original files:"
echo "rm -rf src/app src/server && mv src/app.backup src/app && mv src/server.backup src/server"
