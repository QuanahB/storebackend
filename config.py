"""Settings for the OIMADIS store API used by the MockMSPaint frontend."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:4321,http://127.0.0.1:4321",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Config:
    """Development defaults. Override with environment variables in production."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MockMSPaint on :4321 and this API on :4000 are different ports on the
    # same host, so Lax cookies still ride along on credentialed fetches.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    CORS_ORIGINS = _origins()
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:4321")
    MAX_CONTENT_LENGTH = 1_000_000

    # Flat shipping until a carrier rate is connected. Free over this subtotal.
    SHIPPING_FLAT = "8.00"
    FREE_SHIPPING_OVER = "120.00"
