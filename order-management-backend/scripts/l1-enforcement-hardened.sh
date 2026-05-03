#!/bin/bash

# L1 Hardened Enforcement Script
# Purpose: Execute hardened L1 verification with comprehensive violation detection

set -e

echo "=== L1 Hardened Enforcement Script ==="
echo "Executing comprehensive L1 verification..."

# Configuration
EVIDENCE_FILE="l1-enforcement-evidence.json"
VIOLATION_LOG="l1-violations.log"
ENFORCEMENT_START=$(date +%s)

# Initialize counters
TOTAL_VIOLATIONS=0
CROSS_DOMAIN_VIOLATIONS=0
SCHEMA_VIOLATIONS=0
AUTH_VIOLATIONS=0
RATE_LIMIT_VIOLATIONS=0
ENV_VIOLATIONS=0

# Initialize status variables
CROSS_DOMAIN_STATUS="PASS"
SCHEMA_AUTHORITY_STATUS="PASS"
AUTH_AUTHORITY_STATUS="PASS"
RATE_LIMIT_AUTHORITY_STATUS="PASS"
ENV_AUTHORITY_STATUS="PASS"

# Clear previous logs
> "$VIOLATION_LOG"

# Function to log violations
log_violation() {
    local violation_type="$1"
    local violation_pattern="$2"
    local file_path="$3"
    local line_number="$4"

    echo "[$violation_type] $file_path:$line_number - $violation_pattern" >> "$VIOLATION_LOG"
    echo "::error::$violation_type in $file_path:$line_number - $violation_pattern"
}

# Function to increment violation counters
increment_violation() {
    local violation_type="$1"
    case "$violation_type" in
        "CROSS_DOMAIN_IMPORT"|"SERVER_LIB_IMPORT")
            CROSS_DOMAIN_VIOLATIONS=$((CROSS_DOMAIN_VIOLATIONS + 1))
            ;;
        "SCHEMA_DUPLICATION"|"UNAUTHORIZED_SCHEMA"|"DB_CONNECTION")
            SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + 1))
            ;;
        "AUTH_PATTERN"|"PASSWORD_HANDLING"|"SESSION_MANAGEMENT")
            AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + 1))
            ;;
        "MEMORY_RATE_LIMIT"|"REDIS_CONFIG")
            RATE_LIMIT_VIOLATIONS=$((RATE_LIMIT_VIOLATIONS + 1))
            ;;
        "HARDCODED_SECRET"|"DIRECT_ENV_ACCESS")
            ENV_VIOLATIONS=$((ENV_VIOLATIONS + 1))
            ;;
    esac
}

# === SECTION 1: Cross-Domain Boundary Enforcement ===
echo "## Section 1: Cross-Domain Boundaries"

# Enhanced pattern detection for cross-domain imports
CROSS_DOMAIN_PATTERNS=(
    "from\s+['\"]\.\.\/\.\.\/server"
    "import.*from\s+['\"]\.\.\/\.\.\/server"
    "require\s*\(\s*['\"]\.\.\/\.\.\/server"
    "from\s+['\"]\.\.\/\.\.\/server\/lib"
    "import.*from\s+['\"]\.\.\/\.\.\/server\/lib"
    "require\s*\(\s*['\"]\.\.\/\.\.\/server\/lib"
    "\.\./\.\./\.\."
)

for pattern in "${CROSS_DOMAIN_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/app/ > /dev/null 2>&1; then
        echo "VIOLATION: Cross-domain import pattern detected: $pattern"
        grep -r -n -E "$pattern" src/app/ | while IFS=: read -r file line content; do
            log_violation "CROSS_DOMAIN_IMPORT" "$pattern" "$file" "$line"
            increment_violation "CROSS_DOMAIN_IMPORT"
        done
    fi
done

# Check for server lib imports in app directory
if find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -l "server/lib" 2>/dev/null; then
    echo "VIOLATION: Direct server/lib imports detected"
    find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -n "server/lib" | while IFS=: read -r file line content; do
        log_violation "SERVER_LIB_IMPORT" "server/lib import" "$file" "$line"
        increment_violation "SERVER_LIB_IMPORT"
    done
fi

if [ $CROSS_DOMAIN_VIOLATIONS -eq 0 ]; then
    echo "PASS: Cross-domain boundaries intact"
    CROSS_DOMAIN_STATUS="PASS"
