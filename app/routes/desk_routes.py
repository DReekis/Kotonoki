from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.auth_service import AuthService
from app.services.branch_service import BranchService
from app.utils.auth_decorators import login_required, get_current_pen_name
from app.models import Dispatch
from app.extensions import db

desk_bp = Blueprint("desk", __name__, url_prefix="/desk")

@desk_bp.route("", methods=["GET"])
@login_required
def desk_view():
    author = get_current_pen_name()
    dispatches = db.session.execute(
        db.select(Dispatch)
        .where(Dispatch.author_id == author.id)
        .order_by(Dispatch.published_at.desc())
    ).scalars().all()

    branches = BranchService.get_popular_branches(limit=30)

    return render_template(
        "desk.html",
        author=author,
        dispatches=dispatches,
        branches=branches
    )

@desk_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    author = get_current_pen_name()
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("desk.desk_view"))

    success, error = AuthService.change_password(author, old_password, new_password)
    if not success:
        flash(error or "Password update failed.", "error")
    else:
        flash("Password successfully updated.", "success")

    return redirect(url_for("desk.desk_view"))
