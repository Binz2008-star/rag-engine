#!/bin/bash

# L1 Violation Cleanup Script
# Purpose: Clean up intentional violations after testing

set -e

echo "=== L1 Violation Cleanup Script ==="

# Check if backups exist
if [ ! -d "src/app.backup" ] || [ ! -d "src/server.backup" ]; then
    echo "Error: Backup directories not found"
    echo "Expected: src/app.backup and src/server.backup"
    exit 1
fi

# Remove violated files
echo "Removing violation test files..."
rm -rf src/app/api/test-cross-domain
rm -f src/app/test-schema.prisma
rm -rf src/app/api/test-auth
rm -rf src/app/api/test-rate-limit
rm -rf src/app/api/test-env
rm -rf src/app/api/test-password
rm -rf src/app/api/test-session

# Restore original files
echo "Restoring original files..."
rm -rf src/app src/server
mv src/app.backup src/app
mv src/server.backup src/server

echo "Cleanup completed successfully"
echo "Original source code restored"