else
    echo "FAIL: $CROSS_DOMAIN_VIOLATIONS cross-domain violations"
    CROSS_DOMAIN_STATUS="FAIL"
fi

# === SECTION 2: Schema Authority Enforcement ===
echo "## Section 2: Schema Authority"

# Enhanced schema violation detection
PRISMA_MODELS=("User" "PaymentAttempt" "Seller" "session" "Order" "Payment" "Inventory")

for model in "${PRISMA_MODELS[@]}"; do
    model_instances=$(grep -r "^model $model" prisma/ src/ 2>/dev/null | wc -l || echo 0)
    if [ "$model_instances" -gt 1 ]; then
        echo "VIOLATION: $model model duplicated ($model_instances instances)"
        grep -r -n "^model $model" prisma/ src/ | while IFS=: read -r file line content; do
            if [[ "$file" != "prisma/"* ]]; then
                log_violation "SCHEMA_DUPLICATION" "Duplicate model: $model" "$file" "$line"
                SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + 1))
            fi
        done
    fi
done

# Check for unauthorized schema files
UNAUTHORIZED_SCHEMAS=$(find src/ -name "*.prisma" -o -name "*schema*.ts" | grep -v node_modules | wc -l || echo 0)
if [ "$UNAUTHORIZED_SCHEMAS" -gt 0 ]; then
    echo "VIOLATION: Unauthorized schema files detected"
    find src/ -name "*.prisma" -o -name "*schema*.ts" | grep -v node_modules | while read -r file; do
        log_violation "UNAUTHORIZED_SCHEMA" "Schema file outside prisma/" "$file" "1"
        SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + 1))
    done
fi

# Database connection violations
DB_PATTERNS=("DATABASE_URL" "postgres://" "mysql://" "mongodb://")
for pattern in "${DB_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/ --exclude-dir=node_modules > /dev/null 2>&1; then
        echo "VIOLATION: Database connection pattern: $pattern"
        grep -r -n -E "$pattern" src/ --exclude-dir=node_modules | while IFS=: read -r file line content; do
            log_violation "DB_CONNECTION" "$pattern" "$file" "$line"
            SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + 1))
        done
    fi
done

if [ $SCHEMA_VIOLATIONS -eq 0 ]; then
    echo "PASS: Schema authority enforced"
    SCHEMA_AUTHORITY_STATUS="PASS"
else
    echo "FAIL: $SCHEMA_VIOLATIONS schema authority violations"
    SCHEMA_AUTHORITY_STATUS="FAIL"
fi

# === SECTION 3: Authentication Authority Enforcement ===
echo "## Section 3: Authentication Authority"

# Enhanced auth pattern detection
RESTRICTED_AUTH_PATTERNS=(
    "bcrypt\.hash"
    "bcrypt\.compare"
    "jwt\.sign"
    "jwt\.verify"
    "createHash"
    "pbkdf2"
    "scrypt"
    "argon2"
    "crypto\.createHmac"
    "crypto\.pbkdf2Sync"
)

for pattern in "${RESTRICTED_AUTH_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/app/ > /dev/null 2>&1; then
        echo "VIOLATION: Restricted auth pattern: $pattern"
        grep -r -n -E "$pattern" src/app/ | while IFS=: read -r file line content; do
            log_violation "AUTH_PATTERN" "$pattern" "$file" "$line"
            AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + 1))
        done
    fi
done

# Password handling violations
PASSWORD_PATTERNS=(
    "(password|Password).*hash"
    "hash.*password"
    "salt.*password"
    "password.*salt"
    "crypto\.pbkdf2Sync.*password"
)

for pattern in "${PASSWORD_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/app/ > /dev/null 2>&1; then
        echo "VIOLATION: Password handling pattern: $pattern"
        grep -r -n -E "$pattern" src/app/ | while IFS=: read -r file line content; do
            log_violation "PASSWORD_HANDLING" "$pattern" "$file" "$line"
            AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + 1))
        done
    fi
done

# Session management violations
SESSION_PATTERNS=(
    "(session|Session).*store"
    "store.*session"
    "new Map.*session"
    "session.*Map"
)

for pattern in "${SESSION_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/app/ > /dev/null 2>&1; then
        echo "VIOLATION: Session management pattern: $pattern"
        grep -r -n -E "$pattern" src/app/ | while IFS=: read -r file line content; do
            log_violation "SESSION_MANAGEMENT" "$pattern" "$file" "$line"
            AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + 1))
        done
    fi
