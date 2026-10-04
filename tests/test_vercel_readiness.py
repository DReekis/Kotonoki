import json
import os
from pathlib import Path
import pytest

def test_vercel_json_validity():
    """Ensure vercel.json exists and has valid configuration for serverless routing."""
    vercel_path = Path("vercel.json")
    assert vercel_path.exists(), "vercel.json must exist in repository root"
    
    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert "rewrites" in data or "routes" in data
    if "rewrites" in data:
        assert any(r.get("destination") == "/api/index" for r in data["rewrites"])

def test_requirements_txt_complete():
    """Ensure requirements.txt and api/requirements.txt contain all critical dependencies for Vercel."""
    for path_str in ["requirements.txt", "api/requirements.txt"]:
        req_path = Path(path_str)
        assert req_path.exists(), f"{path_str} must exist"
        
        content = req_path.read_text(encoding="utf-8").lower()
        critical_packages = ["flask", "flask-sqlalchemy", "flask-limiter", "sqlalchemy", "argon2-cffi", "nh3", "bleach", "pillow", "psycopg", "psycopg2-binary"]
        for pkg in critical_packages:
            assert pkg in content, f"Missing critical package in {path_str}: {pkg}"

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

def test_vercel_static_assets_present():
    """Ensure public/ directory contains all critical static assets for direct CDN delivery on Vercel."""
    public_dir = Path("public")
    assert public_dir.exists(), "public/ folder must exist in repository root for Vercel CDN static delivery"
    
    required_assets = [
        "public/static/css/tokens.css",
        "public/static/css/explorer.css",
        "public/static/css/sticky.css",
        "public/static/css/print.css",
        "public/static/js/app.js",
        "public/static/js/htmx.min.js",
        "public/static/icons/icon-192.png",
        "public/manifest.json",
        "public/sw.js"
    ]
    for asset in required_assets:
        p = Path(asset)
        assert p.exists(), f"Required static asset missing: {asset}"
        assert p.stat().st_size > 0, f"Static asset is empty: {asset}"

def test_static_mime_types_and_delivery():
    """Verify that static assets serve with proper text/css and javascript MIME types."""
    from api.index import app
    with app.test_client() as client:
        r_css = client.get("/static/css/explorer.css")
        assert r_css.status_code == 200
        assert "text/css" in r_css.headers.get("Content-Type", "")
        
        r_tokens = client.get("/static/css/tokens.css")
        assert r_tokens.status_code == 200
        assert "text/css" in r_tokens.headers.get("Content-Type", "")
        
        r_js = client.get("/static/js/app.js")
        assert r_js.status_code == 200
        assert any(t in r_js.headers.get("Content-Type", "") for t in ["javascript", "text/plain"])

def test_vercel_rewrite_path_resolution():
    """Verify that VercelPathFixMiddleware maps /api/index rewrite paths to correct routes."""
    from api.index import app
    with app.test_client() as client:
        # Case 1: Rewrite to /api/index with x-matched-path: /
        r_home = client.get("/api/index", headers={"x-matched-path": "/"})
        assert r_home.status_code == 200
        assert b"All Dispatches" in r_home.data
        assert b"Error 404" not in r_home.data

        # Case 2: Rewrite to /api/index with x-matched-path: /branches
        r_branches = client.get("/api/index", headers={"x-matched-path": "/branches"})
        assert r_branches.status_code == 200
        assert b"Browse Branches" in r_branches.data or b"Branches" in r_branches.data
        assert b"Error 404" not in r_branches.data

        # Case 3: Direct /api/index hit without headers -> fallback to home
        r_direct = client.get("/api/index")
        assert r_direct.status_code == 200
        assert b"All Dispatches" in r_direct.data
        assert b"Error 404" not in r_direct.data

        # Case 4: Subpath hit /api/index/branches -> redirect to /branches
        r_subpath = client.get("/api/index/branches")
        assert r_subpath.status_code in (200, 302)


