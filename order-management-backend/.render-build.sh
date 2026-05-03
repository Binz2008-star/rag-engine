#!/bin/bash
# Render build script for Next.js app
set -e

echo "Building Next.js app for Render..."
npm ci
npm run build

echo "Build complete. Standalone output in .next/standalone/"
