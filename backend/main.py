import sentry_sdk
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis

from .config import settings
from .routers import auth, invoices, metrics, notifications, projects, reports, requests

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,  # Adjust as needed
    )

app = FastAPI()

app.middleware("http")(metrics.metrics_middleware)


@app.on_event("startup")
async def startup():
    # Allow the API to start even if Redis is unavailable (e.g. local dev / unit tests).
    try:
        redis = Redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
        await redis.ping()
        await FastAPILimiter.init(redis)
    except Exception:
        return


app.include_router(projects.router, prefix="/api/v1")
app.include_router(requests.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
