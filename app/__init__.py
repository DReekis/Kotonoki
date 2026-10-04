import os
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, request, session
from app.config import Config
from app.extensions import db, limiter
from app.utils.csrf import get_csrf_token, csrf_field, validate_csrf
from app.utils.auth_decorators import get_current_pen_name
from app.services.sanitizer_service import SanitizerService

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload directory exists
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # CSRF protection hook
    @app.before_request
    def check_csrf():
        # Static routes and uploads are exempt from CSRF
        if request.endpoint and ("static" in request.endpoint or "serve_upload" in request.endpoint):
            return
        validate_csrf()

    # Template context processors
    @app.context_processor
    def inject_global_vars():
        return {
            "csrf_token": get_csrf_token,
            "csrf_field": csrf_field,
            "current_user": get_current_pen_name(),
            "now_utc": datetime.now(timezone.utc),
            "asset_version": "2.2"
        }

    # Template filters
    @app.template_filter("time_ago")
    def time_ago_filter(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt

        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d, %Y")

    @app.template_filter("excerpt")
    def excerpt_filter(html_content, length=220):
        return SanitizerService.extract_text_excerpt(html_content, max_length=length)

    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.feed_routes import feed_bp
    from app.routes.dispatch_routes import dispatch_bp
    from app.routes.desk_routes import desk_bp
    from app.routes.static_routes import static_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(desk_bp)
    app.register_blueprint(static_bp)
    app.register_blueprint(feed_bp)  # Registered last for /<branch_slug> catch-all

    # Security headers
    @app.after_request
    def set_security_headers(response):
        # Strict CSP allowlist
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # Custom Error Handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template("errors/error.html", code=400, title="Bad Request", message=str(e.description or "Invalid request parameters.")), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template("errors/error.html", code=403, title="Forbidden", message=str(e.description or "You do not have permission to perform this action.")), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template("errors/error.html", code=404, title="Not Found", message="The requested dispatch, branch, or resource does not exist."), 404

    @app.errorhandler(429)
    def ratelimit_error(e):
        return render_template("errors/error.html", code=429, title="Patience", message="You are performing actions too quickly. Please wait a moment before trying again."), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/error.html", code=500, title="System Error", message="An unexpected error occurred. The system has preserved its state."), 500

    return app
