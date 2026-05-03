#!/bin/bash

# L1 Hardened Enforcement Script v2
# Purpose: Execute hardened L1 verification with comprehensive violation detection

set -e

echo "=== L1 Hardened Enforcement Script v2 ==="
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

# Function to log violations and increment counters
log_violation() {
    local violation_type="$1"
    local violation_pattern="$2"
    local file_path="$3"
    local line_number="$4"
    
    echo "[$violation_type] $file_path:$line_number - $violation_pattern" >> "$VIOLATION_LOG"
    echo "::error::$violation_type in $file_path:$line_number - $violation_pattern"
    
    # Increment the appropriate counter
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

# Function to count violations from grep output
count_violations() {
    local pattern="$1"
    local search_path="$2"
    local violation_type="$3"
    local violation_desc="$4"
    
    local count=$(grep -r -E "$pattern" "$search_path" 2>/dev/null | wc -l || echo 0)
    if [ "$count" -gt 0 ]; then
        echo "VIOLATION: $violation_desc ($count instances)"
        grep -r -n -E "$pattern" "$search_path" 2>/dev/null | while IFS=: read -r file line content; do
            log_violation "$violation_type" "$pattern" "$file" "$line"
        done
    fi
    echo "$count"
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
)

for pattern in "${CROSS_DOMAIN_PATTERNS[@]}"; do
    count=$(count_violations "$pattern" "src/app/" "CROSS_DOMAIN_IMPORT" "Cross-domain import pattern: $pattern")
    CROSS_DOMAIN_VIOLATIONS=$((CROSS_DOMAIN_VIOLATIONS + count))
done

# Check for server lib imports in app directory
server_lib_count=$(find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -l "server/lib" 2>/dev/null | wc -l || echo 0)
if [ "$server_lib_count" -gt 0 ]; then
    echo "VIOLATION: Direct server/lib imports detected"
    find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -n "server/lib" 2>/dev/null | while IFS=: read -r file line content; do
        log_violation "SERVER_LIB_IMPORT" "server/lib import" "$file" "$line"
    done
    CROSS_DOMAIN_VIOLATIONS=$((CROSS_DOMAIN_VIOLATIONS + server_lib_count))
fi

# Check for deep relative paths
deep_path_count=$(find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -l "\.\./\.\./\.\." 2>/dev/null | wc -l || echo 0)
if [ "$deep_path_count" -gt 0 ]; then
    echo "VIOLATION: Deep relative paths found ($deep_path_count instances)"
    find src/app/ -name "*.ts" -o -name "*.tsx" | xargs grep -n "\.\./\.\./\.\." 2>/dev/null | while IFS=: read -r file line content; do
        log_violation "CROSS_DOMAIN_IMPORT" "Deep relative path" "$file" "$line"
    done
    CROSS_DOMAIN_VIOLATIONS=$((CROSS_DOMAIN_VIOLATIONS + deep_path_count))
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
        grep -r -n "^model $model" prisma/ src/ 2>/dev/null | while IFS=: read -r file line content; do
            if [[ "$file" != "prisma/"* ]]; then
                log_violation "SCHEMA_DUPLICATION" "Duplicate model: $model" "$file" "$line"
            fi
        done
        # Count non-prisma instances
        non_prisma_instances=$(grep -r "^model $model" src/ 2>/dev/null | wc -l || echo 0)
        SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + non_prisma_instances))
    fi
done

# Check for unauthorized schema files
unauthorized_schema_count=$(find src/ -name "*.prisma" -o -name "*schema*.ts" | grep -v node_modules | wc -l || echo 0)
if [ "$unauthorized_schema_count" -gt 0 ]; then
    echo "VIOLATION: Unauthorized schema files detected ($unauthorized_schema_count instances)"
    find src/ -name "*.prisma" -o -name "*schema*.ts" | grep -v node_modules | while read -r file; do
        log_violation "UNAUTHORIZED_SCHEMA" "Schema file outside prisma/" "$file" "1"
    done
    SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + unauthorized_schema_count))
fi

# Database connection violations
DB_PATTERNS=("DATABASE_URL" "postgres://" "mysql://" "mongodb://")
for pattern in "${DB_PATTERNS[@]}"; do
    # Only check src/ directory (server/ is allowed to have DB connections)
    count=$(count_violations "$pattern" "src/" "DB_CONNECTION" "Database connection pattern: $pattern")
    # Exclude server/ directory from DB connection checks
    src_only_count=$(grep -r -E "$pattern" src/ --exclude-dir=server --exclude-dir=node_modules 2>/dev/null | wc -l || echo 0)
    SCHEMA_VIOLATIONS=$((SCHEMA_VIOLATIONS + src_only_count))
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
    count=$(count_violations "$pattern" "src/app/" "AUTH_PATTERN" "Restricted auth pattern: $pattern")
    AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + count))
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
    count=$(count_violations "$pattern" "src/app/" "PASSWORD_HANDLING" "Password handling pattern: $pattern")
    AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + count))
done

# Session management violations
SESSION_PATTERNS=(
    "(session|Session).*store"
    "store.*session"
    "new Map.*session"
    "session.*Map"
)

for pattern in "${SESSION_PATTERNS[@]}"; do
    count=$(count_violations "$pattern" "src/app/" "SESSION_MANAGEMENT" "Session management pattern: $pattern")
    AUTH_VIOLATIONS=$((AUTH_VIOLATIONS + count))
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
    count=$(count_violations "$pattern" "src/" "MEMORY_RATE_LIMIT" "In-memory rate limiting pattern: $pattern")
    RATE_LIMIT_VIOLATIONS=$((RATE_LIMIT_VIOLATIONS + count))
done

# Redis configuration violations
REDIS_PATTERNS=(
    "REDIS_URL"
    "redis.*createClient"
    "createClient.*redis"
    "redis\.connect"
)

for pattern in "${REDIS_PATTERNS[@]}"; do
    count=$(count_violations "$pattern" "src/app/" "REDIS_CONFIG" "Redis configuration pattern: $pattern")
    RATE_LIMIT_VIOLATIONS=$((RATE_LIMIT_VIOLATIONS + count))
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
    count=$(count_violations "$pattern" "src/" "HARDCODED_SECRET" "Potential hardcoded secret pattern: $pattern")
    ENV_VIOLATIONS=$((ENV_VIOLATIONS + count))
done

# Direct process.env usage
env_count=$(count_violations "process\.env\." "src/app/" "DIRECT_ENV_ACCESS" "Direct process.env usage")
ENV_VIOLATIONS=$((ENV_VIOLATIONS + env_count))

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
    "enforcement_version": "hardened-v2.2",
    "duration_seconds": $ENFORCEMENT_DURATION,
    "script_version": "2.0.0"
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
