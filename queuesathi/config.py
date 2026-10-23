import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # If set, PostgreSQL is used. If empty, local SQLite is used.
    DATABASE_URL = os.getenv("DATABASE_URL")

    REFRESH_INTERVAL = 10000

    DEFAULT_SERVICE_SECONDS = 300

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Render sets RENDER=true automatically. Cookies are HTTPS-only there.
    SESSION_COOKIE_SECURE = os.getenv("RENDER") == "true"

    WTF_CSRF_ENABLED = True