done

if [ $AUTH_VIOLATIONS -eq 0 ]; then
    echo "PASS: Authentication authority enforced"
    AUTH_AUTHORITY_STATUS="PASS"
else
    echo "FAIL: $AUTH_VIOLATIONS authentication authority violations"
    AUTH_AUTHORITY_STATUS="FAIL"
fi

# === SECTION 4: Rate Limiting Authority Enforcement ===
echo "## Section 4: Rate Limiting Authority"

# Enhanced rate limiting pattern detection
MEMORY_RATE_LIMIT_PATTERNS=(
    "new Map.*rate.*limit"
    "rate.*limit.*Map"
    "Map.*rate.*limit"
    "rate.*limit.*new Map"
    "rateLimit.*Map"
    "Map.*rateLimit"
)

for pattern in "${MEMORY_RATE_LIMIT_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/ > /dev/null 2>&1; then
        echo "VIOLATION: In-memory rate limiting pattern: $pattern"
        grep -r -n -E "$pattern" src/ | while IFS=: read -r file line content; do
            log_violation "MEMORY_RATE_LIMIT" "$pattern" "$file" "$line"
            RATE_LIMIT_VIOLATIONS=$((RATE_LIMIT_VIOLATIONS + 1))
        done
    fi
done

# Redis configuration violations
REDIS_PATTERNS=(
    "REDIS_URL"
    "redis.*createClient"
    "createClient.*redis"
    "redis\.connect"
)

for pattern in "${REDIS_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/app/ > /dev/null 2>&1; then
        echo "VIOLATION: Redis configuration pattern: $pattern"
        grep -r -n -E "$pattern" src/app/ | while IFS=: read -r file line content; do
            log_violation "REDIS_CONFIG" "$pattern" "$file" "$line"
            RATE_LIMIT_VIOLATIONS=$((RATE_LIMIT_VIOLATIONS + 1))
        done
    fi
done

if [ $RATE_LIMIT_VIOLATIONS -eq 0 ]; then
    echo "PASS: Rate limiting authority enforced"
    RATE_LIMIT_AUTHORITY_STATUS="PASS"
else
    echo "FAIL: $RATE_LIMIT_VIOLATIONS rate limiting authority violations"
    RATE_LIMIT_AUTHORITY_STATUS="FAIL"
fi

# === SECTION 5: Environment Variable Authority ===
echo "## Section 5: Environment Variable Authority"

# Enhanced secret detection
SECRET_PATTERNS=(
    "password.*=.*['\"][^'\"]{8,}['\"]"
    "secret.*=.*['\"][^'\"]{8,}['\"]"
    "key.*=.*['\"][^'\"]{16,}['\"]"
    "token.*=.*['\"][^'\"]{20,}['\"]"
    "api_key.*=.*['\"][^'\"]{10,}['\"]"
    "private_key.*=.*['\"][^'\"]{30,}['\"]"
)

for pattern in "${SECRET_PATTERNS[@]}"; do
    if grep -r -E "$pattern" src/ --exclude-dir=node_modules > /dev/null 2>&1; then
        echo "VIOLATION: Potential hardcoded secret pattern: $pattern"
        grep -r -n -E "$pattern" src/ --exclude-dir=node_modules | while IFS=: read -r file line content; do
            log_violation "HARDCODED_SECRET" "$pattern" "$file" "$line"
            ENV_VIOLATIONS=$((ENV_VIOLATIONS + 1))
        done
    fi
done

# Direct process.env usage
if grep -r -E "process\.env\." src/app/ > /dev/null 2>&1; then
    echo "VIOLATION: Direct process.env usage in API routes"
    grep -r -n -E "process\.env\." src/app/ | while IFS=: read -r file line content; do
        log_violation "DIRECT_ENV_ACCESS" "process.env usage" "$file" "$line"
        ENV_VIOLATIONS=$((ENV_VIOLATIONS + 1))
    done
fi

if [ $ENV_VIOLATIONS -eq 0 ]; then
    echo "PASS: Environment variable authority enforced"
    ENV_AUTHORITY_STATUS="PASS"
else
    echo "FAIL: $ENV_VIOLATIONS environment variable authority violations"
    ENV_AUTHORITY_STATUS="FAIL"
fi

