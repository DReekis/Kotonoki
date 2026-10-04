from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.extensions import limiter
from app.services.auth_service import AuthService
from app.utils.auth_decorators import get_current_pen_name

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("", methods=["GET"])
@auth_bp.route("/", methods=["GET"])
def auth_view():
    if get_current_pen_name():
        return redirect(url_for("desk.desk_view"))
    
    active_tab = request.args.get("tab", "register")
    next_url = request.args.get("next", "")
    return render_template("auth.html", active_tab=active_tab, next_url=next_url)

@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per 15 minutes")
def register():
    handle = request.form.get("handle", "")
    password = request.form.get("password", "")
    next_url = request.form.get("next", "")

    user, error = AuthService.register(handle, password)
    if error:
        flash(error, "error")
        return render_template("auth.html", active_tab="register", next_url=next_url, handle=handle), 422

    session.clear()
    session["pen_name_id"] = user.id
    session.permanent = True
    flash(f"Pen name '{user.handle}' claimed. Welcome to Kotonoki.", "success")

    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("feed.all_dispatches"))

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("15 per 15 minutes")
def login():
    handle = request.form.get("handle", "")
    password = request.form.get("password", "")
    next_url = request.form.get("next", "")

    user, error = AuthService.authenticate(handle, password)
    if error:
        flash(error, "error")
        return render_template("auth.html", active_tab="login", next_url=next_url, handle=handle), 401

    session.clear()
    session["pen_name_id"] = user.id
    session.permanent = True
    flash(f"Welcome back, {user.handle}.", "success")

    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("feed.all_dispatches"))

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("feed.all_dispatches"))
