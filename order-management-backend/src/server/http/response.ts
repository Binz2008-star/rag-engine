import { NextResponse } from 'next/server'
import { ApiError } from './api-error'

type JsonValue = Record<string, unknown> | unknown[] | string | number | boolean | null

function buildHeaders(requestId: string, headers?: HeadersInit): Headers {
  const responseHeaders = new Headers(headers)
  responseHeaders.set('X-Request-ID', requestId)
  return responseHeaders
}

export function jsonSuccess<T extends JsonValue>(
  data: T,
  requestId: string,
  init?: { status?: number; headers?: HeadersInit }
): NextResponse<T> {
  return NextResponse.json(data, {
    status: init?.status ?? 200,
    headers: buildHeaders(requestId, init?.headers),
  })
}

export function jsonError(
  error: ApiError,
  requestId: string,
  init?: { headers?: HeadersInit }
): NextResponse<{
  error: string
  code: string
  details?: typeof error.details
  requestId: string
}> {
  return NextResponse.json(
    {
      error: error.message,
      code: error.code,
      details: error.details,
      requestId,
    },
    {
      status: error.statusCode,
      headers: buildHeaders(requestId, init?.headers),
    }
  )
}

