import base64
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select, and_, or_
from app.extensions import db
from app.models import Dispatch, Branch, Vote

DEFAULT_PAGE_SIZE = 20

def encode_cursor(dt: datetime, dispatch_id: str) -> str:
    """Encode published_at timestamp and dispatch_id into a safe URL cursor string."""
    epoch_ms = int(dt.timestamp() * 1000)
    raw = f"{epoch_ms}:{dispatch_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

def decode_cursor(cursor_str: str) -> Optional[Tuple[datetime, str]]:
    """Decode a cursor string back into (published_at, dispatch_id)."""
    if not cursor_str:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        epoch_ms_str, dispatch_id = raw.split(":", 1)
        epoch_ms = int(epoch_ms_str)
        dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
        return dt, dispatch_id
    except Exception:
        return None

class FeedService:
    @classmethod
    def get_feed(
        cls,
        branch_id: Optional[str] = None,
        author_id: Optional[str] = None,
        cursor_str: Optional[str] = None,
        viewer_pen_name_id: Optional[str] = None,
        limit: int = DEFAULT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """
        Pure reverse chronological feed with keyset/cursor pagination.
        Returns dispatches, next_cursor, and viewer vote mappings.
        """
        query = select(Dispatch).order_by(Dispatch.published_at.desc(), Dispatch.id.desc())

        if branch_id:
            query = query.where(Dispatch.branch_id == branch_id)

        if author_id:
            query = query.where(Dispatch.author_id == author_id)

        cursor = decode_cursor(cursor_str)
        if cursor:
            cursor_dt, cursor_id = cursor
            query = query.where(
                or_(
                    Dispatch.published_at < cursor_dt,
                    and_(Dispatch.published_at == cursor_dt, Dispatch.id < cursor_id)
                )
            )

        # Fetch limit + 1 to check for next page
        query = query.limit(limit + 1)
        dispatches = db.session.execute(query).scalars().all()

        has_more = len(dispatches) > limit
        items = dispatches[:limit]

        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            next_cursor = encode_cursor(last_item.published_at, last_item.id)

        # Batch lookup viewer's votes on these dispatches
        viewer_votes: Dict[str, int] = {}
        if viewer_pen_name_id and items:
            dispatch_ids = [d.id for d in items]
            votes = db.session.execute(
                select(Vote.dispatch_id, Vote.value).where(
                    Vote.dispatch_id.in_(dispatch_ids),
                    Vote.author_id == viewer_pen_name_id
                )
            ).all()
            for did, val in votes:
                viewer_votes[did] = val

        return {
            "dispatches": items,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "viewer_votes": viewer_votes
        }
