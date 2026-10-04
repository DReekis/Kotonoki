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

class VercelPathFixMiddleware:
    """
    On Vercel, rewrites route incoming URLs (e.g. /, /branches, /write) to
    the serverless entrypoint destination (/api/index). This causes WSGI
    PATH_INFO to be set to '/api/index' while Vercel passes the original
    requested URI in 'HTTP_X_MATCHED_PATH' or 'HTTP_X_FORWARDED_URI'.
    
    This middleware restores the original PATH_INFO so Flask's URL routing
    matches the user's intended route instead of raising a 404 on /api/index.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched_path = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
        )
        if matched_path:
            if "?" in matched_path:
                path_part, query_part = matched_path.split("?", 1)
                environ["PATH_INFO"] = path_part
                if not environ.get("QUERY_STRING"):
                    environ["QUERY_STRING"] = query_part
            else:
                environ["PATH_INFO"] = matched_path
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index.py", "/api"):
            environ["PATH_INFO"] = "/"
        elif environ.get("PATH_INFO", "").startswith("/api/index/"):
            environ["PATH_INFO"] = environ["PATH_INFO"][len("/api/index"):]

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
