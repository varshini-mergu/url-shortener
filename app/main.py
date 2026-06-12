import time
import uuid
import logging
import tracemalloc
from collections import defaultdict

# Start memory tracking
tracemalloc.start()

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from app.database import engine, Base, wait_for_db_query, DatabaseTimeoutError
from app.routers import links, redirect, teams
from app.logging_config import setup_logging, request_id_context
# Import models to register them on Base for startup schema creation
import app.models


from sqlalchemy import text

# Initialize structured, redacted logging config on startup
setup_logging()
logger = logging.getLogger("app.main")

# In-memory Prometheus-style metrics collector for request volumes and latency distributions
http_requests_total = defaultdict(int)
http_request_duration_histogram = defaultdict(lambda: defaultdict(int))
http_request_duration_sum = defaultdict(float)
http_request_duration_count = defaultdict(int)
HISTOGRAM_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")]

app = FastAPI(
    title="URL Shortener API",
    description="A secure and high-performance URL shortening service.",
    version="1.0.0"
)


def _prom_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _metric_key(method: str, path: str, status_code: int) -> tuple[str, str, str]:
    return method.upper(), path, str(status_code)


def _record_request_metrics(method: str, path: str, status_code: int, latency_seconds: float) -> None:
    key = _metric_key(method, path, status_code)
    http_requests_total[key] += 1
    http_request_duration_sum[key] += latency_seconds
    http_request_duration_count[key] += 1

    bucket_counts = http_request_duration_histogram[key]
    for bucket in HISTOGRAM_BUCKETS:
        if latency_seconds <= bucket:
            label = "+Inf" if bucket == float("inf") else str(bucket)
            bucket_counts[label] += 1


# --- MIDDLEWARE ---

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Tracks latency, generates thread-safe request Correlation IDs, and logs http metrics."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_context.set(request_id)
    
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start_time) * 1000
        latency_seconds = latency_ms / 1000.0
        metric_path = request.scope.get("route").path if request.scope.get("route") is not None else request.url.path
        _record_request_metrics(request.method, metric_path, response.status_code, latency_seconds)
        
        # Log structured request details safely (handled by RedactingFormatter)
        logger.info(
            f"HTTP {request.method} {request.url.path} - Status: {response.status_code} - Latency: {latency_ms:.2f}ms"
        )
        
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        latency_seconds = latency_ms / 1000.0
        metric_path = request.scope.get("route").path if request.scope.get("route") is not None else request.url.path
        _record_request_metrics(request.method, metric_path, 500, latency_seconds)
        logger.error(
            f"HTTP {request.method} {request.url.path} - FAILED - Latency: {latency_ms:.2f}ms - Error: {str(exc)}",
            exc_info=exc
        )
        
        # Dispatch exceptions explicitly to exception handlers to prevent raw trace leaks caused by Starlette middleware propagation
        if isinstance(exc, HTTPException):
            response = await http_exception_handler(request, exc)
        elif isinstance(exc, RequestValidationError):
            response = await validation_exception_handler(request, exc)
        else:
            response = await unhandled_exception_handler(request, exc)
            
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_context.reset(token)

# --- EXCEPTION HANDLERS ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardizes HTTPExceptions (auth/not found/rate limit) into the standard JSON envelope."""
    status_code = exc.status_code
    
    # Map status codes to stable error strings
    if status_code == 401:
        code = "UNAUTHORIZED"
    elif status_code == 403:
        code = "FORBIDDEN"
    elif status_code == 404:
        code = "NOT_FOUND"
    elif status_code == 429:
        code = "TOO_MANY_REQUESTS"
    elif status_code == 500:
        code = "INTERNAL_SERVER_ERROR"
    else:
        code = "HTTP_ERROR"
        
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "request_id": request_id_context.get()
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Simplifies validation errors into a clean string without leaking schema internal trace details."""
    errors = exc.errors()
    err_msgs = []
    for error in errors:
        loc = " -> ".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "invalid value")
        err_msgs.append(f"{loc}: {msg}")
    friendly_message = "Validation failed: " + "; ".join(err_msgs)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": friendly_message,
                "request_id": request_id_context.get()
            }
        }
    )

@app.exception_handler(DatabaseTimeoutError)
async def database_timeout_exception_handler(request: Request, exc: DatabaseTimeoutError):
    logger.error(f"Database timeout detected: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_TIMEOUT",
                "message": "A database operation timed out. Please retry shortly.",
                "request_id": request_id_context.get()
            }
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Intercepts unhandled 500 server crashes, logs full traceback with request ID, and hides them from clients."""
    request_id = request_id_context.get()
    logger.error(f"Unhandled server error: {str(exc)}", exc_info=exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred. Please contact support.",
                "request_id": request_id
            }
        }
    )

