import { type AuthUser } from '@/server/lib/auth'
import { generateRequestId, logger } from '@/server/lib/logger'
import {
    type RateLimitConfig,
    type RateLimitResponse,
    createRateLimit,
} from '@/server/lib/rate-limit'
import { type NextRequest, type NextResponse } from 'next/server'
import { type ZodType } from 'zod'
import { ApiError, toApiError } from './api-error'
import { requireRequestAdmin, requireRequestSeller, requireRequestUser } from './auth-guard'
import { jsonError, jsonSuccess } from './response'

type RouteAuthMode = 'public' | 'user' | 'seller' | 'admin'

type RouteOptions<TBody, TQuery, TParams, TUser extends AuthUser | undefined> = {
  bodySchema?: ZodType<TBody>
  querySchema?: ZodType<TQuery>
  paramsSchema?: ZodType<TParams>
  auth?: RouteAuthMode
  rateLimit?: RateLimitConfig
  handler: (context: {
    request: NextRequest
    requestId: string
    body: TBody
    query: TQuery
    params: TParams
    user: TUser
  }) => Promise<{
    body: Record<string, unknown>
    status?: number
    headers?: HeadersInit
  }>
}

type RawRouteContext = {
  params?: Promise<unknown>
}

function emptyValue<T>(): T {
  return undefined as T
}

async function parseJsonBody<T>(request: NextRequest, schema?: ZodType<T>): Promise<T> {
  if (!schema) {
    return emptyValue<T>()
  }

  try {
    const payload = await request.json()
    return schema.parse(payload)
  } catch (error) {
    // Log detailed error for debugging
    console.error('PARSE_JSON_ERROR:', {
      error: error instanceof Error ? error.message : String(error),
      url: request.url,
      method: request.method,
      contentType: request.headers.get('content-type'),
    })
    throw new ApiError(400, 'Invalid JSON body', 'INVALID_JSON')
  }
}

function parseQuery<T>(request: NextRequest, schema?: ZodType<T>): T {
  if (!schema) {
    return emptyValue<T>()
  }

  const { searchParams } = new URL(request.url)
  return schema.parse(Object.fromEntries(searchParams.entries()))
}

async function parseParams<T>(context: RawRouteContext | undefined, schema?: ZodType<T>): Promise<T> {
  if (!schema) {
    return emptyValue<T>()
  }

  if (!context?.params) {
    throw new ApiError(400, 'Missing route parameters', 'MISSING_PARAMS')
  }

  return schema.parse(await context.params)
}

async function authenticateRequest(
  mode: RouteAuthMode | undefined,
  request: NextRequest
): Promise<AuthUser | undefined> {
  switch (mode) {
    case 'user':
      return requireRequestUser(request)
    case 'seller':
      return requireRequestSeller(request)
    case 'admin':
      return requireRequestAdmin(request)
    default:
      return undefined
  }
}

function buildRateLimitError(result: Exclude<RateLimitResponse, { success: true }>): ApiError {
  if (result.reason === 'store_unavailable') {
    return new ApiError(503, 'Rate limiting service unavailable', 'RATE_LIMIT_UNAVAILABLE')
  }

  return new ApiError(429, 'Too many requests', 'RATE_LIMIT_EXCEEDED')
}

export function createRouteHandler<
  TBody = undefined,
  TQuery = undefined,
  TParams = undefined,
  TUser extends AuthUser | undefined = undefined,
>(
  options: RouteOptions<TBody, TQuery, TParams, TUser>
) {
  const rateLimit = options.rateLimit ? createRateLimit(options.rateLimit) : null

  return async (request: NextRequest, context?: RawRouteContext): Promise<NextResponse> => {
    const requestId = request.headers.get('x-request-id')?.trim() || generateRequestId()
    logger.setRequestId(requestId)

    try {
      let rateLimitHeaders: HeadersInit | undefined

      if (rateLimit) {
        const rateLimitResult = await rateLimit(request)
        rateLimitHeaders = rateLimitResult.headers

        if (!rateLimitResult.success) {
          return jsonError(buildRateLimitError(rateLimitResult), requestId, {
            headers: rateLimitHeaders,
          })
        }
      }

      const [body, params] = await Promise.all([
        Promise.resolve(parseJsonBody(request, options.bodySchema)),
        parseParams(context, options.paramsSchema),
      ])

      const query = parseQuery(request, options.querySchema)
      const user = await authenticateRequest(options.auth, request) as TUser

      const response = await options.handler({
        request,
        requestId,
        body,
        query,
        params,
        user,
      })

      return jsonSuccess(response.body, requestId, {
        status: response.status,
        headers: response.headers ?? rateLimitHeaders,
      })
    } catch (error) {
      console.error('ROUTE_HANDLER_ERROR', {
        message: error instanceof Error ? error.message : error,
        stack: error instanceof Error ? error.stack : undefined,
        requestId,
        path: request.url,
        method: request.method,
      })

      const apiError = toApiError(error)
      logger.error('Route handler failed', apiError, { requestId, path: request.url, method: request.method })
      return jsonError(apiError, requestId)
    }
  }
}
