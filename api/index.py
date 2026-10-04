import os
import sys
from pathlib import Path
from werkzeug.middleware.proxy_fix import ProxyFix

# Ensure root directory is on sys.path for serverless execution
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app import create_app
from app.extensions import db
from seed import seed_initial_data

import urllib.parse

class VercelPathFixMiddleware:
    """
    On Vercel, rewrites route incoming URLs to the serverless entrypoint
    destination (/api/index?_url_path=$1). This middleware extracts _url_path
    from the query string and restores PATH_INFO and clean QUERY_STRING so
    Flask routes match the user's intended route (e.g. /, /auth, /branches, /write).
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get("QUERY_STRING", "")
        if "_url_path" in query_string:
            qs_dict = urllib.parse.parse_qs(query_string, keep_blank_values=True)
            if "_url_path" in qs_dict:
                raw_path = qs_dict.pop("_url_path")[0]
                environ["QUERY_STRING"] = urllib.parse.urlencode(qs_dict, doseq=True)
                norm_path = raw_path if raw_path.startswith("/") else "/" + raw_path
                environ["PATH_INFO"] = norm_path
                return self.wsgi_app(environ, start_response)

        # Fallback 1: Check proxy headers (if not pointing to /api/index)
        matched_path = (
            environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
        )
        if matched_path and not matched_path.startswith("/api/index"):
            environ["PATH_INFO"] = matched_path.split("?")[0]
            return self.wsgi_app(environ, start_response)

        # Fallback 2: Normalize /api/index entrypoint
        path = environ.get("PATH_INFO", "")
        if path in ("/api/index", "/api/index.py", "/api"):
            environ["PATH_INFO"] = "/"
        elif path.startswith("/api/index/"):
            environ["PATH_INFO"] = path[len("/api/index"):]

        return self.wsgi_app(environ, start_response)

# Create Flask WSGI application instance
app = create_app()

# Apply Vercel proxy headers and path-fix middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

# Auto-initialize database tables and seed dispatches on cold start
with app.app_context():
    try:
        db.create_all()
        seed_initial_data()
    except Exception as e:
        print(f"Database initialization note: {e}")
