import { NextRequest } from 'next/server'

export function withRequestId(handler: (req: NextRequest) => Promise<Response>) {
  return async (req: NextRequest) => {
    const requestId = crypto.randomUUID()

    // Add request ID to response headers
    const response = await handler(req)
    response.headers.set('X-Request-ID', requestId)

    return response
  }
}
