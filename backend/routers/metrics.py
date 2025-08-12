from fastapi import APIRouter
from prometheus_client import generate_latest, Counter

router = APIRouter()

# Define a Counter metric
REQUESTS_TOTAL = Counter(
    'http_requests_total', 'Total HTTP requests', ['method', 'endpoint']
)

@router.get("/metrics")
async def get_metrics():
    # Increment the counter for this specific endpoint
    REQUESTS_TOTAL.labels(method='GET', endpoint='/metrics').inc()
    
    # Return Prometheus metrics in plain text format
    return generate_latest().decode("utf-8")