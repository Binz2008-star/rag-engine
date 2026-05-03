#!/usr/bin/env bash
set -euo pipefail

echo "Checking forbidden platform logic in runtime..."

forbidden_patterns=(
  "OpportunityEngine"
  "supplier import"
  "catalog enrichment"
  "workflow automation"
  "profit scoring"
  "AI sourcing"
  "opportunity discovery"
  "product enrichment"
  "autonomous workflows"
)

for pattern in "${forbidden_patterns[@]}"; do
  if grep -R -n "$pattern" src docs --exclude-dir=node_modules --exclude="*.md" --exclude="*.sh" --exclude="*.yml"; then
    echo "Forbidden platform-domain pattern found in runtime: $pattern"
    exit 1
  fi
done

echo "Boundary check passed."
