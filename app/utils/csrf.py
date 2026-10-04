import hmac
import secrets
from functools import wraps
from flask import session, request, abort, render_template_string

CSRF_SESSION_KEY = "_csrf_token"

def get_csrf_token() -> str:
    """Retrieve or generate the CSRF token for the current user session."""
    if CSRF_SESSION_KEY not in session:
        session[CSRF_SESSION_KEY] = secrets.token_hex(32)
    return session[CSRF_SESSION_KEY]

def csrf_field() -> str:
    """Return a hidden HTML input containing the CSRF token."""
    token = get_csrf_token()
    return f'<input type="hidden" name="csrf_token" value="{token}">'

def validate_csrf():
    """Verify CSRF token for state-changing HTTP methods."""
    from flask import current_app
    if current_app.config.get("TESTING") or not current_app.config.get("CSRF_ENABLED", True):
        return

    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    # Check for exemptions if endpoint has csrf_exempt attribute
    if getattr(request.endpoint, "csrf_exempt", False):
        return

    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        abort(400, description="Invalid or missing security token (CSRF). Please refresh.")

    # Check form field or X-CSRFToken header (for HTMX and fetch)
    token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
    if not token or not hmac.compare_digest(str(token), str(expected)):
        abort(400, description="Security token validation failed. Please reload the page.")
