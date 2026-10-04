from flask import Blueprint, render_template, request, abort, redirect, url_for
from app.extensions import db
from app.models import Branch, Dispatch
from app.services.feed_service import FeedService
from app.services.branch_service import BranchService, RESERVED_SLUGS
from app.utils.auth_decorators import get_current_pen_name

feed_bp = Blueprint("feed", __name__)

@feed_bp.route("/", methods=["GET"])
def all_dispatches():
    cursor = request.args.get("before")
    current_user = get_current_pen_name()
    current_user_id = current_user.id if current_user else None

    branches = BranchService.get_popular_branches(limit=30)
    feed_data = FeedService.get_feed(
        cursor_str=cursor,
        viewer_pen_name_id=current_user_id,
        limit=20
    )

    if request.headers.get("HX-Request") and request.args.get("partial") == "true":
        return render_template(
            "partials/dispatch_list.html",
            dispatches=feed_data["dispatches"],
            next_cursor=feed_data["next_cursor"],
            has_more=feed_data["has_more"],
            viewer_votes=feed_data["viewer_votes"],
            current_branch=None,
            feed_url=url_for("feed.all_dispatches")
        )

    return render_template(
        "feed.html",
        dispatches=feed_data["dispatches"],
        next_cursor=feed_data["next_cursor"],
        has_more=feed_data["has_more"],
        viewer_votes=feed_data["viewer_votes"],
        branches=branches,
        current_branch=None,
        feed_title="All Dispatches",
        feed_url=url_for("feed.all_dispatches")
    )

@feed_bp.route("/<string:branch_slug>", methods=["GET"])
def branch_feed(branch_slug: str):
    slug = branch_slug.lower()
    if slug in RESERVED_SLUGS:
        abort(404)

    branch = db.session.execute(
        db.select(Branch).where(Branch.slug == slug)
    ).scalar_one_or_none()

    if not branch:
        # Branch does not exist yet; offer clean empty state
        branch = Branch(slug=slug)

    cursor = request.args.get("before")
    current_user = get_current_pen_name()
    current_user_id = current_user.id if current_user else None

    branches = BranchService.get_popular_branches(limit=30)
    feed_data = FeedService.get_feed(
        branch_id=branch.id if branch.id else "non-existent",
        cursor_str=cursor,
        viewer_pen_name_id=current_user_id,
        limit=20
    )

    feed_url = url_for("feed.branch_feed", branch_slug=slug)

    if request.headers.get("HX-Request") and request.args.get("partial") == "true":
        return render_template(
            "partials/dispatch_list.html",
            dispatches=feed_data["dispatches"],
            next_cursor=feed_data["next_cursor"],
            has_more=feed_data["has_more"],
            viewer_votes=feed_data["viewer_votes"],
            current_branch=branch,
            feed_url=feed_url
        )

    return render_template(
        "feed.html",
        dispatches=feed_data["dispatches"],
        next_cursor=feed_data["next_cursor"],
        has_more=feed_data["has_more"],
        viewer_votes=feed_data["viewer_votes"],
        branches=branches,
        current_branch=branch,
        feed_title=f"/{slug}",
        feed_url=feed_url
    )

@feed_bp.route("/<string:branch_slug>/<string:dispatch_id>", methods=["GET"])
def view_dispatch(branch_slug: str, dispatch_id: str):
    slug = branch_slug.lower()
    if slug in RESERVED_SLUGS:
        abort(404)

    dispatch = db.session.execute(
        db.select(Dispatch).where(Dispatch.id == dispatch_id)
    ).scalar_one_or_none()

    if not dispatch:
        abort(404, description="Dispatch not found or has been Struck.")

    # Redirect canonical branch if slug doesn't match
    if dispatch.branch.slug != slug:
        return redirect(url_for("feed.view_dispatch", branch_slug=dispatch.branch.slug, dispatch_id=dispatch_id))

    current_user = get_current_pen_name()
    user_vote_value = 0
    if current_user:
        from app.models import Vote
        v = db.session.execute(
            db.select(Vote.value).where(
                Vote.dispatch_id == dispatch.id,
                Vote.author_id == current_user.id
            )
        ).scalar_one_or_none()
        if v:
            user_vote_value = v

    branches = BranchService.get_popular_branches(limit=30)
    return render_template(
        "dispatch_detail.html",
        dispatch=dispatch,
        user_vote_value=user_vote_value,
        branches=branches,
        current_branch=dispatch.branch
    )
