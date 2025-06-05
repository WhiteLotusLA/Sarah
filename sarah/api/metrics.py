"""Prometheus metrics for Sarah AI monitoring."""

import time
from typing import Optional, Callable
from functools import wraps
import psutil
import asyncio

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest
from prometheus_client.core import CollectorRegistry
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# Create a custom registry
REGISTRY = CollectorRegistry()

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    registry=REGISTRY,
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    registry=REGISTRY,
)

# WebSocket metrics
websocket_connections = Gauge(
    "websocket_connections",
    "Current WebSocket connections",
    ["endpoint"],
    registry=REGISTRY,
)

websocket_messages_total = Counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    ["endpoint", "direction"],  # direction: sent/received
    registry=REGISTRY,
)

# Agent metrics
sarah_agent_up = Gauge(
    "sarah_agent_up",
    "Agent availability (1 = up, 0 = down)",
    ["agent_id", "agent_type"],
    registry=REGISTRY,
)

sarah_agent_memory_mb = Gauge(
    "sarah_agent_memory_mb",
    "Agent memory usage in MB",
    ["agent_id", "agent_type"],
    registry=REGISTRY,
)

sarah_agent_tasks_total = Counter(
    "sarah_agent_tasks_total",
    "Total tasks processed by agent",
    ["agent_id", "agent_type", "status"],  # status: success/failure
    registry=REGISTRY,
)

sarah_agent_response_time_seconds = Histogram(
    "sarah_agent_response_time_seconds",
    "Agent response time",
    ["agent_id", "agent_type"],
    registry=REGISTRY,
)

# Memory system metrics
sarah_memory_operations_total = Counter(
    "sarah_memory_operations_total",
    "Total memory operations",
    ["operation", "status"],  # operation: store/recall/search, status: success/failure
    registry=REGISTRY,
)

sarah_memory_size_bytes = Gauge(
    "sarah_memory_size_bytes", "Total size of memory storage", registry=REGISTRY
)

# Rate limiting metrics
sarah_rate_limit_exceeded_total = Counter(
    "sarah_rate_limit_exceeded_total",
    "Total rate limit violations",
    ["user_tier", "endpoint"],
    registry=REGISTRY,
)

# Backup metrics
sarah_backup_last_success_timestamp = Gauge(
    "sarah_backup_last_success_timestamp",
    "Timestamp of last successful backup",
    ["backup_type"],  # backup_type: database/redis/files
    registry=REGISTRY,
)

sarah_backup_size_bytes = Gauge(
    "sarah_backup_size_bytes",
    "Size of last backup in bytes",
    ["backup_type"],
    registry=REGISTRY,
)

sarah_backup_duration_seconds = Histogram(
    "sarah_backup_duration_seconds",
    "Backup duration",
    ["backup_type"],
    registry=REGISTRY,
)

# System info
system_info = Info("sarah_system", "System information", registry=REGISTRY)

# Set system info
system_info.info(
    {"version": "0.1.0", "python_version": "3.11", "environment": "production"}
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        # Track in-progress requests
        http_requests_in_progress.inc()

        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            labels = {
                "method": request.method,
                "endpoint": request.url.path,
                "status": str(response.status_code),
            }
            http_requests_total.labels(**labels).inc()

            duration_labels = {"method": request.method, "endpoint": request.url.path}
            http_request_duration_seconds.labels(**duration_labels).observe(
                time.time() - start_time
            )

            return response

        finally:
            http_requests_in_progress.dec()


def track_agent_metrics(agent_id: str, agent_type: str):
    """Decorator to track agent method metrics."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failure"
                raise e
            finally:
                # Record task completion
                sarah_agent_tasks_total.labels(
                    agent_id=agent_id, agent_type=agent_type, status=status
                ).inc()

                # Record response time
                sarah_agent_response_time_seconds.labels(
                    agent_id=agent_id, agent_type=agent_type
                ).observe(time.time() - start_time)

        return wrapper

    return decorator


async def collect_system_metrics():
    """Collect system-level metrics."""
    while True:
        try:
            # Collect CPU and memory for current process
            process = psutil.Process()

            # Update agent memory usage (example for main process)
            sarah_agent_memory_mb.labels(agent_id="main", agent_type="system").set(
                process.memory_info().rss / 1024 / 1024
            )

            await asyncio.sleep(30)  # Collect every 30 seconds

        except Exception as e:
            print(f"Error collecting system metrics: {e}")
            await asyncio.sleep(60)


def metrics_endpoint() -> Response:
    """Generate metrics for Prometheus scraping."""
    metrics = generate_latest(REGISTRY)
    return Response(content=metrics, media_type="text/plain")


# WebSocket tracking helpers
def track_websocket_connect(endpoint: str):
    """Track WebSocket connection."""
    websocket_connections.labels(endpoint=endpoint).inc()


def track_websocket_disconnect(endpoint: str):
    """Track WebSocket disconnection."""
    websocket_connections.labels(endpoint=endpoint).dec()


def track_websocket_message(endpoint: str, direction: str):
    """Track WebSocket message."""
    websocket_messages_total.labels(endpoint=endpoint, direction=direction).inc()


# Agent health tracking
def update_agent_health(agent_id: str, agent_type: str, is_up: bool):
    """Update agent health status."""
    sarah_agent_up.labels(agent_id=agent_id, agent_type=agent_type).set(
        1 if is_up else 0
    )


# Memory operation tracking
def track_memory_operation(operation: str, status: str):
    """Track memory operation."""
    sarah_memory_operations_total.labels(operation=operation, status=status).inc()


# Rate limit tracking
def track_rate_limit_exceeded(user_tier: str, endpoint: str):
    """Track rate limit violation."""
    sarah_rate_limit_exceeded_total.labels(user_tier=user_tier, endpoint=endpoint).inc()


# Backup tracking
def update_backup_metrics(
    backup_type: str, size_bytes: int, duration: float, success: bool
):
    """Update backup metrics."""
    if success:
        sarah_backup_last_success_timestamp.labels(
            backup_type=backup_type
        ).set_to_current_time()

        sarah_backup_size_bytes.labels(backup_type=backup_type).set(size_bytes)

    sarah_backup_duration_seconds.labels(backup_type=backup_type).observe(duration)
