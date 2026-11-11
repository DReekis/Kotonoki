from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from datetime import datetime, timezone
import io
import re
import zipfile
from sqlalchemy.orm import joinedload
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
        .options(joinedload(Dispatch.branch))
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

def html_to_markdown(html_content: str) -> str:
    """Convert clean dispatch HTML into legible, standard Markdown for export."""
    text = html_content
    text = re.sub(r'<h1>(.*?)</h1>', r'# \1\n\n', text, flags=re.I)
    text = re.sub(r'<h2>(.*?)</h2>', r'## \1\n\n', text, flags=re.I)
    text = re.sub(r'<h3>(.*?)</h3>', r'### \1\n\n', text, flags=re.I)
    text = re.sub(r'<b>(.*?)</b>|<strong>(.*?)</strong>', r'**\1\2**', text, flags=re.I)
    text = re.sub(r'<i>(.*?)</i>|<em>(.*?)</em>', r'*\1\2*', text, flags=re.I)
    text = re.sub(r'<u>(.*?)</u>', r'_\1_', text, flags=re.I)
    text = re.sub(r'<mark[^>]*>(.*?)</mark>', r'==\1==', text, flags=re.I)
    text = re.sub(r'<blockquote>(.*?)</blockquote>', r'> \1\n\n', text, flags=re.I)
    text = re.sub(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.I)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</p>', '\n\n', text, flags=re.I)
    text = re.sub(r'<p[^>]*>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)  # Strip remaining tags
    return text.strip()


@desk_bp.route("/export", methods=["POST"])
@login_required
def export_journal():
    author = get_current_pen_name()
    dispatches = db.session.execute(
        db.select(Dispatch)
        .options(joinedload(Dispatch.branch))
        .where(Dispatch.author_id == author.id)
        .order_by(Dispatch.published_at.desc())
    ).scalars().all()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = f"# {author.handle}'s Journal Archive\n\n"
        readme += f"Exported from Kotonoki (言の木) on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
        readme += f"Total Dispatches: {len(dispatches)}\n\n"
        readme += "## Dispatches Index\n\n"

        for idx, d in enumerate(dispatches, 1):
            date_str = d.published_at.strftime('%Y-%m-%d')
            slug_title = re.sub(r'[^a-zA-Z0-9_-]+', '-', d.title.lower()).strip('-')[:50]
            filename = f"dispatches/{date_str}_{slug_title or d.id[:8]}.md"

            readme += f"{idx}. [{d.title}]({filename}) — /{d.branch.slug} ({date_str})\n"

            md = f"---\ntitle: {d.title}\nbranch: {d.branch.slug}\npublished_at: {d.published_at.isoformat()}\nid: {d.id}\n"
            if d.image_path:
                md += f"image: {d.image_path}\n"
            md += f"---\n\n# {d.title}\n\n"
            md += f"**Branch:** /{d.branch.slug} · **Published:** {date_str}\n\n"
            md += html_to_markdown(d.content_html) + "\n"

            zf.writestr(filename, md.encode("utf-8"))

        zf.writestr("README.md", readme.encode("utf-8"))

    buffer.seek(0)
    safe_handle = re.sub(r'[^a-zA-Z0-9_-]', '', author.handle)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"kotonoki-{safe_handle}-journal.zip"
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


