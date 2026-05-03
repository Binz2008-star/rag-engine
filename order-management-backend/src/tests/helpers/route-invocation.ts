import { NextRequest } from 'next/server'

type RouteResponse<T> = {
  status: number
  body: T
}

type RouteLikeError = {
  statusCode?: number
  message?: string
}

type InvokeRouteOptions<TParams = undefined> = {
  url: string
  method?: string
  headers?: Record<string, string>
  body?: unknown
  params?: TParams
}

let requestCounter = 0

function nextIpAddress(): string {
  requestCounter += 1
  const octet = (requestCounter % 250) + 1
  return `127.0.0.${octet}`
}

function normalizeBody(body: unknown, headers: Record<string, string>) {
  if (body === undefined || body === null) {
    return undefined
  }

  if (
    typeof body === 'string' ||
    body instanceof ArrayBuffer ||
    body instanceof Blob ||
    body instanceof FormData ||
    body instanceof URLSearchParams
  ) {
    return body
  }

  if (!headers['content-type'] && !headers['Content-Type']) {
    headers['content-type'] = 'application/json'
  }

  return JSON.stringify(body)
}

function createRequest<TParams>(options: InvokeRouteOptions<TParams>): NextRequest {
  const headers: Record<string, string> = {
    'x-forwarded-for': nextIpAddress(),
    ...(options.headers ?? {}),
  }

  const body = normalizeBody(options.body, headers)

  return new NextRequest(options.url, {
    method: options.method ?? 'GET',
    headers,
    body: body as BodyInit | null | undefined,
  })
}

export async function invokeRoute<TResponse>(
  handler: (request: NextRequest) => Promise<Response>,
  options: InvokeRouteOptions<undefined>
): Promise<RouteResponse<TResponse>>
export async function invokeRoute<TResponse, TParams>(
  handler: (
    request: NextRequest,
    context: { params: Promise<TParams> }
  ) => Promise<Response>,
  options: InvokeRouteOptions<TParams>
): Promise<RouteResponse<TResponse>>
export async function invokeRoute<TResponse, TParams = undefined>(
  handler:
    | ((request: NextRequest) => Promise<Response>)
    | ((request: NextRequest, context: { params: Promise<TParams> }) => Promise<Response>),
  options: InvokeRouteOptions<TParams>
): Promise<RouteResponse<TResponse>> {
  const request = createRequest(options)

  let response: Response

  try {
    response =
      options.params !== undefined
        ? await (handler as (
          request: NextRequest,
          context: { params: Promise<TParams> }
        ) => Promise<Response>)(request, { params: Promise.resolve(options.params) })
        : await (handler as (request: NextRequest) => Promise<Response>)(request)
  } catch (error) {
    const routeError = error as RouteLikeError
    if (typeof routeError?.statusCode === 'number' && typeof routeError?.message === 'string') {
      response = new Response(
        JSON.stringify({ error: routeError.message }),
        {
          status: routeError.statusCode,
          headers: { 'content-type': 'application/json' },
        }
      )
    } else {
      throw error
    }
  }

  return {
    status: response.status,
    body: (await response.json()) as TResponse,
  }
}
