import time

from fastapi import APIRouter, Request
from prometheus_client import Counter, Histogram, generate_latest

router = APIRouter()

# Define a Counter metric for total requests
REQUESTS_TOTAL = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint"])

# Define a Counter metric for error requests
REQUESTS_ERROR = Counter(
	"http_requests_error_total",
	"Total HTTP requests resulting in an error",
	["method", "endpoint", "status_code"],
)

# Define a Histogram metric for request duration
REQUEST_DURATION_SECONDS = Histogram(
	"http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)


async def metrics_middleware(request: Request, call_next):
	start_time = time.time()
	response = await call_next(request)
	process_time = time.time() - start_time

	method = request.method
	endpoint = request.url.path

	REQUESTS_TOTAL.labels(method=method, endpoint=endpoint).inc()
	REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(process_time)

	if response.status_code >= 400:
		REQUESTS_ERROR.labels(method=method, endpoint=endpoint, status_code=response.status_code).inc()

	return response


@router.get("/metrics")
async def get_metrics():
	# This endpoint itself is also instrumented by the middleware
	# Return Prometheus metrics in plain text format
	return generate_latest().decode("utf-8")
