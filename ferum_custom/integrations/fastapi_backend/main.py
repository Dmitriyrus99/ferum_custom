import socket
from urllib.parse import urlparse

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


def _redis_is_reachable(redis_url: str) -> bool:
	parsed = urlparse(redis_url)

	if parsed.scheme == "unix":
		try:
			sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			sock.settimeout(0.2)
			sock.connect(parsed.path)
			sock.close()
			return True
		except OSError:
			return False

	host = parsed.hostname or "localhost"
	port = parsed.port or 6379
	try:
		with socket.create_connection((host, port), timeout=0.2):
			return True
	except OSError:
		return False


@app.on_event("startup")
async def startup():
	# Allow the API to start even if Redis is unavailable (e.g. local dev / unit tests).
	#
	# NOTE: Using `asyncio.wait_for` around `redis.ping()` can still hang on some environments because
	# cancellation may not reliably abort the underlying connect attempt. Prefer socket-level timeouts.
	if not _redis_is_reachable(settings.REDIS_URL):
		return

	redis = Redis.from_url(
		settings.REDIS_URL,
		encoding="utf-8",
		decode_responses=True,
		socket_connect_timeout=1.5,
		socket_timeout=1.5,
	)
	try:
		await redis.ping()
		await FastAPILimiter.init(redis)
	except Exception:
		await redis.close()
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