# === CALCULATE TOTAL VIOLATIONS ===
TOTAL_VIOLATIONS=$((CROSS_DOMAIN_VIOLATIONS + SCHEMA_VIOLATIONS + AUTH_VIOLATIONS + RATE_LIMIT_VIOLATIONS + ENV_VIOLATIONS))

# === EVIDENCE GENERATION ===
echo "## Evidence Generation"
ENFORCEMENT_END=$(date +%s)
ENFORCEMENT_DURATION=$((ENFORCEMENT_END - ENFORCEMENT_START))

# Generate comprehensive evidence report
cat > "$EVIDENCE_FILE" << EOF
{
  "metadata": {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "run_id": "${GITHUB_RUN_ID:-local}",
    "repo": "${GITHUB_REPOSITORY:-order-management-backend}",
    "branch": "${GITHUB_REF_NAME:-local}",
    "layer": "L1",
    "enforcement_version": "hardened-v2.1",
    "duration_seconds": $ENFORCEMENT_DURATION,
    "script_version": "1.0.0"
  },
  "enforcement_checks": {
    "cross_domain_boundaries": {
      "status": "$CROSS_DOMAIN_STATUS",
      "violations": $CROSS_DOMAIN_VIOLATIONS,
      "description": "API routes importing server layer or bypassing boundaries"
    },
    "schema_authority": {
      "status": "$SCHEMA_AUTHORITY_STATUS",
      "violations": $SCHEMA_VIOLATIONS,
      "description": "Schema duplication, unauthorized files, or database connections"
    },
    "authentication_authority": {
      "status": "$AUTH_AUTHORITY_STATUS",
      "violations": $AUTH_VIOLATIONS,
      "description": "Auth logic, password handling, or session management in API routes"
    },
    "rate_limiting_authority": {
      "status": "$RATE_LIMIT_AUTHORITY_STATUS",
      "violations": $RATE_LIMIT_VIOLATIONS,
      "description": "In-memory rate limiting or Redis configuration in API routes"
    },
    "environment_authority": {
      "status": "$ENV_AUTHORITY_STATUS",
      "violations": $ENV_VIOLATIONS,
      "description": "Hardcoded secrets or direct process.env usage"
    }
  },
  "summary": {
    "total_violations": $TOTAL_VIOLATIONS,
    "enforcement_result": "$([ $TOTAL_VIOLATIONS -eq 0 ] && echo 'PASS' || echo 'FAIL')",
    "compliance_level": "$([ $TOTAL_VIOLATIONS -eq 0 ] && echo 'L1_COMPLETE' || echo 'L1_VIOLATIONS')",
    "governance_status": "$([ $TOTAL_VIOLATIONS -eq 0 ] && echo 'COMPLIANT' || echo 'NON_COMPLIANT')",
    "violation_breakdown": {
      "cross_domain": $CROSS_DOMAIN_VIOLATIONS,
      "schema": $SCHEMA_VIOLATIONS,
      "auth": $AUTH_VIOLATIONS,
      "rate_limit": $RATE_LIMIT_VIOLATIONS,
      "environment": $ENV_VIOLATIONS
    }
  }
}
EOF

echo "=== L1 Enforcement Summary ==="
echo "Evidence report: $EVIDENCE_FILE"
echo "Violation log: $VIOLATION_LOG"
echo "Enforcement duration: ${ENFORCEMENT_DURATION}s"
echo "Total violations: $TOTAL_VIOLATIONS"
echo ""

echo "Violation breakdown:"
echo "- Cross-domain: $CROSS_DOMAIN_VIOLATIONS"
echo "- Schema: $SCHEMA_VIOLATIONS"
echo "- Auth: $AUTH_VIOLATIONS"
echo "- Rate limiting: $RATE_LIMIT_VIOLATIONS"
echo "- Environment: $ENV_VIOLATIONS"
echo ""

# Final enforcement decision
if [ $TOTAL_VIOLATIONS -gt 0 ]; then
    echo "::error::L1 Hardened Enforcement FAILED"
    echo "Violations detected: $TOTAL_VIOLATIONS"
    echo "Review violation log: $VIOLATION_LOG"
    echo "Review evidence report: $EVIDENCE_FILE"
    exit 1
else
    echo "L1 Hardened Enforcement: PASSED"
    echo "All boundary checks passed - governance compliant"
fi

echo "=== L1 Enforcement Complete ==="
