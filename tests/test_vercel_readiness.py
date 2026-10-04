import json
import os
from pathlib import Path
import pytest

def test_vercel_json_validity():
    """Ensure vercel.json exists and has valid configuration for Python runtime."""
    vercel_path = Path("vercel.json")
    assert vercel_path.exists(), "vercel.json must exist in repository root"
    
    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "builds" in data
    assert any(b.get("src") == "api/index.py" and b.get("use") == "@vercel/python" for b in data["builds"])
    assert "routes" in data
    assert any(r.get("dest") == "api/index.py" for r in data["routes"])

def test_requirements_txt_complete():
    """Ensure requirements.txt contains all critical dependencies for Vercel."""
    req_path = Path("requirements.txt")
    assert req_path.exists(), "requirements.txt must exist in repository root"
    
    content = req_path.read_text(encoding="utf-8").lower()
    critical_packages = ["flask", "flask-sqlalchemy", "flask-limiter", "sqlalchemy", "argon2-cffi", "bleach", "pillow", "psycopg2-binary"]
    for pkg in critical_packages:
        assert pkg in content, f"Missing critical package in requirements.txt: {pkg}"

def test_api_index_entrypoint():
    """Ensure api/index.py imports cleanly and exports a valid Flask WSGI application."""
    from api.index import app
    assert app is not None
    assert app.name == "app"

def test_vercel_environment_simulation(monkeypatch):
    """Verify that when VERCEL is set, paths default to writable /tmp and postgresql:// is sanitized."""
    import importlib
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    
    import app.config
    importlib.reload(app.config)
    Config = app.config.Config
    
    # Without DATABASE_URL, Vercel defaults to /tmp/kotonoki.db
    assert "/tmp" in Config.SQLALCHEMY_DATABASE_URI
    assert "/tmp" in Config.UPLOAD_FOLDER
    assert Config.SESSION_COOKIE_SECURE is True
    
    # With postgres:// DATABASE_URL, it automatically converts to postgresql://
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host.neon.tech/db")
    importlib.reload(app.config)
    Config = app.config.Config
    assert Config.SQLALCHEMY_DATABASE_URI.startswith("postgresql://")
