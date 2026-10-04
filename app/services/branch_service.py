import re
from typing import Optional, Tuple, List
from app.extensions import db
from app.models import Branch

BRANCH_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

RESERVED_SLUGS = {
    "admin",
    "auth",
    "write",
    "about",
    "rules",
    "api",
    "static",
    "desk",
    "branch",
    "dispatch",
    "uploads",
    "health",
    "favicon.ico",
    "manifest.json",
    "sw.js",
    "robots.txt"
}

class BranchService:
    @staticmethod
    def normalize_slug(raw_name: str) -> str:
        """
        Normalize a user-provided branch string into a canonical kebab-case slug.
        e.g. 'Cast Iron' -> 'cast-iron', 'MIDNIGHT THOUGHTS' -> 'midnight-thoughts',
        '#books-2026' -> 'books-2026'
        """
        if not raw_name:
            return ""

        # Strip leading slashes, hashes, or whitespace
        slug = raw_name.strip().lstrip("/#").strip().lower()

        # Replace non-alphanumeric characters with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)

        # Remove leading/trailing hyphens and collapse consecutive hyphens
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug

    @classmethod
    def validate_slug(cls, slug: str) -> Tuple[bool, Optional[str]]:
        if not slug:
            return False, "Branch name cannot be empty."

        if len(slug) < 2 or len(slug) > 50:
            return False, "Branch name must be between 2 and 50 characters."

        if not BRANCH_REGEX.match(slug):
            return False, "Branch names may only contain lowercase letters, numbers, and single hyphens."

        if slug in RESERVED_SLUGS:
            return False, f"The branch name '/{slug}' is reserved by the system."

        return True, None

    @classmethod
    def get_or_create(cls, raw_name: str) -> Tuple[Optional[Branch], Optional[str]]:
        slug = cls.normalize_slug(raw_name)
        is_valid, error = cls.validate_slug(slug)
        if not is_valid:
            return None, error

        branch = db.session.execute(
            db.select(Branch).where(Branch.slug == slug)
        ).scalar_one_or_none()

        if not branch:
            branch = Branch(slug=slug)
            db.session.add(branch)
            db.session.commit()

        return branch, None

    @classmethod
    def get_popular_branches(cls, limit: int = 25) -> List[Branch]:
        """
        Return branches that have dispatches, ordered alphabetically or by recent usage.
        """
        return db.session.execute(
            db.select(Branch).order_by(Branch.slug.asc()).limit(limit)
        ).scalars().all()
