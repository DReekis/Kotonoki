from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from app.extensions import db, limiter
from app.models import Dispatch, Vote, Report, Branch
from app.services.branch_service import BranchService
from app.services.sanitizer_service import SanitizerService
from app.services.image_service import ImageService
from app.utils.auth_decorators import login_required, get_current_pen_name

dispatch_bp = Blueprint("dispatch", __name__)

@dispatch_bp.route("/write", methods=["GET"])
@login_required
def write_view():
    branch_param = request.args.get("branch", "")
    branches = BranchService.get_popular_branches(limit=30)
    return render_template("write.html", default_branch=branch_param, branches=branches)

@dispatch_bp.route("/write", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def create_dispatch():
    author = get_current_pen_name()
    title = request.form.get("title", "").strip()
    branch_name = request.form.get("branch", "").strip()
    raw_content = request.form.get("content_html", "").strip()
    uploaded_image = request.files.get("image")

    # 1. Title validation
    if not title or len(title) > 200:
        flash("Title is required and must be under 200 characters.", "error")
        return redirect(url_for("dispatch.write_view", branch=branch_name))

    # 2. Branch normalization and creation
    branch, branch_err = BranchService.get_or_create(branch_name)
    if branch_err:
        flash(branch_err, "error")
        return redirect(url_for("dispatch.write_view", branch=branch_name))

    # 3. Content sanitization
    sanitized_content = SanitizerService.sanitize_html(raw_content)
    if not sanitized_content:
        flash("Dispatch body cannot be empty.", "error")
        return redirect(url_for("dispatch.write_view", branch=branch_name))

    # 4. Optional image processing
    image_path = None
    if uploaded_image and uploaded_image.filename:
        image_path, img_err = ImageService.process_and_save(uploaded_image)
        if img_err:
            flash(img_err, "error")
            return redirect(url_for("dispatch.write_view", branch=branch_name))

    # 5. Persist dispatch
    dispatch = Dispatch(
        branch_id=branch.id,
        author_id=author.id,
        title=title,
        content_html=sanitized_content,
        image_path=image_path
    )
    db.session.add(dispatch)
    db.session.commit()

    flash("Dispatch published.", "success")
    return redirect(url_for("feed.view_dispatch", branch_slug=branch.slug, dispatch_id=dispatch.id))

@dispatch_bp.route("/dispatch/<string:dispatch_id>/vote", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def vote(dispatch_id: str):
    author = get_current_pen_name()
    dispatch = db.session.get(Dispatch, dispatch_id)
    if not dispatch:
        abort(404)

    try:
        vote_val = int(request.form.get("value", 0))
    except ValueError:
        abort(400)

    if vote_val not in (1, -1):
        abort(400)

    # Check existing vote
    existing_vote = db.session.execute(
        db.select(Vote).where(
            Vote.dispatch_id == dispatch.id,
            Vote.author_id == author.id
        )
    ).scalar_one_or_none()

    if existing_vote:
        if existing_vote.value == vote_val:
            # Clicking same vote removes it
            db.session.delete(existing_vote)
            user_vote = 0
        else:
            # Change vote
            existing_vote.value = vote_val
            user_vote = vote_val
    else:
        new_vote = Vote(dispatch_id=dispatch.id, author_id=author.id, value=vote_val)
        db.session.add(new_vote)
        user_vote = vote_val

    db.session.flush()

    # Recalculate vote counts directly from DB
    upvotes = db.session.execute(
        db.select(db.func.count(Vote.id)).where(Vote.dispatch_id == dispatch.id, Vote.value == 1)
    ).scalar() or 0
    downvotes = db.session.execute(
        db.select(db.func.count(Vote.id)).where(Vote.dispatch_id == dispatch.id, Vote.value == -1)
    ).scalar() or 0

    dispatch.upvotes_count = upvotes
    dispatch.downvotes_count = downvotes
    db.session.commit()

    return render_template(
        "partials/vote_widget.html",
        dispatch=dispatch,
        user_vote_value=user_vote
    )

@dispatch_bp.route("/dispatch/<string:dispatch_id>/strike", methods=["POST"])
@login_required
def strike(dispatch_id: str):
    author = get_current_pen_name()
    dispatch = db.session.get(Dispatch, dispatch_id)
    if not dispatch:
        abort(404)

    if dispatch.author_id != author.id:
        abort(403, description="You can only Strike your own dispatches.")

    # 1. Unlink associated image file from disk immediately
    if dispatch.image_path:
        ImageService.delete_image_file(dispatch.image_path)

    # 2. Permanent deletion from database
    branch_slug = dispatch.branch.slug
    db.session.delete(dispatch)
    db.session.commit()

    flash("Dispatch has been permanently Struck.", "info")
    if request.headers.get("HX-Request"):
        return "", 200, {"HX-Redirect": url_for("desk.desk_view")}
    return redirect(url_for("desk.desk_view"))

@dispatch_bp.route("/dispatch/<string:dispatch_id>/sticky", methods=["GET"])
def sticky_view(dispatch_id: str):
    dispatch = db.session.get(Dispatch, dispatch_id)
    if not dispatch:
        abort(404)

    return render_template("sticky.html", dispatch=dispatch)

@dispatch_bp.route("/dispatch/<string:dispatch_id>/report", methods=["POST"])
@limiter.limit("15 per hour")
def report_dispatch(dispatch_id: str):
    dispatch = db.session.get(Dispatch, dispatch_id)
    if not dispatch:
        abort(404)

    reason = request.form.get("reason", "Other").strip()
    valid_reasons = {"Spam", "Harassment", "Dangerous link", "Illegal content", "Other"}
    if reason not in valid_reasons:
        reason = "Other"

    reporter = get_current_pen_name()
    reporter_id = reporter.id if reporter else None

    rep = Report(
        dispatch_id=dispatch.id,
        reporter_id=reporter_id,
        reason=reason,
        status="open"
    )
    db.session.add(rep)
    db.session.commit()

    if request.headers.get("HX-Request"):
        return '<div class="report-success">Report submitted. Thank you.</div>'

    flash("Report submitted. Thank you.", "info")
    return redirect(url_for("feed.view_dispatch", branch_slug=dispatch.branch.slug, dispatch_id=dispatch.id))
