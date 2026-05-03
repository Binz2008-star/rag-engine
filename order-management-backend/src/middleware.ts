import { NextRequest, NextResponse } from 'next/server';

export const config = {
  matcher: [
    '/api/:path*',
  ],
};

export default function middleware(request: NextRequest) {
  // Disable all middleware for now to avoid body consumption issues
  return NextResponse.next();
}
