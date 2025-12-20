import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
	SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key")
	ALGORITHM: str = "HS256"
	ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
	ERP_API_URL: str = os.getenv("ERP_API_URL", "http://localhost:8000")
	ERP_API_KEY: str | None = os.getenv("ERP_API_KEY")
	ERP_API_SECRET: str | None = os.getenv("ERP_API_SECRET")
	TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
	SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")
	REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


settings = Settings()
