from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client.fastapi import metrics
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Metrics configuration
if settings.METRICS_ENABLED:
    # Request metrics
    llm_requests_total = Counter(
        'llm_requests_total',
        'Total LLM requests',
        ['model', 'method']
    )
    
    llm_requests_cached = Counter(
        'llm_requests_cached',
        'Total cached LLM requests',
        ['model']
    )
    
    # Latency metrics
    llm_request_duration = Histogram(
        'llm_request_duration_seconds',
        'LLM request duration',
        ['model', 'method']
    )
    
    # Error metrics
    llm_errors_total = Counter(
        'llm_errors_total',
        'Total LLM errors',
        ['model', 'error_type']
    )
    
    # Circuit breaker metrics
    circuit_breaker_state = Gauge(
        'circuit_breaker_state',
        'Circuit breaker state (0=closed, 1=half_open, 2=open)',
        ['name']
    )
    
    circuit_breaker_failures = Gauge(
        'circuit_breaker_failures',
        'Circuit breaker failure count',
        ['name']
    )
    
    # Rate limit metrics
    rate_limit_requests = Gauge(
        'rate_limit_requests',
        'Rate limit remaining requests',
        ['identifier']
    )
    
    # Application info
    app_info = Info(
        'app_info',
        'Application information'
    )
    app_info.info({
        'version': settings.VERSION,
        'model': settings.MODEL
    })
else:
    logger.warning("metrics_disabled")


def record_request(model: str, method: str):
    """Record a request metric."""
    if settings.METRICS_ENABLED:
        llm_requests_total.labels(model=model, method=method).inc()


def record_cache_hit(model: str):
    """Record a cache hit."""
    if settings.METRICS_ENABLED:
        llm_requests_cached.labels(model=model).inc()


def record_error(model: str, error_type: str):
    """Record an error."""
    if settings.METRICS_ENABLED:
        llm_errors_total.labels(model=model, error_type=error_type).inc()


def record_circuit_state(name: str, state: int):
    """Record circuit breaker state."""
    if settings.METRICS_ENABLED:
        circuit_breaker_state.labels(name=name).set(state)


def record_circuit_failures(name: str, count: int):
    """Record circuit breaker failures."""
    if settings.METRICS_ENABLED:
        circuit_breaker_failures.labels(name=name).set(count)
