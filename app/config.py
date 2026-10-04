import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "kotonoki-dev-insecure-secret-key-replace-in-prod-789012")
    
    # Database URL configuration (Supports Neon, Supabase, Vercel Postgres, Local SQLite)
    _raw_db_url = os.environ.get("DATABASE_URL")
    if _raw_db_url:
        if _raw_db_url.startswith("postgres://"):
            _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _raw_db_url
    elif os.environ.get("VERCEL"):
        # On Vercel serverless without external DB, fallback to writable /tmp
        SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/kotonoki.db"
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'kotonoki.db'}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings (use writable /tmp on Vercel)
    if os.environ.get("VERCEL"):
        UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp/uploads")
    else:
        UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))

    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12MB HTTP ceiling (allows 10MB image + form data)
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    IMAGE_MAX_DIMENSION = 1600
    IMAGE_QUALITY = 82
    
    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production" or os.environ.get("VERCEL") is not None
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30  # 30 days
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_HEADERS_ENABLED = True