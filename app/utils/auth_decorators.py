from functools import wraps
from typing import Optional
from flask import session, redirect, url_for, request, g, flash
from app.extensions import db
from app.models import PenName

def get_current_pen_name() -> Optional[PenName]:
    """Retrieve the current logged-in PenName object cached in Flask g context."""
    if hasattr(g, "current_pen_name"):
        return g.current_pen_name

    pen_name_id = session.get("pen_name_id")
    if not pen_name_id:
        g.current_pen_name = None
        return None

    pen_name = db.session.get(PenName, pen_name_id)
    g.current_pen_name = pen_name
    return pen_name

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_pen_name()
        if not user:
            flash("Please claim a pen name or open your desk to proceed.", "info")
            return redirect(url_for("auth.auth_view", next=request.path))
        return f(*args, **kwargs)
    return decorated_function