# --- STARTUP & ROUTERS ---

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown():
    logger.info("Application is shutting down. Cleaning up connections...")
    # Clean up database connection pool cleanly
    await engine.dispose()
    # Clean up Redis client connections cleanly
    from app.services.cache_service import redis_client
    await redis_client.close()
    logger.info("Connections cleaned up successfully.")

app.include_router(links.router)
app.include_router(redirect.router)
app.include_router(teams.router)

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint to prove the service is active and running."""
    return {"status": "healthy"}

@app.get("/live", tags=["System"])
async def liveness_check():
    """Liveness check endpoint to prove the process is running."""
    return {"status": "healthy"}

@app.get("/debug/memory", tags=["System"])
def memory_stats():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")
    return {"top_allocations": [str(s) for s in top_stats[:10]]}


@app.get("/ready", tags=["System"])
async def readiness_check():
    """Readiness check endpoint that verifies connectivity to database and Redis."""
    # Check Database connectivity
    try:
        async with engine.connect() as conn:
            await wait_for_db_query(conn.execute(text("SELECT 1")))
    except DatabaseTimeoutError as e:
        logger.error(f"Readiness probe failed: Database timeout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database operation timed out"
        )
    except Exception as e:
        logger.error(f"Readiness probe failed: Database is unreachable: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )
        
    # Check Redis connectivity
    try:
        from app.services.cache_service import redis_client
        await redis_client.ping()
    except Exception as e:
        logger.error(f"Readiness probe failed: Redis is unreachable: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection failed"
        )
    
    return {"status": "ready"}


@app.get("/metrics", tags=["System"])
async def metrics():
    """Expose Prometheus-compatible metrics for observability verification."""
    link_count = 0
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM links"))
            link_count = result.scalar_one()
    except Exception as exc:
        logger.error(f"Metrics endpoint failed to count links: {str(exc)}", exc_info=exc)

    lines = [
        "# HELP http_requests_total Total number of HTTP requests received.",
        "# TYPE http_requests_total counter"
    ]

    for (method, path, status_code), count in sorted(http_requests_total.items()):
        labels = f'method="{_prom_label_value(method)}",path="{_prom_label_value(path)}",status="{status_code}"'
        lines.append(f"http_requests_total{{{labels}}} {count}")

    lines.append("# HELP http_request_duration_seconds Histogram of request durations in seconds.")
    lines.append("# TYPE http_request_duration_seconds histogram")

    for key, bucket_counts in sorted(http_request_duration_histogram.items()):
        method, path, status_code = key
        for bucket, value in sorted(bucket_counts.items(), key=lambda item: float('inf') if item[0] == '+Inf' else float(item[0])):
            labels = f'method="{_prom_label_value(method)}",path="{_prom_label_value(path)}",status="{status_code}",le="{bucket}"'
            lines.append(f"http_request_duration_seconds_bucket{{{labels}}} {value}")
        summary_labels = f'method="{_prom_label_value(method)}",path="{_prom_label_value(path)}",status="{status_code}"'
        lines.append(f"http_request_duration_seconds_sum{{{summary_labels}}} {http_request_duration_sum[key]:.6f}")
        lines.append(f"http_request_duration_seconds_count{{{summary_labels}}} {http_request_duration_count[key]}")

    lines.extend([
        "# HELP url_shortener_links_current_count Current number of shortened links in the service.",
        "# TYPE url_shortener_links_current_count gauge",
        f"url_shortener_links_current_count {link_count}"
    ])

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
