from fastapi import FastAPI
from .routers import projects, requests, reports, invoices, metrics, auth, notifications
from .config import settings
import sentry_sdk
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0, # Adjust as needed
    )

app = FastAPI()

@app.on_startup
async def startup():
    redis = Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis)

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